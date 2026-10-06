#!/usr/bin/env python3
"""Actual new payload + native getter/model/curve under Unicorn; no camera."""
import json
from pathlib import Path
import sys
import tempfile

from build_indoor import build, ROOT, REPO, GETTER, STOCK
import subprocess
from indoor_fixture import IndoorCamera, Prototype, RES, LIMITS, MODEL, TABLE, RANGES, TUPLE, DRAW_SITE
from test_loader_hook import HEAP, STACK, DONE, CAVE_LOW, AR_RET, AR_TABLE
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.arm_const import *


class TestCamera(IndoorCamera):
    def __init__(self, out):
        super().__init__(out)
        self.observe = False
        self.changes = []
        self.mu.hook_add(UC_HOOK_MEM_WRITE, self.track)

    def track(self, mu, access, addr, size, value, data):
        if self.observe and not STACK-0x10000 <= addr < STACK:
            self.changes.append((addr, size, value))

    def _hook(self, mu, addr, size, data):
        if addr in (0xc00b4be8, 0xc00b7eb0):
            assert self.r(UC_ARM_REG_SP)%8 == 0
        return super()._hook(mu, addr, size, data)

    def getter(self):
        saved = list(range(0xabc004,0xabc00c))
        for i,v in enumerate(saved): self.mu.reg_write(UC_ARM_REG_R4+i,v)
        self.changes.clear(); self.observe=True
        ret,sp=self.call(GETTER,0xc3202288,sp=STACK-0x2004)
        self.observe=False
        assert sp==STACK-0x2004 and self.r(UC_ARM_REG_PC)==DONE
        assert [self.r(UC_ARM_REG_R4+i) for i in range(8)] == saved
        # Stock property getters update their guard/cache metadata in context.
        # No detector/override or saved settings-bank stores are allowed.
        assert {a for a,_,_ in self.changes} <= {0xc31adf6d,0xc31adf79,0xc31adf7a} | set(range(RES,RES+0x1000)), self.changes
        return ret


