"""Native Indoor/LV checks executed with verify_card globals."""
def verify(path):
    pairs = [(int(a, 16), int(w, 16)) for a, w in re.findall(
        r'^mem set (0x\w+) (0x\w+)', (path / 'AutoRun.txt').read_text(), re.M)]
    loader = {a: w for a, w in pairs if T.CAVE_LOW <= a < T.CAVE_LOW + 0x200}
    bootstrap = {a: w for a, w in pairs if 0xC072F700 <= a < 0xC0730000}
    c = Card(loader, (path / 'fpSup.BIN').read_bytes())
    c.mu.mem_write(SAVE, struct.pack('<I', MAGIC | 6))
    c.now = 15_000_000
    modes = ('ordinary loader', 'stored bootstrap', 'warm hook') if bootstrap else ('ordinary loader', 'ordinary reload')
    for mode, restore_index in ((m, i) for m in modes for i in (0, 1)):
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
        assert c.word(0xc021ee94)==0xeb0017f5, 'Old Indoor builder hook remains'
        assert c.word(0xc0226508)==0xe92d4df0, 'BF interpolator remains'
        assert c.word(0xc0210118)!=0xe92d4010, 'Native getter hook absent'
        c.preset()
        c.fixture(state=0,publish=False)
        ret,sp=c.call(0xc0210118,0xc3202288,sp=STACK)
        assert ret==2 and sp==STACK
        assert c.word(0xc320228c)==0 and c.word(0xc32006fc)==0
        c.preset(dial=3)
        ret,sp=c.call(0xc0210118,0xc3202288,sp=STACK)
        assert ret==0 and sp==STACK
        assert c.word(0xc05288e4)!=0xe2855001, 'Warning draw hook absent'
        c.call(0xc052b310,0xc37830d0,sp=STACK)
        pixels=T.HEAP+0x200000;desc=T.HEAP+0x1a0000;dims=desc+16
        c.put(desc,3,pixels,dims)
        c.put(STACK+0x20,desc)
        c.put(STACK+0x1c,0x1000000);c.put(dims,1024,128)
        c.mu.mem_write(pixels,bytes([7])*(1024*128))
        for name,classification,threshold in ((b'Indoor',2,7315),(b'Indoor60',2,7315),(b'Indoor50',1,6967)):
            c.preset(name=name);c.fixture(state=0,publish=False)
            ret,sp=c.call(0xc0210118,0xc3202288,sp=STACK)
            assert ret==classification and sp==STACK
            for lens in (0,1,2):
                c.put(0xc347b1d4,lens);c.put(0xc3202c9c,threshold+1)
                c.put(STACK+0x18,0);c.mu.reg_write(UC_ARM_REG_R5,1)
                draw_warning(c,desc)
                assert c.r(UC_ARM_REG_PC)==0xc05288e8
                assert bytes(c.mu.mem_read(STACK+0x18,4))==bytes((0,0,0,1))
                assert bytes(c.mu.mem_read(pixels+64*1024+400,192))==bytes([3])*192
                c.put(0xc3202c9c,threshold);c.mu.reg_write(UC_ARM_REG_R5,1)
                draw_warning(c,desc)
                assert bytes(c.mu.mem_read(pixels+64*1024+400,192))==bytes(192)
        c.put(0xc3202c78,8192)  # non-display tuple must not affect the warning
        c.put(0xc3202c9c,7000)
        for name,risk in ((b'Indoor60',False),(b'Indoor50',True),(b'Indoor60',False)):
            c.preset(name=name);c.call(0xc0210118,0xc3202288,sp=STACK)
            c.mu.reg_write(UC_ARM_REG_R5,1)
            draw_warning(c,desc)
            assert bytes(c.mu.mem_read(pixels+64*1024+400,192))==(bytes([3])*192 if risk else bytes(192))
        check_focus(c)
        obj = c.registered[restore_index][0]
        c.call(c.word(obj + 4), r0=obj, r1=4, sp=STACK)
        for a, word, _ in B.hook_sites(True):
            assert bytes(c.mu.mem_read(a, 4)) == word, hex(a)
        for a, data in stock:
            assert bytes(c.mu.mem_read(a, len(data))) == data, f'journal failed at {a:#x}'
        assert c.word(T.DRAW) == T.DRAW_STOCK
        assert c.word(SAVE) == MAGIC | 6
        print(f'{path.name} / {mode}: payload entries returned, LV Boost task resident, hooks restored')
