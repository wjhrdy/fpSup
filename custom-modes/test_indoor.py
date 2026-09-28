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
import unittest

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

class FamilyTests(unittest.TestCase):
    def test_family_curves_and_native_interpolation(self):
        import math
        import json
        with tempfile.TemporaryDirectory() as tmp:
            for hz, base in ((120, 7073),):
                out, manifest = build(Path(tmp)/str(hz))
                c = IndoorCamera(out) if hz == 120 else Prototype(out)
                c.boot()
                if hz == 120:
                    c.preset()
                # Manual family never installs the two hooks implicated in Auto testing.
                self.assertEqual(c.word(DRAW_SITE), 0xe1a03000)
                self.assertEqual(c.word(RESULT_SITE), 0xeb000173)
                c.mu.mem_write(HEAP, bytes(0x20000))  # no staging dependency
                cycles = [1]+[n for k in range(1, 12 if hz == 120 else 11) for n in (2**k, 3*2**(k-1))]
                allowed = {base-round(1024*math.log2(n)) for n in cycles}
                models = [(1, 0xc091388c+i*64) for i in range(5)]
                models += [(0, 0xc0913a0c+i*64) for i in range(7)]
                for path, model in models:
                    for autoiso in (False, True):
                        c.fixture(path=path, model_at=model, autoiso=autoiso)
                        low = max(-5025, struct.unpack('<i', c.mu.mem_read(MODEL+4,4))[0])
                        sentinel = bytes([0xa5])*32
                        c.mu.mem_write(TABLE+0xaf0, sentinel)
                        self.assertEqual(c.invoke(capture=False), 0)
                        points = []
                        for i in range(100):
                            p = struct.unpack('<7i', c.mu.mem_read(TABLE+i*28,28))
                            if p[1] == p[3] == 0:
                                break
                            points.append(p)
                        self.assertLess(len(points), 100)
                        self.assertEqual(bytes(c.mu.mem_read(TABLE+0xaf0,32)), sentinel)
                        self.assertGreater(len({p[2] for p in points}), 1)
                        for p in points:
                            self.assertIn(p[2], allowed)
                            self.assertGreaterEqual(p[2], low)
                            self.assertEqual(p[0], p[1]+p[2]+p[4]-p[3])
                            self.assertTrue(3072 <= p[1] <= 9216)
                            self.assertTrue(5120 <= p[3] <= (15360 if autoiso else 5120))
                        # Sample both sides of EVERY step as well as a brightness sweep.
                        bvs = set(range(points[-1][0],points[0][0]+1,157))
                        for a,b in zip(points,points[1:]):
                            self.assertGreaterEqual(a[0], b[0])
                            if a[2] != b[2]:
                                self.assertEqual(a[0], b[0])
                                bvs.update((a[0]-1,a[0],a[0]+1))
                        for bv in sorted(bvs, reverse=True):
                            c.mu.reg_write(UC_ARM_REG_R2,TUPLE)
                            c.call(0xc0226508,bv,TABLE,sp=STACK-0x2000)
                            self.assertEqual(c.r(UC_ARM_REG_PC),DONE)
                            p = struct.unpack('<7i',c.mu.mem_read(TUPLE,28))
                            self.assertIn(p[2],allowed)
                            self.assertLessEqual(abs(bv-(p[1]+p[2]+p[4]-p[3])),1)
                        # The native range reporter includes the newly extended slow end.
                        self.assertEqual(struct.unpack('<i',c.mu.mem_read(RANGES,4))[0],
                                         min(p[2] for p in points))
                # Native APEX conversion stays within integer quantization of n mains cycles.
                c.mu.reg_write(UC_ARM_REG_C1_C0_2, 0xf00000)
                c.mu.reg_write(UC_ARM_REG_FPEXC, 0x40000000)
                for n in cycles:
                    tv = base-round(1024*math.log2(n))
                    us, _ = c.call(0xc021ad00,tv,sp=STACK-0x2000)
                    self.assertLess(abs(us/(1_000_000*n/hz)-1),0.001)
                # Mutation: removing the extension must fail the multi-exposure check.
                syms = manifest['symbols']
                at = RES+syms['extend_family']-syms['resident']
                c.put(at, 0xe12fff1e)  # bx lr
                c.mu.ctl_remove_cache(at,at+4)
                c.fixture()
                c.invoke(capture=False)
                with self.assertRaises(AssertionError):
                    self.assertLess(struct.unpack('<i',c.mu.mem_read(RANGES,4))[0],base)

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


