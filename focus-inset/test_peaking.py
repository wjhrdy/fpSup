"""Actual native peaking region builder plus installed adapter, without hardware."""
import argparse
from pathlib import Path
import struct
from unicorn import UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
from test_trial import TrialCamera, HEAP, STACK, DONE, CAVE_LOW


class PeakingCamera(TrialCamera):
    def _hook(self, mu, address, size, data):
        if address == 0xc0017ac8:
            self._ret(HEAP+0x70000); return  # Read-only runtime Result singleton.
        return super()._hook(mu, address, size, data)


def exercise(directory):
    c = PeakingCamera(directory)
    c.call(CAVE_LOW)
    site = 0xc0305b98
    armed = bytes(c.mu.mem_read(site, 4))
    stock = (directory/'c0305b98.stock').read_bytes()
    output, event, rect, params = [HEAP+x for x in (0x60000,0x60100,0x60200,0x60300)]
    def put(a, *v): c.mu.mem_write(a,struct.pack('<'+'I'*len(v),*v))
    put(event,0,rect); put(0xc375d844,params); put(params,0)
    put(params+0x28,2); put(0xc3202cf0,0); put(0xc3075174,0)
    put(HEAP+0x7023c,2)
    saved = [UC_ARM_REG_R4+i for i in range(8)]
    writes=[]
    hook=c.mu.hook_add(UC_HOOK_MEM_WRITE,lambda mu,access,a,n,v,data:writes.append((a,n)))
    def run(patched, dimensions, region, cine=0, af=0, pip=2, mode=0, kind=0):
        put(rect,*dimensions,*region); put(output,0,0,0,0)
        put(0xc3202cf0,cine); c.af=af; put(params,mode); put(params+0x28,pip)
        put(0xc3075174,kind)
        c.mu.mem_write(site,armed if patched else stock)
        # Flush translated instructions after the deliberate negative/stock control.
        c.mu.ctl_remove_cache(site,site+4)
        for i,r in enumerate(saved):c.mu.reg_write(r,0x5550+i)
        c.mu.reg_write(UC_ARM_REG_R2,event)
        c.mu.reg_write(UC_ARM_REG_D0,0x4008000000000000)
        c.mu.reg_write(UC_ARM_REG_FPSCR,0)
        writes.clear()
        c.call(site,output,HEAP+0x60400,sp=STACK-0x1000)
        assert c.r(UC_ARM_REG_PC)==DONE and c.r(UC_ARM_REG_SP)==STACK-0x1000
        assert [c.r(r) for r in saved]==[0x5550+i for i in range(8)]
        assert all(output<=a<a+n<=output+16 or STACK-0x2000<=a<a+n<=STACK for a,n in writes)
        assert c.r(UC_ARM_REG_FPSCR)==0
        return struct.unpack('<4I',c.mu.mem_read(output,16))
    for dims,region in [((1920,1080),(0,0,1620,1080)),((1024,682),(0,0,1024,682)),
                        ((1920,1080),(16,20,1600,1040))]:
        old=run(False,dims,region)
        expected=(region[0],region[1],region[0]+region[2]-1,region[1]+region[3]-1)
        assert old!=expected, 'Stock PIP clipping was not reproduced'
        put(HEAP+0x7023c,0)
        assert run(False,dims,region)==expected, 'Override differs from native normal-view area'
        put(HEAP+0x7023c,2)
        for kind in (0,2,0,2,0):
            assert run(True,dims,region,kind=kind)==expected
        for gate in [dict(cine=1),dict(af=1),dict(pip=1),dict(mode=2),dict(kind=1)]:
            assert run(True,dims,region,**gate)==run(False,dims,region,**gate)
    # Other output profiles and malformed geometry retain native behavior.
    for dims,region in [((1280,720),(0,0,1080,720)),((1920,1080),(0,0,1921,1080))]:
        assert run(True,dims,region)==run(False,dims,region)
    c.mu.hook_del(hook)
    print('PASS native centred PIP clipping reproduced; full peaking region on both supported displays, repeated entry/exit, AF/CINE/capture/fullscreen passthrough, stack/register ABI and output-only writes')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path)
    exercise(p.parse_args().directory)
