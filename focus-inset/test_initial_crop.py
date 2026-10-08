"""First native OpNew crop submission: reproduce empty cache, verify local fix."""
import argparse,json,struct
from pathlib import Path
from unicorn.arm_const import *
from test_trial import TrialCamera,HEAP,STACK,DONE,CAVE_LOW

class CropCamera(TrialCamera):
    def _hook(self,mu,address,size,data):
        # Read-only services and hardware writers are substituted. The native
        # crop builder, profile getters, Result reads and cache setter execute.
        returns={0xc030c768:HEAP+0x71000,0xc030c7d0:100,
                 0xc03629d8:1,0xc03629f8:1,0xc00178d8:0xc3033834,
                 0xc0017ac8:0xc303384c,0xc01d4c48:0,0xc01d3860:0,
                 0xc01d3618:0x11,0xc01a6130:0,0xc01a6160:0,0xc01a6198:0}
        if address in returns:self._ret(returns[address]);return
        return super()._hook(mu,address,size,data)

def exercise(directory):
    c=CropCamera(directory);c.call(CAVE_LOW)
    site=0xc0428bec;armed=bytes(c.mu.mem_read(site,4))
    stock=(directory/'c0428bec.stock').read_bytes()
    obj,profile,config,params=[HEAP+x for x in (0x60000,0x60100,0x60200,0x60400)]
    def put(a,*v):c.mu.mem_write(a,struct.pack('<'+'I'*len(v),*v))
    put(profile,0x11,config);put(config+0x24,750);put(config+0x2c,500)
    put(0xc375d844,params);put(params,0);put(params+0x28,2)
    put(params+0x2c,1024,682,384,256,256,171)
    put(0xc3033a84,1,2,6064,4042,2274,1517,1516,1013,6064,4042,0,1010,6064,2022,100,100)
    saved=[UC_ARM_REG_R4+i for i in range(8)]
    def run(patched,state=0,kind=2,cine=0,af=0,pip=2):
        c.mu.mem_write(0xc31df8c4,bytes(0xa88))
        put(obj,0,profile,0,state,0,0,kind,0x123)
        original=bytes(c.mu.mem_read(obj,32))
        put(0xc3202cf0,cine);put(params+0x28,pip);c.af=af
        c.mu.mem_write(site,armed if patched else stock);c.mu.ctl_remove_cache(site,site+4)
        for i,r in enumerate(saved):c.mu.reg_write(r,0x5550+i)
        c.mu.reg_write(UC_ARM_REG_D0,0x4008000000000000)
        c.mu.reg_write(UC_ARM_REG_FPSCR,0)
        sp=STACK-0x1004
        c.stop_at=site+4
        c.call(site,obj,lr=DONE,sp=sp)
        assert c.r(UC_ARM_REG_PC)==site+4 and c.r(UC_ARM_REG_SP)==sp
        assert [c.r(r) for r in saved]==[0x5550+i for i in range(8)]
        assert bytes(c.mu.mem_read(obj,32))==original,'Real controller state was changed'
        return bytes(c.mu.mem_read(0xc31dfbf0,32))
    old=run(False);assert old==bytes(32),'Stock initial missing crop was not reproduced'
    expected=run(False,state=5)
    assert struct.unpack('<8I',expected)==(3032,1013,0,1010,6064,4042,6064,2022),struct.unpack('<8I',expected)
    assert run(True)==expected,'Initial submission differs from native ready-state crop'
    for gates in [dict(state=5),dict(state=1),dict(kind=0),dict(cine=1),dict(af=1),dict(pip=0)]:
        assert run(True,**gates)==run(False,**gates),gates
    print('PASS actual native initial crop; stock empty-cache failure, ready-state equivalence, gates, controller preservation and wrapper ABI')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path)
    exercise(p.parse_args().directory)
