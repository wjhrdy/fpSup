"""Run the actual shared loader, trial installer and hook ABI boundaries offline."""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
from types import SimpleNamespace
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import *

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'fp_usb_shell'))
from test_loader_hook import Camera, CAVE_LOW, HEAP, STACK, DONE, F
from fixtures import descriptor, picture_descriptor, scene, frame_scene
from armasm import assemble, symbols


class TrialCamera(Camera):
    def __init__(self, directory, fail=False, card=None):
        self.manifest=json.loads((directory/'manifest.json').read_text())
        package=card or directory
        text=(package/'AutoRun.txt').read_text()
        loader={int(a,16):int(v,16) for a,v in re.findall(
            r'^mem set (0x[0-9a-fA-F]+) (0x[0-9a-fA-F]+)',text,re.M)
            if CAVE_LOW<=int(a,16)<CAVE_LOW+0x200}
        self.running_sup=False; self.fail=fail; self.stop_at=None; self.vectors=[]
        self.af=0; self.picture_seen=[]
        self.visibility_props=None
        self.controls_probe=False;self.controls_dirty=[]
        self.controls_native_reset=None
        self.transition_probe=False;self.lock_depth=0;self.transition_order=[]
        self.card_offsets=None;self.worker_at=None;self.module_at=None;self.worker_calls=0
        self.resident=HEAP+0x10000
        blob=(package/'fpSup.BIN').read_bytes()
        if card:
            # The shared trampoline must retain worker -> focus installer.
            count,entry=struct.unpack_from('<2I',blob,4)
            offset=16+8*count;records=[]
            for i in range(count):
                addr,size=struct.unpack_from('<2I',blob,16+8*i)
                records.append((addr,offset,blob[offset:offset+size]))
                offset+=size+(-size%4)
            shell=ROOT/'fp_usb_shell';worker=assemble(shell/'camera/worker.S')
            module=(directory/'inset-trial.arm').read_bytes()
            def location(data):
                matches=[o for a,o,d in records if a==0 and d==data]
                assert len(matches)==1;return matches[0]
            w=location(worker)+symbols(shell/'camera/worker.S')['spawn']
            m=location(module)
            trampoline=next(d for a,o,d in records if a==0 and o==entry)
            t=symbols(shell/'templates/entries.S')['table']
            assert trampoline[:t]==assemble(shell/'templates/entries.S')[:t]
            assert struct.unpack_from('<4I',trampoline,t)==(entry+t,w,m,0)
            self.card_offsets=(entry,w,m)
        super().__init__(loader,blob)
        self.mu.reg_write(UC_ARM_REG_C1_C0_2, 0xf << 20)
        self.mu.reg_write(UC_ARM_REG_FPEXC, 0x40000000)

    def _hook(self,mu,address,size,data):
        if address==self.entry:
            if self.card_offsets:
                e,w,m=self.card_offsets
                self.worker_at=address-e+w;self.module_at=address-e+m
            else:self.running_sup=True
            self.entry=None
        if address==self.worker_at:
            self.worker_calls+=1;self._ret(0);return # Worker task creation substituted.
        if address==self.module_at:self.running_sup=True
        if self.stop_at==address:
            mu.emu_stop();return
        if address==0xc03626c0:
            # The extra query may clobber caller VFP state.
            mu.reg_write(UC_ARM_REG_D0,0)
            mu.reg_write(UC_ARM_REG_FPSCR,0x00400000)
            self._ret(self.af);return
        if address==0xc05d6400 and self.visibility_props is not None:
            assert self.r(UC_ARM_REG_R1)==6
            value=self.visibility_props[self.r(UC_ARM_REG_R0)]
            mu.mem_write(self.r(UC_ARM_REG_R2),struct.pack('<I',value))
            self._ret(0);return # Bool property storage read substituted.
        if self.controls_probe:
            if address==0xc05dc17c and self.controls_native_reset is not None:
                # Original prologue ran. Substitute only the remaining binding
                # body: it writes a stale value and returns with native VFP.
                sp=self.r(UC_ARM_REG_SP)
                assert [self.r(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]==[HEAP+0x50000,1,HEAP+0x6e000,0]
                assert self.word(sp+36)==1
                location,value=self.controls_native_reset
                mu.mem_write(location,struct.pack('<I',value))
                frame=struct.unpack('<9I',mu.mem_read(sp,36))
                for r,v in zip((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11),frame):mu.reg_write(r,v)
                mu.reg_write(UC_ARM_REG_SP,sp+36);mu.reg_write(UC_ARM_REG_LR,frame[-1])
                mu.reg_write(UC_ARM_REG_D0,0x4009000000000000)
                mu.reg_write(UC_ARM_REG_FPSCR,0x01000000)
                self._ret(0x123);return
            if address in (0xc05d0630,0xc05d0738):
                owner=self.r(UC_ARM_REG_R0)
                self.controls_dirty.append((address,owner))
                mu.mem_write(owner+0x24,struct.pack('<I',self.word(owner+0x24)|0x1000))
                self._ret(0);return # Descendant invalidation traversal substituted.
        if self.transition_probe:
            if address in (0xc0010298,0xc00102d0):
                self.lock_depth+=1 if address==0xc0010298 else -1
                self._ret(0);return # Native mutex implementation substituted.
            if address in (HEAP+0x67000,HEAP+0x67004):
                assert self.lock_depth==1
                self.transition_order.append('exit' if address==HEAP+0x67000 else 'entry')
                if address==HEAP+0x67004:mu.reg_write(UC_ARM_REG_D0,0x4009000000000000)
                self._ret(0);return # Stock state callbacks substituted.
            if address==F['UI_FORCE']:
                assert self.lock_depth==0 and self.transition_order==['exit','entry']
                self.transition_order.append('redraw')
        if address==0xc00178d8:
            self._ret(0xc3033834);return # Read-only USER singleton lookup.
        if address==0xc02e4128:
            self._ret(HEAP+0x70000);return # Device status singleton lookup.
        if address in (0xc02e4930,0xc02e4970,0xc02e4a50):
            self._ret(0);return # Read-only hardware status queries.
        if address==0xc01d69d0:
            assert self.r(UC_ARM_REG_SP)%8==0
            self.picture_seen.append(([self.r(r) for r in
                (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R3)],
                bytes(mu.mem_read(self.r(UC_ARM_REG_R2),56)),
                self.r(UC_ARM_REG_D0),self.r(UC_ARM_REG_FPSCR)))
            # Run the stock Thumb setter and its channel-4 cache writes.
        if address==0xc05d64e0:
            sp=self.r(UC_ARM_REG_SP)
            index,pointer=struct.unpack('<2I',mu.mem_read(sp,8))
            component=self.r(UC_ARM_REG_R0)
            count=1 if index==3 else (2 if self.word(component+0x18)==0xc2dff5f4 else 4)
            assert [self.r(r) for r in (UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]==[1,0,0]
            self.vectors.append((index,bytes(mu.mem_read(pointer,4*count))))
            # Property callbacks are substituted; deliberately clobber caller
            # VFP/FPSCR state to check the activation wrapper restores them.
            mu.reg_write(UC_ARM_REG_D0,0)
            mu.reg_write(UC_ARM_REG_FPSCR,0x00400000)
            self._ret(0);return
        if self.running_sup and address==F['H_ADDR']:
            self.calls.append('SUP_ALLOC');self._ret(0 if self.fail else self.resident);return
        super()._hook(mu,address,size,data)

    def boot(self):
        self.call(CAVE_LOW)
        assert len(self.registered)==2
        assert self.word(0xc03da420)==0xeb0000cc


def check_install(c):
    m=c.manifest;symbols=m['symbols'];base=c.resident-symbols['resident']
    for i,(site,wrapper,kind) in enumerate(m['sites']):
        veneer=0xc072e064+8*i
        expected=base+symbols[wrapper]
        if kind==2:assert c.word(site)==expected
        elif kind==3:
            insn=list(Cs(CS_ARCH_ARM,CS_MODE_THUMB).disasm(bytes(c.mu.mem_read(site,4)),site))
            assert len(insn)==1 and insn[0].mnemonic=='b.w'
            assert int(insn[0].op_str.lstrip('#'),16)==veneer,(hex(site),insn[0].op_str,hex(veneer))
            assert c.word(veneer)==0xf000f8df and c.word(veneer+4)==expected
        else:
            word=c.word(site);offset=word&0xffffff
            if offset&0x800000:offset-=0x1000000
            assert site+8+offset*4==veneer
            assert c.word(veneer)==0xe51ff004 and c.word(veneer+4)==expected
    assert c.word(0xc072e060)==0xc072e064+8*len(m['sites'])
    return base


def exercise(directory,card=None):
    c=TrialCamera(directory,card=card);c.boot();base=check_install(c)
    if card:assert c.worker_calls==1
    blob=(directory/'inset-trial.arm').read_bytes();syms=c.manifest['symbols']
    assert bytes(c.mu.mem_read(c.resident,c.manifest['resident_bytes']))==blob[syms['resident']:]
    # Native Thumb variable-listener prologue: arguments and VFP inputs
    # must equal the original function entry; the stolen four bytes execute once.
    regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]
    fixture=SimpleNamespace(uc=c.mu,word=lambda a,v:c.mu.mem_write(a,struct.pack('<I',v)),
        words=lambda a,n=1:struct.unpack('<'+'I'*n,c.mu.mem_read(a,4*n)))
    root,_=scene(fixture);frame_scene(fixture,root)
    screen=c.word(root+0x80)
    app=HEAP+0x50000
    c.mu.mem_write(app+0x84c,struct.pack('<I',screen))
    for r,v in zip(regs,[app,0x2222,0x3333,0x4444]):c.mu.reg_write(r,v)
    for i in range(9):c.mu.reg_write(UC_ARM_REG_D0+i,0x4008000000000000+i)
    sp=STACK-0x1004;c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE|1)
    c.stop_at=0xc05d9f94
    c.mu.emu_start(0xc05d9f91,DONE,count=20000)
    assert c.r(UC_ARM_REG_PC)==c.stop_at
    assert [c.r(r) for r in regs]==[app,0x2222,0x3333,0x4444]
    assert c.word(base+syms['diagnostic']+168)==root
    assert c.word(base+syms['diagnostic']+172)==1
    assert [i for i,_ in c.vectors]==[3]*6+[0,0,1,1,9,6]
    assert [v for _,v in c.vectors[:6]]==[
        struct.pack('<f',2),struct.pack('<f',1)]*3
    assert c.r(UC_ARM_REG_SP)==sp-16 and c.r(UC_ARM_REG_R5)==0x2222
    assert [c.r(UC_ARM_REG_D0+i) for i in range(9)]==[0x4008000000000000+i for i in range(9)]
    assert c.r(UC_ARM_REG_FPSCR)==0
    assert c.word(base+syms['diagnostic']+196)==0
    # Nested property notifications preserve the native call without applying
    # the layout recursively or clearing the outer call's guard.
    c.mu.mem_write(base+syms['diagnostic']+196,struct.pack('<I',1))
    c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE|1)
    c.mu.reg_write(UC_ARM_REG_R0,app);c.mu.reg_write(UC_ARM_REG_R1,0x2222)
    c.mu.emu_start(0xc05d9f91,DONE,count=20000)
    assert c.word(base+syms['diagnostic']+164)==1 and len(c.vectors)==12
    assert c.word(base+syms['diagnostic']+196)==1
    c.mu.mem_write(base+syms['diagnostic']+196,struct.pack('<I',0))
    # CINE submission passes the descriptor pointer to the original Thumb
    # adapter and reproduces its 192-byte prologue without touching it.
    c.mu.mem_write(0xc3202cf0,struct.pack('<I',1))
    source=HEAP+0x30000;c.mu.mem_write(source,bytes(156))
    c.stop_at=0xc00e9c24
    c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE|1)
    c.mu.reg_write(UC_ARM_REG_R0,source)
    c.mu.emu_start(0xc00e9c21,DONE,count=20000)
    assert c.r(UC_ARM_REG_PC)==c.stop_at and c.r(UC_ARM_REG_R0)==source
    assert c.r(UC_ARM_REG_SP)%8==0
    assert bytes(c.mu.mem_read(source,156))==bytes(156)
    # The observed live-preview bank is diagnostic only. The complete original
    # descriptor and pointer must pass through unchanged even during MF PIP.
    raw=descriptor();struct.pack_into('<I',raw,0,3);raw=bytes(raw)
    c.mu.mem_write(source,raw)
    for address,value in ((0xc3202cf0,0),(0xc3765a24,0xc3765a8c),
        (0xc3765a8c,4),(0xc3075230,HEAP+0x40000),
        (HEAP+0x4058c,2),(0xc31d3e30,0),(0xc31d2858,1)):
        c.mu.mem_write(address,struct.pack('<I',value))
    c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE|1)
    c.mu.reg_write(UC_ARM_REG_R0,source)
    c.mu.emu_start(0xc00e9c21,DONE,count=20000)
    local=c.r(UC_ARM_REG_R0)
    assert c.r(UC_ARM_REG_PC)==c.stop_at and local==source
    assert bytes(c.mu.mem_read(source,156))==raw
    assert bytes(c.mu.mem_read(base+syms['diagnostic']+8,156))==raw
    assert c.word(base+syms['diagnostic'])==0
    assert c.word(base+syms['diagnostic']+4)==0
    assert c.word(base+syms['diagnostic']+164)==1
    assert c.word(base+syms['diagnostic']+176)==2
    # ARM callsite -> resident ARM wrapper -> stock Thumb output setter.
    # Verify the native cache, complete source immutability, return value,
    # callee-saved registers, alignment and VFP inputs at the native boundary.
    raw=bytearray(picture_descriptor());buffers=HEAP+0x31000
    struct.pack_into('<I',raw,32,buffers)
    c.mu.mem_write(buffers,struct.pack('<4I',0x49801000,0x49bfd000,0x49ff9000,0x4a3f5000))
    raw=bytes(raw)
    applied=(1,2,6064,4042,2274,1517,1516,1013,6064,4042,0,1010,6064,2022,100,100)
    c.mu.mem_write(0xc3033a84,struct.pack('<16I',*applied))
    for cine,af in ((0,0),(1,0),(0,1)):
        c.af=af;c.mu.mem_write(0xc3202cf0,struct.pack('<I',cine))
        c.mu.mem_write(source,raw)
        c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE)
        for r,v in zip(regs,[0,4,source,0x4444]):c.mu.reg_write(r,v)
        saved=[UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
               UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11]
        for i,r in enumerate(saved):c.mu.reg_write(r,0x5550+i)
        c.mu.reg_write(UC_ARM_REG_D0,0x4008000000000000)
        c.mu.reg_write(UC_ARM_REG_FPSCR,0)
        c.stop_at=0xc0429d20
        c.mu.emu_start(0xc0429d1c,DONE,count=20000)
        expected=bytearray(raw)
        if not cine and not af:struct.pack_into('<5I',expected,0,354,234,152,1114,114)
        assert c.picture_seen[-1]==([0,4,0x4444],bytes(expected),0x4008000000000000,0)
        assert c.r(UC_ARM_REG_PC)==c.stop_at and c.r(UC_ARM_REG_R0)==0
        assert c.r(UC_ARM_REG_SP)==sp
        assert [c.r(r) for r in saved]==[0x5550+i for i in range(8)]
        assert bytes(c.mu.mem_read(source,56))==raw
        e=struct.unpack('<14I',expected)
        assert struct.unpack('<8I',c.mu.mem_read(0xc31e11e8,32))==(e[12],e[0],e[1],0,e[2],e[3],e[4],e[5])
        assert bytes(c.mu.mem_read(0xc31e120c,16))==bytes(c.mu.mem_read(buffers,16))
        c.mu.mem_write(0xc3033a84,bytes(64))
    assert c.word(base+syms['diagnostic']+200)==3
    # Run the actual stock mode builder through the patched ARM callsite.
    # All MF controller, preference and Common words remain unchanged.
    common=HEAP+0x60000;params=HEAP+0x61000;override=HEAP+0x62000
    c.mu.mem_write(0xc375d844,struct.pack('<I',params))
    crop=(1024,682,448,299,128,85)
    for mode,kind,cine,af,custom in ((0,0,0,0,0),(1,0,0,0,0),
        (2,0,0,0,0),(0,1,0,0,0),(0,2,0,0,0),(0,0,1,0,0),
        (0,0,0,1,0),(0,0,0,0,1),(0,2,0,0,0)):
        c.af=af;c.mu.mem_write(0xc3202cf0,struct.pack('<I',cine))
        original=bytearray(0x5e4)
        struct.pack_into('<2I',original,0,3840,2160)
        struct.pack_into('<4I',original,0x58c,kind,0,100,100)
        struct.pack_into('<6I',original,0x59c,*crop)
        c.mu.mem_write(common,bytes(original))
        c.mu.mem_write(params,struct.pack('<2I',mode,0)+bytes(88))
        c.mu.mem_write(override,struct.pack('<6I',5,3840,2160,0,1,0))
        args=[mode,params+8,common,override if custom else 0]
        for r,v in zip(regs,args):c.mu.reg_write(r,v)
        for i,r in enumerate(saved):c.mu.reg_write(r,0x5550+i)
        c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE)
        c.mu.reg_write(UC_ARM_REG_D0,0x4008000000000000)
        c.mu.reg_write(UC_ARM_REG_FPSCR,0);c.stop_at=0xc04369fc
        c.mu.emu_start(0xc04369f8,DONE,count=20000)
        yes=not(mode>1 or kind or cine or af or custom)
        assert c.word(params+0x28)==(2 if yes else (0 if custom else kind))
        if yes:assert struct.unpack('<6I',c.mu.mem_read(params+0x2c,24))==crop
        assert bytes(c.mu.mem_read(common,len(original)))==bytes(original)
        assert c.r(UC_ARM_REG_SP)==sp
        assert [c.r(r) for r in saved]==[0x5550+i for i in range(8)]
        assert c.r(UC_ARM_REG_D0)==0x4008000000000000 and c.r(UC_ARM_REG_FPSCR)==0
        # Crop adapter preserves the original native call, passing the local
        # selected crop only for passive manual STILL previews.
        c.mu.mem_write(params+0x28,struct.pack('<7I',2,*crop))
        c.mu.mem_write(0xc3075174,struct.pack('<I',kind))
        args=[0x1111,common+0x59c,HEAP+0x63000,0x4444]
        for r,v in zip(regs,args):c.mu.reg_write(r,v)
        c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE)
        c.mu.reg_write(UC_ARM_REG_D0,0x4008000000000000)
        c.mu.reg_write(UC_ARM_REG_FPSCR,0);c.stop_at=0xc030cc90
        c.mu.emu_start(0xc0436af0,DONE,count=20000)
        expected=args.copy()
        if not(mode>1 or kind or cine or af):expected[1]=params+0x2c
        assert [c.r(r) for r in regs]==expected
        assert c.r(UC_ARM_REG_SP)==sp
        assert [c.r(r) for r in saved]==[0x5550+i for i in range(8)]
        assert c.r(UC_ARM_REG_D0)==0x4008000000000000 and c.r(UC_ARM_REG_FPSCR)==0
        assert bytes(c.mu.mem_read(common,len(original)))==bytes(original)
    # Diagnostic startup history must survive later preview preparations.
    if c.manifest['symbols']['core']-c.manifest['symbols']['diagnostic'] in (2416,2480):
        diag=c.resident+c.manifest['symbols']['diagnostic']-c.manifest['symbols']['resident']
        for i in range(8):
            row=struct.unpack('<64I',c.mu.mem_read(diag+256+i*256,256))
            assert row[:2]==(i+1,params+8)
            assert row[28:34]==crop, 'Startup Common crop snapshot is incomplete'
        assert row[10]==0 and row[24]==0, 'Later preparation overwrote startup history'
        first=struct.unpack('<28I',c.mu.mem_read(diag+2304,112))
        assert first[:14]==struct.unpack('<14I',raw)
        assert first[14:19]==(354,234,152,1114,114)
        if c.manifest['symbols']['core']-c.manifest['symbols']['diagnostic']==2480:
            assert struct.unpack('<16I',c.mu.mem_read(diag+2416,64))==applied
            assert c.word(diag)==params and c.word(diag+4)==0x5553
    # Execute the original transition body through its one-instruction
    # trampoline. Redraw must follow BOTH native callbacks and mutex releases.
    manager=HEAP+0x66000;vt=HEAP+0x64000;states=HEAP+0x65000
    c.mu.mem_write(vt+12,struct.pack('<2I',HEAP+0x67004,HEAP+0x67000))
    for index in (1,3,4,5):
        c.mu.mem_write(states+index*32,struct.pack('<5I',index,0,0,manager,vt))
    c.transition_probe=True;c.stop_at=None
    for previous,current,cine,af in ((1,4,0,0),(4,1,0,0),(1,5,0,0),
        (5,1,0,0),(4,4,0,0),(4,5,0,0),(4,3,0,0),(1,4,1,0),(4,1,0,1)):
        c.af=af;c.transition_order=[];c.lock_depth=0
        c.mu.mem_write(0xc3202cf0,struct.pack('<I',cine))
        old=states+previous*32;new=states+current*32
        c.mu.mem_write(manager,struct.pack('<3I',old,old,0))
        for r,v in zip(regs,[manager,new,1,0x4444]):c.mu.reg_write(r,v)
        for i,r in enumerate(saved):c.mu.reg_write(r,0x5550+i)
        c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE)
        c.mu.reg_write(UC_ARM_REG_D0,0x4008000000000000);c.mu.reg_write(UC_ARM_REG_FPSCR,0)
        before=len(c.draws)
        c.mu.emu_start(0xc0481a08,DONE,count=20000)
        yes=not(cine or af) and ((previous==1 and current in (4,5)) or
                                (previous in (4,5) and current==1))
        assert c.transition_order==['exit','entry']+(['redraw'] if yes else [])
        assert len(c.draws)==before+int(yes)
        if yes:assert c.draws[-1][1]==(0x101,0xffffffff,0)
        assert c.lock_depth==0 and c.word(manager+4)==new and c.word(manager+8)==old
        assert c.r(UC_ARM_REG_SP)==sp and c.r(UC_ARM_REG_R0)==0
        assert [c.r(r) for r in saved]==[0x5550+i for i in range(8)]
        assert c.r(UC_ARM_REG_D0)==0x4009000000000000 and c.r(UC_ARM_REG_FPSCR)==0
    c.transition_probe=False
    # Run the stock effective-visibility ancestor walk with Magnify hidden.
    # Only the PIP border may escape it; the mask and adjustment parents must
    # stay hidden. All native property/state words remain unchanged.
    params=HEAP+0x61000
    c.visibility_props={}
    nodes=[];p=root
    for i in range(6):
        nodes.append(p)
        if i<5:p=c.word(c.word(p+0x60))
    border=c.word(c.word(nodes[-1]+0x60));mask=c.word(c.word(nodes[-1]+0x60)+4)
    nodes += [border,mask]
    for i,node in enumerate(nodes):
        comp=HEAP+0x68000+i*0x100;table=HEAP+0x69000+i*4
        c.mu.mem_write(node+0x30,struct.pack('<I',1))
        c.mu.mem_write(node+0x40,struct.pack('<I',1))
        c.mu.mem_write(node+0x4c,struct.pack('<I',table))
        c.mu.mem_write(table,struct.pack('<I',comp))
        c.visibility_props[comp]=0 if i==1 else 1
    original_props=c.visibility_props.copy()
    for cine,af,mode,pip,kind in ((0,0,0,2,0),(0,0,1,2,0),
        (1,0,0,2,0),(0,1,0,2,0),(0,0,2,2,0),(0,0,0,0,0),
        (0,0,0,2,1),(0,0,0,2,2)):
        c.af=af;c.mu.mem_write(0xc3202cf0,struct.pack('<I',cine))
        c.mu.mem_write(params,struct.pack('<I',mode))
        c.mu.mem_write(params+0x28,struct.pack('<I',pip))
        c.mu.mem_write(0xc3075174,struct.pack('<I',kind))
        for node in (border,mask,nodes[1],nodes[3],nodes[5]):
            for i,r in enumerate(saved):c.mu.reg_write(r,0x5550+i)
            c.mu.reg_write(UC_ARM_REG_R0,node)
            c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE)
            c.mu.reg_write(UC_ARM_REG_D0,0x4008000000000000);c.mu.reg_write(UC_ARM_REG_FPSCR,0)
            c.mu.emu_start(0xc05d0289,DONE,count=20000)
            yes=node==border and not(cine or af or mode>1 or pip!=2 or kind)
            assert c.r(UC_ARM_REG_R0)==int(yes), ('border visibility',hex(node),cine,af,mode,pip,kind)
            assert c.r(UC_ARM_REG_SP)==sp
            assert [c.r(r) for r in saved]==[0x5550+i for i in range(8)]
            assert c.r(UC_ARM_REG_D0)==0x4008000000000000 and c.r(UC_ARM_REG_FPSCR)==0
            assert c.visibility_props==original_props
    # Native null guard still returns zero through the resident trampoline.
    c.mu.reg_write(UC_ARM_REG_R0,0);c.mu.reg_write(UC_ARM_REG_SP,sp)
    c.mu.reg_write(UC_ARM_REG_LR,DONE);c.mu.emu_start(0xc05d0289,DONE,count=20000)
    assert c.r(UC_ARM_REG_R0)==0 and c.r(UC_ARM_REG_SP)==sp
    assert c.word(base+syms['diagnostic']+244)==2
    c.visibility_props=None
    # Post-binding update: execute native current-only bool reader/setter,
    # generic property storage and ObjectBase change callback. Enter/exit stale
    # values must change immediately, with dirty propagation and no default edit.
    check_controls(c,base,root,sp,saved,regs)
    # The physical failure was on MEDIUM; repeat with its distinct object IDs.
    screen=c.word(root+0x80)
    c.mu.mem_write(c.word(screen+8),b'LV_STILL_MEDIUM\0')
    parent=c.word(c.word(root+0x60))
    c.mu.mem_write(parent+0x18,struct.pack('<I',8938))
    check_controls(c,base,root,sp,saved,regs)
    # Real shared power-off journal restores every hook word, on both lists.
    c.stop_at=None
    obj=c.registered[0][0]
    for _ in range(2):c.call(c.word(obj+4),r0=obj,r1=4)
    for site,_,_ in c.manifest['sites']:
        assert bytes(c.mu.mem_read(site,4))==(directory/f'{site:08x}.stock').read_bytes()
    if card:assert c.word(0xc0cf3740)==struct.unpack_from('<I',c.stock,0xcf3740)[0]
    failed=TrialCamera(directory,fail=True,card=card);failed.boot()
    for site,_,_ in failed.manifest['sites']:
        assert bytes(failed.mu.mem_read(site,4))==(directory/f'{site:08x}.stock').read_bytes()
    assert failed.word(0xc072e060)==0xc072e064
    # A full native shutdown list must leave every hook untouched too.
    full=TrialCamera(directory,card=card);full.journal_failure='ordinary'
    full.call(CAVE_LOW)
    assert full.word(0xc072e060)==0xc072e064 and not full.running_sup
    for site,_,_ in full.manifest['sites']:
        assert bytes(full.mu.mem_read(site,4))==(directory/f'{site:08x}.stock').read_bytes()
    # Negative control: corrupt the long Thumb branch's J2 bit.
    bad=TrialCamera(directory,card=card);bad.boot()
    site=0xc00e9c20;bad.mu.mem_write(site,struct.pack('<I',bad.word(site)^(1<<27)))
    try:check_install(bad)
    except AssertionError:pass
    else:raise AssertionError('corrupted Thumb branch was accepted')
    # Disable the new hook: the first stale entry must fail this same check.
    bad=TrialCamera(directory,card=card);bad.boot();badbase=check_install(bad)
    badroot,_=scene(SimpleNamespace(uc=bad.mu,word=lambda a,v:bad.mu.mem_write(a,struct.pack('<I',v))))
    bad.mu.mem_write(0xc05dc178,(directory/'c05dc178.stock').read_bytes())
    try:check_controls(bad,badbase,badroot,sp,saved,regs)
    except AssertionError:pass
    else:raise AssertionError('disabled controls correction was accepted')
    print(f'PASS: shared loader + installer, {len(c.manifest["sites"])} declared hooks/owned copy, listener/VFP ABI, native PIP output setter/cache, native preview builder and local crop ABI, transition body and redraw after callback locks, native visibility walk with border-only override, native current-only bool storage/change callback, immediate stale entry/exit correction with unchanged defaults, complementary normal-display recovery including moved-area partial exit, capture/fullscreen/AF/CINE passthrough, recursive guard, power-off restore, allocation failure, branch and disabled-controls negative checks')