def verify(out, fast=False, warm=False):
    c=TestCamera(out)
    if warm:
        c.put(AR_TABLE+0x21c,0)
        c.call(CAVE_LOW+4,0xc0babdd8,1,lr=AR_RET)
        assert c.entries==1
    else:c.boot()
    c.mu.mem_write(HEAP,bytes(0x20000))  # staging freed; resident still works
    assert c.word(GETTER)!=0xe92d4010
    for site,word in STOCK.items():
        if site==DRAW_SITE:assert c.word(site)!=word
        else:assert c.word(site)==word
    for name,hz in ((b'Indoor',2),(b'Indoor60',2),(b'Indoor50',1)):
        for bank in (0,1):
            for second in (False,True):
                for dial in range(10):
                    c.preset(dial,name=name,bank=bank,second_dial=second)
                    c.fixture(state=0,publish=False)
                    assert c.getter()==(hz if dial>=4 else 0)
        for opts in ({'mode':1},{'mode':3},{'mode':4},{'cine':1},{'shift':1}):
            c.preset(name=name);c.fixture(state=0,publish=False,**opts);assert c.getter()==0
    for name,hz in ((b'Indoor',2),(b'INDOOR',2),(b'indoor',2),
                    (b'INDOOR60',2),(b'InDoOr50',1),(b'indoor50',1),
                    (b'Outdoor',0),(b'IndoorX',0),(b'',0),(b'Indoor5',0),
                    (b'Indoor6',0),(b'Indoor50X',0),(b'Indoor60 ',0),
                    (b'Indoor 50',0),(b'Indoor500',0),(b'Indoor00',0)):
        c.preset(name=name);c.fixture(state=0,publish=False)
        assert c.getter()==hz,name
    c.fixture(state=0,publish=False);c.put(0xc31caa80,0);assert c.getter()==0
    # Leaving Indoor respects pre-existing native override as well as cached result.
    c.preset(name=b'Outdoor');c.put(0xc32006fc,1,1);assert c.getter()==1
    c.preset();assert c.getter()==2
    c.preset(name=b'Outdoor');assert c.getter()==1

    c.call(0xc052b310,0xc37830d0,sp=STACK-0x2000)
    c.put(0xc3033a44,2);c.put(0xc3033a54,1)
    c.put(0xc3202ab4,0xc0915cdc)
    ctx=HEAP+0x190000
    for autoiso in (True,False):
        for name,hz in ((b'Outdoor',0),(b'Indoor',2),(b'Indoor60',2),(b'Indoor50',1)):
            c.preset(name=name)
            c.fixture(state=0,publish=False,autoiso=autoiso)
            c.put(0xc3202cc0,0 if autoiso else 400)
            c.mu.mem_write(ctx,bytes(236));c.put(ctx+0x24,2)
            model,sp=c.call(0xc0220300,ctx,LIMITS,sp=STACK-0x2000)
            assert c.word(model)==({0:0x65,1:0x6b,2:0x6c} if autoiso else {0:0x65,1:0x79,2:0x7a})[hz]
            c.mu.mem_write(MODEL,bytes(c.mu.mem_read(model,64)));c.put(MODEL+0x18,0,18)
            c.mu.reg_write(UC_ARM_REG_R2,RANGES)
            ret,sp=c.call(0xc0224e70,LIMITS,TABLE,sp=STACK-0x2000)
            assert ret==0 and sp==STACK-0x2000
            assert c.word(LIMITS)==0x80000000 and c.word(LIMITS+0x8c)==0
            c.mu.reg_write(UC_ARM_REG_R2,TUPLE)
            c.call(0xc0226508,16000,TABLE,sp=STACK-0x2000)
            assert c.word(TUPLE+8)>7073  # bright native shutter freedom retained
            if hz:
                # Native bright-scene exposure after aperture/ISO constraints:
                # a controlled lens must warn too, using the native selected Tv.
                c.put(0xc347b1d4,1);c.put(0xc3202c9c,c.word(TUPLE+8))
                assert Prototype.draw_frame(c,HEAP+0x200000,publish=False)==bytes((0,1,0,0))
                assert bytes(c.mu.mem_read(HEAP+0x200000+64*1024+400,192))==bytes([3])*192
                c.put(0xc3202c9c,6967 if hz==1 else 7315)
                assert Prototype.draw_frame(c,HEAP+0x200000,publish=False)==bytes((0,1,0,0))
    # Execute the stock UI rational formatter, including both rounding edges.
    c.put(0xc320284c,0xc0913078)  # stock singleton initial value; OS guard mocked
    rational=HEAP+0x1b0000
    for tv,denominator in ((7073,125),(7133,125),(7168,125),(7315,125),
                           (7316,160),(6803,100),(6967,100),(6968,125)):
        c.call(0xc0228d48,rational,tv,sp=STACK-0x2000)
        assert (c.word(rational),c.word(rational+4))==(1,denominator)
    for name,threshold in ((b'Indoor',7315),(b'Indoor60',7315),(b'Indoor50',6967)):
        verify_warning(c,name,threshold)
    obj=c.registered[0][0];c.call(c.word(obj+4),obj,4)
    for site,word in {**STOCK,GETTER:0xe92d4010}.items():assert c.word(site)==word
    c.preset();c.fixture(state=1,publish=False);assert c.getter()==1
    print('PASS',out,'warm',warm)


