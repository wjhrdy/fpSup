#!/usr/bin/env python3
"""Run the actual loader, entry and ARM hook against fp 5.02 in Unicorn.

Only OS/file/heap/cache and singleton-initialization guards are mocked.
Policy checks intercept the builder to inspect its arguments; integration
checks run that native builder and its native table interpolator.
"""
from pathlib import Path
import re
import struct
import tempfile

from build_indoor import ROOT, SITE, DRAW_SITE, SCAN_SITE, RESULT_SITE, build
from test_loader_hook import Camera, CAVE_LOW, HEAP, STACK, DONE, F
from unicorn.arm_const import *

SECONDS = 0xc30781a4
RES = HEAP + 0x100000
LIMITS, MODEL, IRIS, TABLE, RANGES, TUPLE = [HEAP + n for n in
                                          (0x180000, 0x181000, 0x182000, 0x183000, 0x184000, 0x185000)]


class Prototype(Camera):
    def __init__(self, out):
        sets = re.findall(r'^mem set (0x[\da-fA-F]+) (0x[\da-fA-F]+)',
                          (out / 'AutoRun.txt').read_text(), re.M)
        loader = {int(a, 16): int(v, 16) for a, v in sets
                  if CAVE_LOW <= int(a, 16) < CAVE_LOW + 0x200}
        self.allocs = self.entries = 0
        self.capture = False
        self.fail_alloc = False
        self.seen = None
        self.executed = set()
        super().__init__(loader, (out / 'fpSup.BIN').read_bytes())
        self.mu.mem_write(0xc2ef6e00, (ROOT / 'out/seg1_c2ef6e00.bin').read_bytes())

    def call(self, *args, **kwargs):
        # Supply the firmware's native seconds counter independently of its API stub.
        self.put(SECONDS, self.now // 1_000_000)
        return super().call(*args, **kwargs)

    def put(self, at, *values):
        self.mu.mem_write(at, struct.pack('<' + 'I'*len(values), *[v & 0xffffffff for v in values]))

    def _hook(self, mu, addr, size, data):
        self.executed.add(addr)
        if addr == self.entry:
            self.entries += 1
            self.entry = None  # Run the real payload; Camera otherwise skips it.
        if addr == F['H_ADDR']:
            self.allocs += 1
            return self._ret(HEAP if self.allocs == 1 else (0 if self.fail_alloc else RES))
        if addr in (F['DCACHE'], F['ICACHE'], F['H_GET'], F['H_ADDR']):
            assert self.r(UC_ARM_REG_SP) % 8 == 0, hex(addr)
        if addr == 0xc0013090:  # objects already initialized in the AE task
            return self._ret(0)
        if addr == 0xc036d758:  # OS event-flag notification; real detector-result wrapper runs
            return self._ret(1)
        if addr == 0xc0011100:
            raise AssertionError('Native firmware assertion')
        if addr in (0xc0208610, 0xc0224e70, 0xc0224d08, 0xc0220740, 0xc0529cb8):
            if RES <= self.r(UC_ARM_REG_LR) < RES+0x1000:
                assert self.r(UC_ARM_REG_SP) % 8 == 0, hex(addr)
        if addr == 0xc0224e70 and self.capture:
            assert self.r(UC_ARM_REG_SP) % 8 == 0
            self.seen = (self.r(UC_ARM_REG_R0), self.r(UC_ARM_REG_R1), self.r(UC_ARM_REG_R2))
            return self._ret(0x123)
        return super()._hook(mu, addr, size, data)

    def boot(self):
        result, sp = self.call(CAVE_LOW, sp=STACK-0x1000)
        assert self.r(UC_ARM_REG_PC) == DONE, 'Loader failed to return'
        assert result == 1 and sp == STACK-0x1000 and self.entries == 1

    def fixture(self, state=1, mode=2, cine=0, shift=0, path=1, autoiso=True, model_at=None, publish=True):
        # Synthetic f/2.8..f/22 lens, but REAL stock program model and functions.
        self.mu.mem_write(LIMITS, bytes(0xcc))
        model_at = model_at or (0xc091388c if path == 1 else 0xc0913a0c)
        self.mu.mem_write(MODEL, bytes(self.mu.mem_read(model_at, 64)))
        self.put(0xc3202cf0, cine)
        self.put(0xc3202cb4, mode)
        self.put(0xc3202d00, shift)
        self.put(0xc320228c, state)
        self.put(0xc32006fc, 0, 0)
        self.put(LIMITS, 0x80000000)
        self.put(LIMITS+8, mode)
        self.put(LIMITS+0x10, 0x10)  # c022a5f8: ordinary, non-flash program
        self.put(LIMITS+0x64, IRIS, 0, 18)
        self.put(LIMITS+0x70, path)
        self.put(LIMITS+0x7c, MODEL)
        self.put(LIMITS+0x90, 0x80000000)
        self.put(LIMITS+0x9c, 0x80000003, 0x7fffffff)
        count = self.word(self.word(MODEL+0x2c)+4)
        self.put(LIMITS+0xa4, count-1)
        self.put(LIMITS+0xa8, 0x80000000, -5025, 13277, 5120,
                 15360 if autoiso else 5120, 0, 18)
        for i in range(51):
            self.put(IRIS+i*8, i, 3072+round(i*1024/3))
        self.put(MODEL+0x18, 0, 18)
        if publish:
            self.complete_detection(state)

    def complete_detection(self, state):
        self.put(0xc320228c, state)
        value, sp = self.call(RESULT_SITE, 0xc3202288, lr=RESULT_SITE+4, sp=STACK-0x1804)
        assert self.r(UC_ARM_REG_PC) == RESULT_SITE+4 and sp == STACK-0x1804
        assert value == 1  # native notification result retained

    def invoke(self, pc=SITE, capture=True, sp=STACK-0x2004):
        self.capture = capture
        self.mu.reg_write(UC_ARM_REG_R2, RANGES)
        saved = list(range(0xabc004, 0xabc00c))
        for i, v in enumerate(saved):
            self.mu.reg_write(UC_ARM_REG_R4+i, v)
        # Run the patched BL but stop at its original continuation.
        ret = SITE+4 if pc == SITE else DONE
        result, endsp = self.call(pc, LIMITS, TABLE, lr=ret, sp=sp)
        assert self.r(UC_ARM_REG_PC) == ret, f'Execution did not return: {self.r(UC_ARM_REG_PC):#x}'
        assert endsp == sp
        assert [self.r(UC_ARM_REG_R4+i) for i in range(8)] == saved
        return result

    def draw_frame(self, pixels, state=2, mode=2, cine=0, group=3,
                   fmt=3, width=1024, height=128, sp=STACK-0x3004, publish=True):
        desc, dims = HEAP+0x1a0000, HEAP+0x1a0010
        self.put(desc, fmt, pixels, dims)
        self.put(dims, width, height)
        self.put(0xc320228c, state)
        self.put(0xc3202cb4, mode)
        self.put(0xc3202cf0, cine)
        if publish:
            self.complete_detection(state)
        self.put(sp+0x18, 0)
        self.put(sp+0x1c, 1 << (8*group))
        self.put(sp+0x20, desc)
        self.mu.reg_write(UC_ARM_REG_R5, group)
        self.call(0xc052884c, desc, lr=0xc0528850, sp=sp)
        for i in range(13):
            self.mu.reg_write(UC_ARM_REG_R0+i, 0xabc000+i)
        self.mu.reg_write(UC_ARM_REG_R5, group)
        flags = self.r(UC_ARM_REG_CPSR) | 0xa0000000
        self.mu.reg_write(UC_ARM_REG_CPSR, flags)
        _, endsp = self.call(DRAW_SITE, desc, 0xabc001, lr=DRAW_SITE+4, sp=sp)
        assert self.r(UC_ARM_REG_PC) == DRAW_SITE+4 and endsp == sp
        want = [0xabc000+i for i in range(13)]
        want[0] = desc
        want[5] = group+1  # stock displaced add r5,r5,#1
        assert [self.r(UC_ARM_REG_R0+i) for i in range(13)] == want
        assert self.r(UC_ARM_REG_CPSR) & 0xf8000000 == flags & 0xf8000000
        return bytes(self.mu.mem_read(sp+0x18, 4))

class IndoorCamera(Prototype):
    def _hook(self, mu, addr, size, data):
        if addr in (0xc0010298, 0xc00102d0):  # OS scoped lock only
            return self._ret(0)
        return super()._hook(mu, addr, size, data)

    def preset(self, dial=4, name=b'Indoor', bank=0, second_dial=False):
        # Synthetic initialized settings; REAL property/bank/name accessors run.
        context, obj = 0xc31ac59c, 0xc31ae3b0
        self.put(0xc31caa80, context)
        self.put(context+4, 0xc07397d8)
        item = context+0x19cc
        self.mu.mem_write(item, bytes(24))
        self.put(item, 0x123)
        self.put(item+12, 0xc073ab60)
        self.mu.mem_write(obj+0xb19c, bytes([bank]))
        self.put(obj+0x11e00, int(second_dial))
        base = obj+(0x58d4 if bank else 12)
        self.mu.mem_write(base+0x2395, b'\0')
        self.put(base, 0)
        self.put(base+0x2a0c, 0)
        self.put(base+(0x2a0c if second_dial else 0), dial)
        for slot in range(6):
            text = name if slot == dial-4 else b'Other'
            self.mu.mem_write(base+0x4ddb+36*slot, text.ljust(17, b'\0'))
        return base
