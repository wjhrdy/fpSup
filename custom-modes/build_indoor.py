#!/usr/bin/env python3
"""Build native Indoor merge input with banding warning, fp 5.02; no card access."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ROOT = REPO.parent  # same extracted firmware layout as shared loader tests
SHELL = REPO / 'fp_usb_shell'
sys.path.insert(0, str(SHELL))
from armasm import assemble, symbols
ROM_HASH = 'aaa5208a028d9c4aebb9cc8614add723d456e96b2a95914f433079954320e622'
SITE, DRAW_SITE = 0xC021EE94, 0xC052884C
SCAN_SITE, RESULT_SITE = 0xC0209DF0, 0xC02100E4
STOCK = {SITE:0xEB0017F5, DRAW_SITE:0xE1A03000, SCAN_SITE:0xEBFFFE2A,
         RESULT_SITE:0xEB000173, 0xC0226508:0xE92D4DF0}

GETTER = 0xc0210118


def build(out, fast=False):
    rom = (ROOT/'out/MAIN_c0000000.bin').read_bytes()
    assert hashlib.sha256(rom).hexdigest() == ROM_HASH
    src = Path(__file__).with_name('indoor.S')
    blob, syms = assemble(src), symbols(src)
    assert syms['entry'] == 0 and syms['resident_end'] == len(blob)
    assert 'extend_family' not in syms
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    (out/'native-indoor.bin').write_bytes(blob)
    cmd = [sys.executable, '-B', str(SHELL/'build_autorun.py'),
           '--loader', '--no-shell', '--boot-bin', str(out/'native-indoor.bin')+':0',
           '--out', str(out/'AutoRun.txt')]
    # Old Indoor/BF hooks restored to stock by stage2. Getter and read-only OSD overlay are the new hooks.
    for addr, word in {**STOCK, GETTER:0xe92d4010}.items():
        data = rom[addr-0xc0000000:addr-0xc0000000+4]
        assert data == struct.pack('<I', word)
        p = out/f'{addr:08x}.bin'; p.write_bytes(data)
        cmd += ['--also-bin', f'{addr:#x}:{p}']
    if fast:
        cmd += ['--store-boot', '--loader-hook', '--four-box-bar']
    r = subprocess.run(cmd, check=True, capture_output=True, text=True)
    (out/'build.log').write_text(r.stdout+r.stderr)
    assert (out/'fpSup.BIN').stat().st_size <= 0xF000
    manifest = dict(version='0.4.0', firmware='fp 5.02', main_sha256=ROM_HASH,
                    activation='custom P preset Indoor/Indoor60 (60 Hz) or Indoor50 (50 Hz); STILL, no program shift',
                    policy='effective flicker classification 1/2 from name; native exposure code unchanged',
                    warning='BANDING RISK in Indoor STILL P live-view, NoLensIris selector 0 and selected Tv > 7073 (60 Hz 1/120) or > 6803 (50 Hz 1/100)',
                    hardware_tested=False, fast=fast, symbols=syms,
                    sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in out.iterdir() if p.name in ('AutoRun.txt','fpSup.BIN')})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return out, manifest


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); print(build(a.out)[0])
