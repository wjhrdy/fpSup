"""Native OSD loop, group routing and glyphs; GUI pixels/hardware submit mocked."""
from pathlib import Path
import re
import sys
from unicorn.arm_const import *
import test_combined as combined

V = combined.V
HEAP, STACK = V.T.HEAP, V.STACK


class DrawCamera(combined.Combined):
    def _hook(self, mu, addr, size, data):
        if addr == 0xc036d888:
            self.put(self.r(UC_ARM_REG_R1)+8, self.group_mask)
            return self._ret(1)
        if addr in (0xc036d7e0, 0xc0019dc0, 0xc001a0d8):
            return self._ret(0)
        if addr == HEAP+0x1c1000:
            return self._ret(HEAP+0x1a0000)  # live native layer descriptor
        if addr == HEAP+0x1c1004:
            self.gui_calls += 1
            desc = self.r(UC_ARM_REG_R1)
            assert desc == HEAP+0x1a0000
            pixels = self.word(desc+4)
            # Model a native GUI observer painting a transparent full screen.
            # Actual observer traversal/order executes; GUI rasterizer is mocked.
            mu.mem_write(pixels, bytes([self.gui_color])*(1024*128))
            return self._ret(1)
        if addr == HEAP+0x1c1008:
            self.flips += 1
            self.front = bytes(mu.mem_read(self.word(HEAP+0x1a0004),1024*128))
            return self._ret(0)  # native layer queue flip only; routing runs
        if addr == HEAP+0x1c100c:
            return self._ret(HEAP+0x1a0000)  # displayed descriptor
        if addr == HEAP+0x1c1010:
            return self._ret(0)  # native observer has no extra redraw callback
        if addr == 0xc0528e18:
            return self._ret(0)  # native external framebuffer option disabled
        if addr == 0xc02e4ea0:
            return self._ret(HEAP+0x1c2000)  # display device singleton
        if addr == 0xc02e5550:
            assert self.r(UC_ARM_REG_R2)==HEAP+0x1a0000
            self.submits += 1
            return self._ret(0)  # hardware output only; C0528650 runs
        if addr == 0xc0528c28:
            return self._ret(0)  # end-of-cycle bookkeeping after submission
        return super()._hook(mu,addr,size,data)


def check(path):
    text=(path/'AutoRun.txt').read_text()
    loader={int(a,16):int(v,16) for a,v in re.findall(r'^mem set (0x\w+) (0x\w+)',text,re.M)
            if V.T.CAVE_LOW<=int(a,16)<V.T.CAVE_LOW+0x200}
    c=DrawCamera(loader,(path/'fpSup.BIN').read_bytes())
    c.call(V.T.CAVE_LOW,sp=STACK)
    c.call(0xc052b310,0xc37830d0,sp=STACK)
    c.preset(name=b'Indoor60');c.fixture(state=0,publish=False)
    c.call(0xc0210118,0xc3202288,sp=STACK)
    c.put(0xc3033a44,2);c.put(0xc3033a54,1)
    desc,dims,layer,vt,obs,ovt=[HEAP+n for n in (0x1a0000,0x1a0010,0x1c0000,0x1c0040,0x1c0080,0x1c00c0)]
    controller=0xc3783020
    # The actual camera shares this layer between groups 1 and 3. Its GUI
    # observer belongs to group 3. Native C0528178 suppresses group-1 submit.
    c.put(controller+0x60,layer);c.put(controller+0x70,layer)
    c.put(layer,vt);c.put(vt+0x10,HEAP+0x1c1000)
    c.put(vt+0x14,HEAP+0x1c1008);c.put(vt+0xc,HEAP+0x1c100c)
    c.put(controller+36,obs);c.put(obs,ovt);c.put(ovt+12,HEAP+0x1c1004)
    c.put(ovt+0x1c,HEAP+0x1c1010)
    frames=[HEAP+0x200000+i*0x20000 for i in range(3)]
    c.put(dims,1024,128)
    c.gui_calls=0
    c.gui_color=0
    c.flips=c.submits=0;c.group_mask=10;c.front=bytes(1024*128)
    # A private group-1 draw must not be mistaken for a visible frame.
    c.group_mask=2;c.put(0xc3202c9c,8192);c.put(desc,3,frames[0],dims)
    c.call(0xc0528700,controller,sp=STACK)
    assert c.flips==0 and c.submits==0
    c.group_mask=10
    for tv,risk in ((8192,True),(7315,False),(8192,True)):
        c.put(0xc3202c9c,tv)
        for pixels in frames:
            c.put(desc,3,pixels,dims)
            c.mu.mem_write(pixels,bytes(1024*128))
            before=c.flips
            c.call(0xc0528700,controller,sp=STACK)
            row=c.front[64*1024+400:64*1024+592]
            assert row==(bytes([3])*192 if risk else bytes(192)), 'Warning absent from submitted GUI frame'
            assert c.flips==before+1 and c.submits>0
    assert c.gui_calls==9
    c.gui_color=7
    c.put(0xc3033a54,2)  # menu/transition: clearing must precede GUI painting
    for pixels in frames:
        c.put(desc,3,pixels,dims)
        c.call(0xc0528700,controller,sp=STACK)
        assert bytes(c.mu.mem_read(pixels,1024*128))==bytes([7])*(1024*128), 'Warning clearing damaged menu redraw'
        assert c.front==bytes([7])*(1024*128)
    print('PASS native full OSD loop and C0528178/C0528650 routing: group 1 never flips; warning reaches submitted group-3 GUI on all three buffers; threshold clearing/menu integrity')


if __name__=='__main__':
    check(Path(sys.argv[1]))