def verify_warning(c,name,threshold):
    # Real font and ARM draw hook; run after staging was freed.
    c.call(0xc052b310,0xc37830d0,sp=STACK-0x2000)
    c.preset(name=name);c.fixture(state=0,publish=False);assert c.getter()==(1 if threshold==6967 else 2)
    c.put(0xc3033a44,2);c.put(0xc3033a54,1)
    frames=[HEAP+0x200000+i*0x20000 for i in range(3)]
    expected=bytearray([7])*(1024*128)
    for y in range(64,96):expected[y*1024+400:y*1024+592]=bytes(192)
    # Native bitmap is inverted: all-one blank rows are background.
    blank=c.mu.mem_read(0xc2f24558,64)
    assert bytes(blank)==bytes([255])*64
    for i,ch in enumerate(b'BANDING RISK'):
        glyph=c.mu.mem_read(0xc2f24558+(ch-32)*64,64)
        for y in range(32):
            for x in range(16):
                expected[(64+y)*1024+400+i*16+x]=3 if glyph[y*2+x//8] & (128>>(x%8)) else 1
    draw=lambda pixels,**kw: Prototype.draw_frame(c,pixels,publish=False,**kw)
    # The STILL label uses its own tuple, independently of the other AE tuple.
    c.put(0xc3202c78,8192);c.put(0xc3202c9c,threshold)
    assert draw(frames[0])==bytes(4), 'Warning followed non-display AE tuple'
    c.put(0xc3202c78,6803);c.put(0xc3202c9c,8192)
    assert draw(frames[0])==b'\0\1\0\0'
    c.put(0xc3202c9c,threshold)
    assert draw(frames[0])==b'\0\1\0\0'

    for tv,selector,risk in ((7073 if threshold==7315 else 6803,0,False),
                             (7133 if threshold==7315 else 6803,1,False),
                             (7168 if threshold==7315 else 6803,2,False),(threshold,0,False),(threshold-1024,0,False),(threshold+1,0,True),
                             (8192,0,True),(8192,1,True),(8192,2,True),(threshold,1,False),(threshold,2,False)):
        c.put(0xc347b1d4,selector);c.put(0xc3202c9c,tv)
        for pixels in frames:
            c.mu.mem_write(pixels,bytes([7])*(1024*128))
            assert draw(pixels)==(b'\0\1\0\0' if risk else bytes(4))
            assert bytes(c.mu.mem_read(pixels,1024*128))==(expected if risk else bytes([7])*(1024*128))
        if risk:
            c.put(0xc3202c9c,threshold)
            for pixels in reversed(frames):
                assert draw(pixels)==b'\0\1\0\0'
                for y in range(64,96):assert bytes(c.mu.mem_read(pixels+y*1024+400,192))==bytes(192)
                assert draw(pixels)==bytes(4)
    c.put(0xc347b1d4,0);c.put(0xc3202c9c,8192)
    for kw in ({'mode':3},{'cine':1},{'group':0},{'fmt':4},{'width':591},{'height':95}):
        assert draw(frames[0],**kw)==bytes(4),kw
    c.fixture(state=0,publish=False);c.put(0xc3202d00,1)
    assert draw(frames[0])==bytes(4)
    c.put(0xc3202d00,0)
    # Leaving the dial must clear without waiting for another flicker getter.
    c.preset(dial=3);assert draw(frames[0])==bytes(4)
    c.getter();assert draw(frames[0])==bytes(4)
    c.preset(name=name);c.getter();assert draw(frames[0])==b'\0\1\0\0'
    c.preset(name=b'Outdoor');assert draw(frames[0])==b'\0\1\0\0'
    c.getter();assert draw(frames[0])==bytes(4)
    c.preset(name=name);c.getter();
    for addr,value in ((0xc3033a44,5),(0xc3033a54,2)):
        c.put(addr,value);assert draw(frames[0])==bytes(4)
        c.put(0xc3033a44,2);c.put(0xc3033a54,1)
    c.put(0xc3202c9c,7000)
    for selected,risk in ((b'Indoor60',False),(b'Indoor50',True),(b'Indoor60',False)):
        c.preset(name=selected)
        # No stale warning may be drawn before the native getter refreshes.
        draw(frames[0])
        c.getter();draw(frames[0])
        assert bytes(c.mu.mem_read(frames[0]+64*1024+400,192))==(bytes([3])*192 if risk else bytes(192))
    print('PASS native pixels, manual/controlled aperture, threshold, 3-buffer clearing, mode/dial gates, registers/flags')


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        ordinary,_=build(tmp/'ordinary')
        fast,m=build(tmp/'fast',fast=True)
        for out,warm in ((ordinary,False),(fast,False),(fast,True)):verify(out,out==fast,warm)
        c=TestCamera(ordinary);c.fail_alloc=True;c.boot()
        assert c.word(GETTER)==0xe92d4010 and c.word(DRAW_SITE)==0xe1a03000, 'Failed allocation armed a hook'
        c=TestCamera(ordinary);c.boot();c.preset(name=b'Outdoor');c.fixture(state=0,publish=False)
        gate=RES+m['symbols']['indoor_selected']-m['symbols']['resident']
        c.put(gate,0xe3a00001,0xe12fff1e);c.mu.ctl_remove_cache(gate,gate+8)
        assert c.getter()!=0, 'Name-gate mutation not caught'
        merged=tmp/'merged'
        subprocess.run(['node',str(REPO/'custom-modes/test_merge.js'),
                        str(ordinary/'fpSup.BIN'),str(merged)],check=True)
        verify(merged/'indoor-ordinary')
        verify(merged/'indoor-fast',fast=True)
        verify(merged/'indoor-fast',fast=True,warm=True)
        print('PASS gates, native exposure selection, no detector/override/settings-bank writes, ordinary/Fast/warm restore, mutation')


if __name__=='__main__':main()
