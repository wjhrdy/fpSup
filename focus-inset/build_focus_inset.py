"""Build the ordinary merge-compatible Focus Inset card for fp firmware 5.02."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace
from elf_text import load_text

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHELL = ROOT / 'fp_usb_shell'
sys.path.insert(0, str(SHELL))
from armasm import assemble, symbols

ROM_HASH = 'aaa5208a028d9c4aebb9cc8614add723d456e96b2a95914f433079954320e622'

def compile_core(directory, source=None):
    path = HERE / 'focus_inset.c'
    if source is not None:
        path = Path(directory) / 'mutation.c'
        path.write_text(source)
    obj = Path(directory) / 'focus_inset.o'
    subprocess.run(['clang', '-target', 'armv7-none-eabi', '-mcpu=cortex-a9',
        '-marm', '-mfloat-abi=soft', '-mfpu=none', '-O2', '-ffreestanding',
        '-fno-builtin', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
        '-Wall', '-Wextra', '-Werror', '-c', str(path), '-o', str(obj)], check=True)
    return load_text(obj)


# kind: ARM BL, ARM B, pointer, Thumb B.W. Each site is journaled separately.
SITES = [(0xc05d9f90, 'layout', 3), (0xc00e9c20, 'submit', 3),
         (0xc0429d1c, 'picture', 0), (0xc04369f8, 'preview', 0),
         (0xc0436af0, 'crop', 0), (0xc0481a08, 'transition', 1),
         (0xc05d0288, 'visible', 3), (0xc05dc178, 'controls', 3),
         (0xc0305b98, 'peaking', 1), (0xc0428bec, 'initial_crop', 0)]


def build(firmware, output):
    image = Path(firmware).read_bytes()
    assert hashlib.sha256(image).hexdigest() == ROM_HASH, "Requires SIGMA fp firmware 5.02"
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    core = compile_core(output)
    (output/'core.arm').write_bytes(core.code)
    table = output/'hooks.inc'
    names = ['PREVIEW', 'CROP', 'REFRESH', 'PREPARE', 'LAYOUT', 'PICTURE', 'VISIBLE', 'CONTROLS', 'PEAKING', 'INITIAL_CROP']
    defs = [f'CORE_FILE="{output / "core.arm"}"', f'HOOK_TABLE="{table}"',
            f'HOOK_COUNT={len(SITES)}']
    for name in names:
        defs.append(f'{name}_OFF={core.functions["focus_inset_" + {"DISPLAY":"display_mode"}.get(name,name.lower())]}')
    rows = []
    for site, wrapper, kind in SITES:
        assert site % 4 == 0 # Shared journal and bounded USB word reads.
        original = image[site-0xc0000000:site-0xc0000000+4]
        word = struct.unpack('<I',original)[0]
        if kind == 0:
            if wrapper == 'picture':
                assert word == 0xfaf6b32b  # ARM BLX C01D69D1; veneer uses ARM BL.
                expected = None
            else:
                expected = {'preview':0xc0436b80, 'crop':0xc030cc90, 'initial_crop':0xc042a178}[wrapper]
            displacement = (word & 0xffffff)
            if displacement & 0x800000: displacement -= 0x1000000
            if expected is not None:
                assert word >> 24 == 0xeb and site+8+4*displacement == expected
        if kind == 2: assert word == 0xc0481470
        if kind == 1: assert word == {'transition':0xe92d40f0, 'peaking':0xe92d4bf0}[wrapper]
        if kind == 3:
            assert 0 < 0xc072efb4-site-4 < 0x800000
            if wrapper == 'visible': assert word == 0xbf082800 # cmp r0,0; it eq
            if wrapper == 'controls': assert word == 0x4ff0e92d # push.w r4-r11,lr
        (output/f'{site:08x}.stock').write_bytes(original)
        rows.append(f'.word {site:#x}, {word:#x}, {wrapper}-resident, {kind}')
    table.write_text('\n'.join(rows)+'\n')
    source=HERE/'trial.S'
    blob,syms=assemble(source,defs),symbols(source,defs)
    assert syms['entry']==0 and syms['resident_end']==len(blob) and len(blob)%4==0
    (output/'inset-trial.arm').write_bytes(blob)
    # Ordinary card: Fast Start and optional Shell are added by the composer.
    cmd=[sys.executable,'-B',str(SHELL/'build_autorun.py'),'--loader','--no-shell',
         '--no-pad','--bin-name','fpSup.BIN','--boot-bin',str(output/'inset-trial.arm')+':0',
         '--out',str(output/'AutoRun.txt')]
    for site,_,_ in SITES:cmd+=['--also-bin',f'{site:#x}:{output/f"{site:08x}.stock"}']
    result=subprocess.run(cmd,check=True,capture_output=True,text=True)
    (output/'build.log').write_text(result.stdout+result.stderr)
    manifest={'kind':'ordinary fpSup-Merge input; no bundled USB Shell or Fast Start',
        'firmware_sha256':hashlib.sha256(image).hexdigest(),'sites':SITES,'symbols':syms,
        'core_functions':core.functions,'resident_bytes':syms['resident_end']-syms['resident'],
        'hardware_tested':False,'automatic_activation':'preview-only local mode descriptor; native MF state, toggle, resume and saved display preference are stock',
        'layout_adapter':'native variable listener C05D9F90 before dispatch lock; app +84c active screen; recursive notifications pass through',
        'controls_adapter':'C05DC178 post-variable-binding dispatch after callbacks/locks; native current-only visibility setter C05D63A9 for all three complementary MagnifyStatus display groups and redraw after correction, defaults unchanged',
        'picture_adapter':'C0429D1C OpNew channel-4 local output copy; manual STILL and exact native 1620x1080 preview layout only',
        'peaking_adapter':'C0305B98 native core-region output postprocessor; supported STILL manual-lens PIP profiles use their stock full visible rectangle, inclusive endpoints; preferences and native enable gates unchanged',
        'command':cmd,'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir() if p.suffix in ('.arm','.BIN','.txt','.stock')}}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.firmware,a.output),indent=2))
