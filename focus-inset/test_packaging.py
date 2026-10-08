"""Exact combined BIN: reject loading when journal allocation/registration fails."""
import importlib.util
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('guard_camera', ROOT/'fp_usb_shell/test_loader_hook.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
t.IMAGE = ROOT.parent/'out/MAIN_c0000000.bin'


def check(card):
    loader = {int(a,16):int(v,16) for a,v in re.findall(
        r'^mem set (0x\w+) (0x\w+)', (card/'AutoRun.txt').read_text(), re.M)
        if t.CAVE_LOW <= int(a,16) < t.CAVE_LOW+0x200}
    for failure in ('heap','allocation','ordinary','forced'):
        c = t.Camera(loader, (card/'fpSup.BIN').read_bytes(), journal_failure=failure)
        c.call(t.CAVE_LOW)
        assert 'ENTRY' not in c.calls, f'Unsafe entry after {failure} failure'
        for a,n in c.sections():
            if a >= 0x40000000 and not t.CAVE_LO <= a < t.CAVE_HI:
                assert bytes(c.mu.mem_read(a,n)) == c.stock[a-0xc0000000:a-0xc0000000+n]
        assert c.word(t.SITE) == t.SITE_ORIG
        assert c.r(t.UC_ARM_REG_PC) == t.DONE
        print('PASS guarded combined card:',failure)


check(Path(sys.argv[1]))
if len(sys.argv) > 2:
    try: check(Path(sys.argv[2]))
    except AssertionError as e:
        assert 'Unsafe entry' in str(e)
        print('PASS negative: previous stage2 without guards is rejected')
    else: raise AssertionError('Unguarded stage2 was not detected')
