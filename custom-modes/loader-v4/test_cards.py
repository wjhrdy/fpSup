"""Offline tests of the real v4 card, loader journal, and both module hooks."""
import argparse
from pathlib import Path
import struct
import sys

from unicorn.arm_const import (UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R5,
                               UC_ARM_REG_R11, UC_ARM_REG_SP)

from build import HERE, REPO, INDOOR, LV


def verify(upstream, cards):
    sys.path[:0] = [str(upstream / 'fpSup/loader-v4'), str(HERE.parent),
                    str(REPO / 'color-modes/lv-boost')]
    import test_boot_card_v4 as boot
    import test_ui_v4 as ui
    from test_boot_slim_v4 import bl_target
    from build_v4 import test_sup
    from indoor_fixture import IndoorCamera, Prototype
    from read_diagnostics import resident

    t = boot.T3
    seg = (REPO / 'out/seg1_c2ef6e00.bin').read_bytes()
    sp = t.STACK - 0x1000
    save, saved = 0xC307544C, 0x4C560106
    tone, getter = 0xC02D2E50, 0xC0210118
    loader_log = r'\fpSup\LOAD.LOG'

    class Camera(boot.Camera, ui.Cam):
        put = Prototype.put
        word = boot.Camera.w
        preset = IndoorCamera.preset
        fixture = Prototype.fixture

        def __init__(self, card, extra=(), fail_lv=False):
            self.fail_lv, self.lv_tasks = fail_lv, []
            ar = (card / 'AutoRun.txt').read_bytes()
            mods = [(p.name, p.read_bytes()) for p in (card / 'fpSup').glob('*.BIN')
                    if p.name != 'LOADER.BIN']
            super().__init__(ar, (card / 'fpSup/LOADER.BIN').read_bytes(),
                             mods + list(extra), active=True)
            autorun_table = bytes(self.mu.mem_read(boot.TABLE, 0x220))
            self.mu.mem_write(0xc2ef6e00, seg)
            self.mu.mem_write(boot.TABLE, autorun_table)
            for p in (card / 'fpSup/UI').glob('*.BIN'):
                self.files['\\fpSup\\UI\\' + p.name] = p.read_bytes()
            self.put(save, saved)
            self.now = 15_000_000

        def _hook(self, mu, addr, size, data):
            if addr in (0xc0013090, 0xc0010298, 0xc00102d0):
                return self._ret(0)
            if addr == 0xc0011100:
                raise AssertionError('Native firmware assertion')
            if addr == t.F['H_GET'] and self.fail_lv and self.r(UC_ARM_REG_R2) == 0x7000:
                self.put(self.r(UC_ARM_REG_R0), 0)
                return self._ret(0)
            if addr == t.F['TK_CRE']:
                desc = self.r(UC_ARM_REG_R0)
                if self.w(desc + 20) == 0x4F544146:
                    self.lv_tasks.append((self.w(desc + 8), self.w(desc + 16)))
            return super()._hook(mu, addr, size, data)

        def call(self, pc, r0=0, r1=0, r2=None, lr=t.DONE, sp=t.STACK - 0x1004, thumb=False):
            if lr == t.DONE:
                return super().call(pc, r0, r1, r2 or 0, lr, sp, thumb)
            if r2 is not None:
                self.mu.reg_write(UC_ARM_REG_R2, r2)
            for reg, value in ((UC_ARM_REG_R0, r0), (UC_ARM_REG_R1, r1),
                               (UC_ARM_REG_SP, sp), (UC_ARM_REG_LR, lr)):
                self.mu.reg_write(reg, value)
            self.mu.emu_start(pc, lr, count=2_000_000)
            if self.error:
                raise self.error
            assert (self.r(UC_ARM_REG_PC), self.r(UC_ARM_REG_SP)) == (lr, sp), (
                hex(pc), hex(self.r(UC_ARM_REG_PC)), hex(lr), hex(self.r(UC_ARM_REG_SP)), hex(sp))
            return self.r(UC_ARM_REG_R0), self.r(UC_ARM_REG_SP)

        def journal(self):
            result = []
            for obj in dict.fromkeys(o for o, _ in self.registered):
                assert {kind for o, kind in self.registered if o == obj} == {0, 1}
                e = self.w(obj + 8)
                while self.w(e):
                    a, n = self.w(e), self.w(e + 4)
                    result.append((a, n, bytes(self.mu.mem_read(e + 8, n))))
                    e += 8 + n
            return result

    def check_loaded(cam, peer=None):
        log = cam.loaded()
        assert {INDOOR, LV, 'SUPMGR.BIN'}.issubset(log), cam.loadlog()
        if peer:
            assert peer in log, cam.loadlog()
        assert any(c == 0x32 and a == 0 for c, a, _, _ in cam.loadlog()), cam.loadlog()
        assert cam.misaligned == [], cam.misaligned
        assert cam.w(t.DRAW) == t.DRAW_STOCK
        assert cam.w(save) == saved and len(cam.lv_tasks) == 1
        assert cam.w(0xc06c07d8) == 0xe3a02011
        res = resident([cam.w(0xc06c07cc), cam.w(0xc06c07d0)])
        task, stack = cam.lv_tasks[0]
        assert stack == 0x2000 and res <= task < res + 0x2600
        assert all(not a <= res < a + cam.allocs.get(a, 0) for a in cam.freed)
        cam.put(res + 4, 1)
        cam.put(0xc3033a44, 2)
        cam.put(0xc3033a54, 1)
        lookup = t.HEAP + 0x210000
        cam.put(lookup + 4, 0xc09c3f34)
        cam.mu.reg_write(UC_ARM_REG_R5, 0)
        cam.mu.reg_write(UC_ARM_REG_R11, 0x24)
        cam.call(tone, lookup, r2=0, lr=tone + 4, sp=sp)
        assert cam.r(UC_ARM_REG_PC) == tone + 4
        assert cam.r(UC_ARM_REG_R1) == cam.w(res + 0x10) + 0x2000
        cam.call(0xc052b310, 0xc37830d0, sp=sp)
        pixels = t.HEAP + 0x200000
        for name, classification, limit in [(b'Indoor50', 1, 6967), (b'Indoor60', 2, 7315)]:
            cam.preset(name=name)
            cam.fixture(state=0, publish=False)
            result, _ = cam.call(getter, 0xc3202288, sp=sp)
            assert result == classification
            cam.mu.mem_write(pixels, bytes(1024 * 128))
            cam.put(0xc3202c9c, limit + 1)
            assert Prototype.draw_frame(cam, pixels, sp=sp, publish=False) == b'\0\0\0\1'
            assert bytes(cam.mu.mem_read(pixels + 64 * 1024 + 400, 192)) == bytes([3]) * 192
            cam.put(0xc3202c9c, limit)
            Prototype.draw_frame(cam, pixels, sp=sp, publish=False)
            assert bytes(cam.mu.mem_read(pixels + 64 * 1024 + 400, 192)) == bytes(192)

    def shut_down(cam):
        journal = cam.journal()
        assert {getter, tone}.issubset(a for a, _, _ in journal)
        cam.power_off_all()
        for a, n, stock in journal:
            assert bytes(cam.mu.mem_read(a, n)) == stock, hex(a)
        assert cam.w(save) == saved

    def warm_reset(cam):
        cam.registered.clear()
        cam.heap_next = t.HEAP
        cam.lv_tasks.clear()
        cam.written.pop(loader_log, None)
        cam.put(boot.TABLE + 0x21c, 0)

    for name in ('ordinary', 'ordinary-with-shell', 'fast', 'fast-with-shell'):
        path = cards / name
        ar = (path / 'AutoRun.txt').read_bytes()
        peer = next((p.name for p in (path / 'fpSup').glob('USB-Shell*.BIN')), None)
        cam = Camera(path)
        # An older card's saved loader has a different key; the new script must miss.
        cam.put(boot.STORE, 0x5c502aa9)
        cam.mu.mem_write(t.CAVE_LOW, bytes(0x200))
        assert not boot.run_autorun(cam, ar)[1], 'first boot must fall back'
        check_loaded(cam, peer)
        assert (cam.w(boot.STORE) != 0x5c502aa9) == name.startswith('fast')
        stored = bytes(cam.mu.mem_read(boot.STORE, 0x1d8))
        shut_down(cam)
        if name.startswith('fast'):
            cam = Camera(path)
            cam.mu.mem_write(boot.STORE, stored)
            cam.mu.mem_write(t.CAVE_LOW, bytes(0x200))
            assert boot.run_autorun(cam, ar)[1], 'stored-loader hit should abort fallback'
            check_loaded(cam, peer)
            assert bytes(cam.mu.mem_read(boot.STORE, len(stored))) == stored
            shut_down(cam)
            warm_reset(cam)
            stub = bl_target(boot.SITE, cam.w(boot.SITE))
            assert t.CAVE_LOW + 4 < stub < t.CAVE_LOW + 0x200
            cam.call(stub, r0=123, r1=456)
            check_loaded(cam, peer)
            assert bytes(cam.mu.mem_read(boot.STORE, len(stored))) == stored
            shut_down(cam)
        print(f'PASS {name}: loader paths, both modules, SupManager and shutdown')

    path = cards / 'ordinary'
    ar = (path / 'AutoRun.txt').read_bytes()
    base = Camera(path)
    original = base.w(tone)
    conflict = test_sup(boot.T4.cfg(claims=[(tone, original, 2, boot.T4.NOP)]), 'PEER')
    cam = Camera(path, extra=[('A-conflict.BIN', conflict)])
    boot.run_autorun(cam, ar)
    assert 'A-conflict.BIN' in cam.loaded() and INDOOR in cam.loaded()
    assert LV not in cam.loaded() and cam.w(tone) == boot.T4.NOP
    assert cam.w(0xc06c07d8) == 0xe3a02010 and not cam.lv_tasks
    assert any(c == boot.T4.CODES['CONFLICT'] and a == tone for c, a, _, _ in cam.loadlog())
    assert {a for a, _, _ in cam.journal()}.isdisjoint({0xc06c07d8})
    cam.power_off_all()
    assert cam.w(tone) == original
    cam = Camera(path, fail_lv=True)
    boot.run_autorun(cam, ar)
    assert INDOOR in cam.loaded() and LV not in cam.loaded()
    assert cam.w(tone) == original and not cam.lv_tasks
    print('PASS v4 declines a conflicting hook and releases failed installations')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, required=True)
    parser.add_argument('--cards', type=Path, required=True)
    args = parser.parse_args()
    verify(args.upstream.resolve(), args.cards.resolve())
