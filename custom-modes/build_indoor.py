#!/usr/bin/env python3
"""Build the ordinary Indoor input for fpSup-Merge (fp firmware 5.02)."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ROOT = REPO.parent  # same firmware layout as fp_usb_shell/test_loader_hook.py
SHELL = REPO / 'fp_usb_shell'
sys.path.insert(0, str(SHELL))
from armasm import assemble, symbols

SITE, DRAW_SITE = 0xC021EE94, 0xC052884C
SCAN_SITE, RESULT_SITE = 0xC0209DF0, 0xC02100E4
ROM_HASH = 'aaa5208a028d9c4aebb9cc8614add723d456e96b2a95914f433079954320e622'
# Includes cleanup of previous experimental detector, overlay and BF hooks.
STOCK = {SITE: 0xEB0017F5, DRAW_SITE: 0xE1A03000, SCAN_SITE: 0xEBFFFE2A,
         RESULT_SITE: 0xEB000173, 0xC0226508: 0xE92D4DF0}


def build(out, *, tv60=6049, fast_start2=False):
    # Fast is exercised by emulation only; distributable inputs are ordinary.
    rom = (ROOT / 'out/MAIN_c0000000.bin').read_bytes()
    assert hashlib.sha256(rom).hexdigest() == ROM_HASH, 'Requires fp 5.02'
    assert 5970 <= tv60 <= 6130, 'Calibration limited to about +/- 5%'
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    src, defines = HERE / 'indoor.S', [f'TV60={tv60}']
    blob, syms = assemble(src, defines), symbols(src, defines)
    assert syms['entry'] == 0 and syms['resident_end'] == len(blob)
    (out / 'indoor.bin').write_bytes(blob)
    cmd = [sys.executable, '-B', str(SHELL / 'build_autorun.py'), '--loader',
           '--no-shell', '--boot-bin', str(out / 'indoor.bin') + ':0',
           '--out', str(out / 'AutoRun.txt')]
    for at, word in STOCK.items():
        data = rom[at-0xC0000000:at-0xC0000000+4]
        assert data == struct.pack('<I', word)
        p = out / f'{at:08x}.bin'
        p.write_bytes(data)
        cmd += ['--also-bin', f'{at:#x}:{p}']
    if fast_start2:
        cmd += ['--store-boot', '--loader-hook', '--four-box-bar']
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    (out / 'build.log').write_text(result.stdout + result.stderr)
    assert (out / 'fpSup.BIN').stat().st_size <= 0xF000
    manifest = dict(firmware='SIGMA fp 5.02', main_sha256=ROM_HASH,
                    family_base_tv=tv60+1024, fast_start2=fast_start2,
                    activation='custom P slot named Indoor, case insensitive',
                    hardware_tested=False, symbols=syms,
                    sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in out.iterdir() if p.suffix in ('.BIN', '.txt')})
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return out, manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True, help='Fresh output directory')
    ap.add_argument('--tv60', type=int, default=6049, help='60 Hz APEX calibration; Indoor adds 1024')
    args = ap.parse_args()
    print(build(args.out, tv60=args.tv60)[0])