class IndoorTests(unittest.TestCase):
    def test_saved_slot_switch_and_native_family(self):
        from test_loader_hook import AR_RET, AR_TABLE
        with tempfile.TemporaryDirectory() as tmp:
            for fast in (False, True):
                out, manifest = build(Path(tmp)/str(fast), fast_start2=fast)
                for warm in ((False, True) if fast else (False,)):
                    c = IndoorCamera(out)
                    if warm:
                        c.put(AR_TABLE+0x21c, 0)
                        c.call(CAVE_LOW+4, 0xc0babdd8, 1, lr=AR_RET)
                    else:
                        c.boot()
                    self.assertEqual(c.entries, 1)
                    c.mu.mem_write(HEAP, bytes(0x20000))
                    for bank in (0, 1):
                        for second in (False, True):
                            for dial in range(10):
                                c.preset(dial, bank=bank, second_dial=second)
                                c.fixture(state=0)
                                c.invoke()
                                self.assertEqual(c.word(LIMITS), 7073 if dial >= 4 else 0x80000000)
                    # Same running hook, no detector events or restart between changes.
                    for name, enabled in ((b'Indoor', True), (b'Outdoor', False),
                                          (b'INDOOR', True), (b'IndoorX', False),
                                          (b'indoor', True), (b'', False)):
                        c.preset(name=name)
                        c.fixture(state=0, publish=False)
                        c.invoke()
                        self.assertEqual(c.word(LIMITS), 7073 if enabled else 0x80000000)
                    # Native P curve and native interpolation still come from 0.4.
                    for autoiso in (False, True):
                        c.preset()
                        c.fixture(autoiso=autoiso)
                        self.assertEqual(c.invoke(capture=False), 0)
                        self.assertLess(struct.unpack('<i', c.mu.mem_read(RANGES,4))[0], 7073)
                        self.assertEqual(c.word(RANGES+4), 7073)
                    for options in ({'mode':1}, {'mode':3}, {'mode':4}, {'cine':1}, {'shift':1}, {'path':2}):
                        c.fixture(**options)
                        before = bytes(c.mu.mem_read(LIMITS,0xcc))
                        c.invoke()
                        self.assertEqual(bytes(c.mu.mem_read(LIMITS,0xcc)), before)
                    c.put(0xc31caa80, 0)
                    c.fixture()
                    c.invoke()
                    self.assertEqual(c.word(LIMITS), 0x80000000)
                    # Mutation: bypassing the name gate makes the off check fail.
                    syms = manifest['symbols']
                    gate = RES+syms['indoor_selected']-syms['resident']
                    c.put(gate, 0xe3a00001, 0xe12fff1e)
                    c.mu.ctl_remove_cache(gate, gate+8)
                    c.preset(dial=3)
                    c.fixture()
                    c.invoke()
                    with self.assertRaises(AssertionError):
                        self.assertEqual(c.word(LIMITS), 0x80000000)
                    obj = c.registered[0][0]
                    c.call(c.word(obj+4), obj, 4)
                    for site in (SITE, DRAW_SITE, SCAN_SITE, RESULT_SITE, 0xc0226508):
                        self.assertEqual(bytes(c.mu.mem_read(site,4)), c.stock[site-0xc0000000:site-0xc0000000+4])




class MergeTests(unittest.TestCase):
    def test_actual_merge_outputs(self):
        import subprocess
        from build_indoor import HERE
        from test_loader_hook import AR_RET, AR_TABLE
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            card, _ = build(tmp/'input')
            subprocess.run(['node', str(HERE/'test_merge.js'), str(card/'fpSup.BIN'),
                            str(tmp/'merged')], check=True)
            for fast, warm in ((False, False), (True, False), (True, True)):
                out = tmp/'merged'/('indoor-fast' if fast else 'indoor-ordinary')
                c = IndoorCamera(out)
                if warm:
                    c.put(AR_TABLE+0x21c, 0)
                    c.call(CAVE_LOW+4, 0xc0babdd8, 1, lr=AR_RET)
                else:
                    c.boot()
                self.assertEqual(c.entries, 1)
                c.preset()
                c.fixture()
                self.assertEqual(c.invoke(capture=False), 0)
                self.assertEqual(c.word(RANGES+4), 7073)
                c.preset(dial=3)
                c.fixture()
                c.invoke()
                self.assertEqual(c.word(LIMITS), 0x80000000)
                obj = c.registered[0][0]
                c.call(c.word(obj+4), obj, 4)
                for site in (SITE, DRAW_SITE, SCAN_SITE, RESULT_SITE, 0xc0226508):
                    self.assertEqual(bytes(c.mu.mem_read(site,4)), c.stock[site-0xc0000000:site-0xc0000000+4])

if __name__ == '__main__':
    unittest.main(verbosity=2)
