"""Run exact combined card entries and both journal callbacks; hardware I/O mocked."""
import argparse
import json
from pathlib import Path
import struct
import sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT/'custom-modes'),
               str(ROOT/'color-modes/lv-boost')]
import verify_card as V
from test_indoor import IndoorCamera, Prototype

V.T.IMAGE = ROOT.parent/'out/MAIN_c0000000.bin'
V.B.ROM = V.T.IMAGE
V.B.SEG1 = ROOT.parent/'out/seg1_c2ef6e00.bin'
M = None
MODULE = None
NEGATIVE = False


class Combined(V.Card):
    put = Prototype.put
    preset = IndoorCamera.preset
    fixture = Prototype.fixture

    def __init__(self, loader, binary):
        # One-word negative control: returning from focus entry must fail.
        if NEGATIVE:
            n = struct.unpack_from('<I', binary, 4)[0]
            pos = 16 + 8*n
            for i in range(n):
                dest, size = struct.unpack_from('<2I', binary, 16 + 8*i)
                if dest == 0 and binary[pos:pos+size] == MODULE:
                    binary = bytearray(binary)
                    struct.pack_into('<I', binary, pos, 0xe12fff1e)
                    binary = bytes(binary)
                    break
                pos += size + (-size % 4)
            else:
                raise AssertionError('Focus module missing from negative control')
        super().__init__(loader, binary)

    def _hook(self, mu, addr, size, data):
        if addr in (0xc0013090, 0xc0010298, 0xc00102d0):
            return self._ret(0)
        if addr == 0xc0011100:
            raise AssertionError('Native assertion')
        return super()._hook(mu, addr, size, data)


def check_focus(c):
    targets = []
    for site, wrapper, kind in M['sites']:
        original = struct.unpack_from('<I', c.stock, site-0xc0000000)[0]
        word = c.word(site)
        assert word != original, f'Focus hook absent: {site:#x}'
        if kind == 3:
            insn = list(Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(bytes(c.mu.mem_read(site, 4)), site))
            assert len(insn) == 1 and insn[0].mnemonic == 'b.w'
            veneer = int(insn[0].op_str.lstrip('#'), 16)
            assert c.word(veneer) == 0xf000f8df
        else:
            displacement = word & 0xffffff
            if displacement & 0x800000: displacement -= 0x1000000
            veneer = site + 8 + displacement*4
            assert c.word(veneer) == 0xe51ff004
        assert 0xc072e064 <= veneer < c.word(0xc072e060) <= 0xc072efb4
        targets.append(c.word(veneer+4) - (M['symbols'][wrapper]-M['symbols']['resident']))
    assert len(set(targets)) == 1, 'Focus hooks disagree on resident'
    resident = targets[0]
    body = MODULE[M['symbols']['resident']:]
    assert bytes(c.mu.mem_read(resident, len(body))) == body
    assert all(not at <= resident < at+n for at, n in c.freed), 'Focus resident retained staging'


def draw_warning(c, desc):
    c.mu.reg_write(V.UC_ARM_REG_R5, 3)
    c.call(0xc052884c,desc,lr=0xc0528850,sp=V.STACK)
    c.call(0xc05288e4,desc,lr=0xc05288e8,sp=V.STACK)


V.Card = Combined
V.check_focus = check_focus
V.draw_warning = draw_warning
exec((ROOT/'focus-inset/combined_checks.py').read_text(), V.__dict__)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cards', type=Path, nargs='+')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--focus-directory', type=Path,
                        default=ROOT/'out/focus-release-build')
    args = parser.parse_args()
    M = json.loads((args.focus_directory/'manifest.json').read_text())
    MODULE = (args.focus_directory/'inset-trial.arm').read_bytes()
    NEGATIVE = args.negative
    for card in args.cards:
        if NEGATIVE:
            try: V.verify(card)
            except AssertionError as e:
                assert 'Focus hook absent' in str(e), str(e)
                print('PASS negative: one-word focus entry bypass detected')
            else: raise AssertionError('Focus bypass was not detected')
        else:
            V.verify(card)
            print('PASS exact combined entries, Indoor warning, LV resident/tone, Focus residency and both shutdown callbacks')