def check_controls(c,base,root,sp,saved,regs):
    def put(a,v):c.mu.mem_write(a,struct.pack('<I',v))
    screen=c.word(root+0x80);parent=c.word(c.word(root+0x60))
    normal_ids=(8938,9113) if c.word(parent+0x18)==9092 else (8936,8937)
    parents=[parent,HEAP+0x6f900,HEAP+0x70900]
    root_table=HEAP+0x74000;put(root+0x54,3);put(root+0x60,root_table)
    app=HEAP+0x50000;params=HEAP+0x61000;props=[]
    for i,owner in enumerate(parents):
        if i:
            put(owner+0x18,normal_ids[i-1]);put(owner+0x1c,root)
            put(owner+0x80,screen)
        put(root_table+4*i,owner)
        start=HEAP+(0x6b000 if not i else 0x6f000+(i-1)*0x1000)
        comp,table,vt,offsets,values,binding,edit,meta=[start+j*0x100 for j in range(8)]
        put(owner+0x40,1);put(owner+0x4c,table);put(table,comp)
        put(comp,binding);put(comp+0x10,vt);put(comp+0x14,13)
        put(comp+0x18,0xc2dff5f4);put(comp+0x1c,offsets);put(comp+0x20,values)
        put(comp+0x24,owner);put(comp+0x28,meta)
        put(vt+8,0xc05d4a91);put(vt+0x18,0xc05d4711)
        put(binding,app);put(binding+0x1c,edit);put(owner,binding)
        props.append((values,edit))
    values=props[0][0]
    put(app+0x84c,screen);put(0xc375d844,params)
    lockholder=HEAP+0x6d000;put(app+0x888,lockholder)
    c.visibility_props=None;c.controls_probe=True;c.stop_at=None
    # Repeated entry/exit with a stale native visibility write. The last case
    # reproduces hardware: Magnify already hidden, normal groups still hidden.
    cases=((2,1,0,0,0,2,0,1),(0,0,1,0,0,2,0,0),
        (2,1,0,0,0,2,0,1),(0,0,1,0,0,2,0,0),
        (2,1,1,0,0,2,0,1),(2,0,1,0,0,2,0,0),
        (2,1,0,1,0,2,0,0),(2,1,0,0,1,2,0,0),
        (2,1,0,0,0,2,2,0),(2,1,0,0,0,0,0,0),
        (1,1,0,0,0,2,0,0),(0,0,0,0,0,2,0,0))
    for index,(kind,active,initial,cine,af,pip,mode,want) in enumerate(cases):
        normal_initial=0 if index==len(cases)-1 else 1-initial
        before_values=[initial,normal_initial,normal_initial]
        allowed=not(cine or af or mode>1 or pip!=2 or kind not in (0,2))
        after_values=[want,1-want,1-want] if allowed else before_values
        for owner,(v,edit),old in zip(parents,props,before_values):
            put(v,old);put(v+4,1);put(owner+0x24,4);put(edit+4,0)
        put(values,1-initial);c.controls_native_reset=(values,initial)
        put(0xc3075174,kind);put(0xc3075178,active)
        put(0xc3202cf0,cine);c.af=af;put(params,mode);put(params+0x28,pip)
        c.controls_dirty=[];before=len(c.draws)
        for r,v in zip(regs,[app,1,HEAP+0x6e000,0]):c.mu.reg_write(r,v)
        for i,r in enumerate(saved):c.mu.reg_write(r,0x5550+i)
        for i in range(9):c.mu.reg_write(UC_ARM_REG_D0+i,0x4008000000000000+i)
        c.mu.reg_write(UC_ARM_REG_FPSCR,0);c.mu.reg_write(UC_ARM_REG_SP,sp)
        put(sp,1);c.mu.reg_write(UC_ARM_REG_LR,DONE)
        c.mu.emu_start(0xc05dc179,DONE,count=20000)
        assert c.r(UC_ARM_REG_PC)==DONE and c.r(UC_ARM_REG_R0)==0x123
        changed=[]
        for owner,(v,edit),old,new in zip(parents,props,before_values,after_values):
            assert c.word(v)==new and c.word(v+4)==1, ('display recovery',index,owner,old,new)
            if old!=new:changed += [(0xc05d0630,owner),(0xc05d0738,owner)]
            assert c.word(edit+4)==0 and c.word(owner+0x24)==(0x1004 if old!=new else 4)
        assert c.controls_dirty==changed
        assert c.r(UC_ARM_REG_SP)==sp and c.word(sp)==1
        assert [c.r(r) for r in saved]==[0x5550+i for i in range(8)]
        assert c.r(UC_ARM_REG_D0)==0x4009000000000000
        assert [c.r(UC_ARM_REG_D0+i) for i in range(1,9)]==[0x4008000000000000+i for i in range(1,9)]
        assert c.r(UC_ARM_REG_FPSCR)==0x01000000
        assert c.word(0xc3075174)==kind and c.word(0xc3075178)==active
        assert len(c.draws)==before+bool(changed)
        if changed:assert c.draws[-1][1]==(0x101,0xffffffff,0)
    # Real native unsupported-variable return and native post-call ABI.
    c.controls_native_reset=None
    put(0xc3202cf0,0);c.af=0;put(params,0);put(params+0x28,2)
    put(0xc3075174,2);put(0xc3075178,1);put(values,0)
    c.mu.reg_write(UC_ARM_REG_R0,app);c.mu.reg_write(UC_ARM_REG_R1,0)
    c.mu.reg_write(UC_ARM_REG_SP,sp);c.mu.reg_write(UC_ARM_REG_LR,DONE)
    c.mu.emu_start(0xc05dc179,DONE,count=20000)
    assert c.r(UC_ARM_REG_PC)==DONE and c.r(UC_ARM_REG_R0)==2
    assert c.r(UC_ARM_REG_SP)==sp and c.word(values)==1 and c.word(values+4)==1
    c.controls_probe=False;c.stop_at=None


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    p.add_argument('--card',type=Path)
    args=p.parse_args();exercise(args.directory,args.card)
