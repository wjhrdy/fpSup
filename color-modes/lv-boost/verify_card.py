"""Execute exact ordinary/Fast/merged cards; native I/O and scheduling are mocked."""
from pathlib import Path
import re
import struct
import sys

from test_lv_boost import B, T, STACK, TONE, SAVE, MAGIC
from read_diagnostics import resident
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_R5,
                               UC_ARM_REG_R11, UC_ARM_REG_LR)


class Card(T.Camera):
    def __init__(self, loader, binary):
        self.tasks, self.descriptors, self.freed = [], {}, []
        super().__init__(loader, binary)
        self.mu.mem_write(B.SEG1_BASE, B.SEG1.read_bytes())
        self.mu.mem_map(T.HEAP + T.HEAP_SIZE, 0x800000)

    def allocate(self, size):
        result = self.heap_next
        self.heap_next = (result + size + 0xFFF) & ~0xFFF
        assert self.heap_next < T.HEAP + T.HEAP_SIZE + 0x800000
        return result

    def _hook(self, mu, addr, size, data):
        if addr == self.entry:
            self.entry = None  # Execute every actual payload entry, including peers.
        if addr == T.F['H_GET']:
            assert self.r(UC_ARM_REG_R1) == 0, 'allocation must use USER memory'
            n = self.r(UC_ARM_REG_R2)
            self.descriptors[self.r(UC_ARM_REG_R0)] = (self.allocate(n), n)
            return self._ret(0)
        if addr == T.F['H_ADDR']:
            return self._ret(self.descriptors[self.r(UC_ARM_REG_R0)][0])
        if addr == T.F['H_FREE']:
            at, n = self.descriptors.pop(self.r(UC_ARM_REG_R0))
            self.freed.append((at, n))
            mu.mem_write(at, b'\xFF' * n)  # catch resident references into staging
            return self._ret(0)
        if addr == T.F['MEM_GET']:
            return self._ret(self.allocate(self.r(UC_ARM_REG_R1)))
        # OpenGate restore reads the native settings facade and recording format.
        # No native settings service/scheduler is running in this emulator.
        if addr == 0xC0057AE8:
            return self._ret(0xC31AC59C)
        if addr == 0xC005BE90:
            return self._ret(0)
        if addr == 0xC0016A58:
            assert self.r(UC_ARM_REG_SP) % 8 == 0
            self.tasks.append(struct.unpack('<8I', mu.mem_read(self.r(UC_ARM_REG_R0), 32)))
            return self._ret(len(self.tasks))
        if addr == 0xC0016BC0:
            assert self.r(UC_ARM_REG_SP) % 8 == 0
            assert 1 <= self.r(UC_ARM_REG_R0) <= len(self.tasks)
            assert self.r(UC_ARM_REG_R1) == 0
            return self._ret(0)
        return super()._hook(mu, addr, size, data)


def verify(path):
    pairs = [(int(a, 16), int(w, 16)) for a, w in re.findall(
        r'^mem set (0x\w+) (0x\w+)', (path / 'AutoRun.txt').read_text(), re.M)]
    loader = {a: w for a, w in pairs if T.CAVE_LOW <= a < T.CAVE_LOW + 0x200}
    bootstrap = {a: w for a, w in pairs if 0xC072F700 <= a < 0xC0730000}
    c = Card(loader, (path / 'fpSup.BIN').read_bytes())
    c.mu.mem_write(SAVE, struct.pack('<I', MAGIC | 6))
    c.now = 15_000_000
    modes = ('ordinary loader', 'stored bootstrap', 'warm hook') if bootstrap else ('ordinary loader', 'ordinary reload')
    for mode in modes:
        c.tasks.clear()
        c.registered.clear()
        c.descriptors.clear()
        c.freed.clear()
        c.heap_next = T.HEAP + 0x20000
        # Warm boot clears BSS/heap, retaining firmware image/cave and saved settings.
        common = bytes(c.mu.mem_read(0xC307523C, 0x300))
        c.mu.mem_write(0xC3000000, bytes(0x1000000))
        c.mu.mem_write(0xC307523C, common)
        c.mu.mem_write(T.HEAP, bytes(T.HEAP_SIZE + 0x800000))
        if mode == 'stored bootstrap':
            for a, w in bootstrap.items():
                c.mu.mem_write(a, struct.pack('<I', w))
            entry = 0xC072F700
        else:
            entry = T.CAVE_LOW + (4 if mode == 'warm hook' else 0)
        stock = [(a, bytes(c.mu.mem_read(a, n))) for a, n in c.sections()
                 if a >= 0x40000000 and not T.CAVE_LO <= a < T.CAVE_HI]
        c.call(entry, r0=0xC0BABDD8, r1=1, sp=STACK)
        assert c.r(UC_ARM_REG_PC) == T.DONE, 'loader did not return'
        assert c.r(UC_ARM_REG_SP) == STACK
        assert c.ar_started is None
        assert c.word(0xC06C07D8) == 0xE3A02011
        assert c.word(TONE) != 0xE5901004
        lv_tasks = [t for t in c.tasks if t[5] == 0x4F544146]
        assert len(lv_tasks) == 1, 'LV Boost startup task missing or duplicated'
        assert lv_tasks[0][3:5] == (28, 0x2000)
        res = resident([c.word(0xC06C07CC), c.word(0xC06C07D0)])
        assert res <= lv_tasks[0][2] < res + 0x2600
        assert all(not at <= lv_tasks[0][2] < at + n for at, n in c.freed)
        assert c.freed, 'loader must free staging'
        assert len(c.registered) == 2
        if bootstrap:
            assert c.word(T.STORE) != 0
        assert c.word(SAVE) == MAGIC | 6
        assert c.word(res + 0x1A4) == 2
        assert 0xC072E064 <= c.word(0xC072E060) <= 0xC072EFB4
        # Run the real resident tone hook AFTER staging was freed and poisoned.
        c.mu.mem_write(res + 4, struct.pack('<I', 1))
        c.mu.mem_write(0xC3033A44, struct.pack('<I', 2))
        c.mu.mem_write(0xC3033A54, struct.pack('<I', 1))
        lookup = T.HEAP + 0x100
        c.mu.mem_write(lookup + 4, struct.pack('<I', 0xC09C3F34))
        for reg, value in ((UC_ARM_REG_R0, lookup), (UC_ARM_REG_R2, 0),
                           (UC_ARM_REG_R5, 0), (UC_ARM_REG_R11, 0x24),
                           (UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, T.DONE)):
            c.mu.reg_write(reg, value)
        c.mu.emu_start(TONE, TONE + 4, count=10000)
        assert c.r(UC_ARM_REG_PC) == TONE + 4
        assert c.r(UC_ARM_REG_R1) == c.word(res + 0x10) + 0x2000
        obj = c.registered[0][0]
        c.call(c.word(obj + 4), r0=obj, r1=4, sp=STACK)
        for a, word, _ in B.hook_sites(True):
            assert bytes(c.mu.mem_read(a, 4)) == word, hex(a)
        for a, data in stock:
            assert bytes(c.mu.mem_read(a, len(data))) == data, f'journal failed at {a:#x}'
        assert c.word(T.DRAW) == T.DRAW_STOCK
        assert c.word(SAVE) == MAGIC | 6
        print(f'{path.name} / {mode}: payload entries returned, LV Boost task resident, hooks restored')


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        verify(Path(arg))
