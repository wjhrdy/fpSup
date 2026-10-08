"""Synthetic GUI trees and native output descriptors for offline checks."""
import struct
RAM = 0xc3800000

def descriptor():
    data = bytearray(156)
    for offset,values in ((0x60,(1024,682)),(0x64,(1024,682)),(0x78,(4096,2730)),
                          (0x7c,(1024,682)),(0x80,(1536,1024))):
        struct.pack_into('<2H',data,offset,*values)
    return data


def picture_descriptor():
    return struct.pack('<14I',808,538,406,406,271,0,0,4,RAM+0x1700,0,0,2,1,0)


def scene(p, name='LV_STILL_LARGE'):
    root, screen, label = RAM+0x2000, RAM+0x2100, RAM+0x2200
    p.word(root+0x18,1); p.word(root+0x80,screen)
    p.word(screen+0xc,root); p.word(screen+8,label)
    p.uc.mem_write(label,name.encode()+b'\0')
    parent = root
    for n,oid in enumerate((8938 if name=='LV_STILL_MEDIUM' else 9092,7780,7894,9085,9093)):
        child,table = RAM+0x3000+n*0x200,RAM+0x3100+n*0x200
        p.word(parent+0x54,1);p.word(parent+0x60,table);p.word(table,child)
        p.word(child+0x18,oid);p.word(child+0x1c,parent);parent=child
    p.word(parent+0x54,2);p.word(parent+0x60,RAM+0x4100)
    components=[]
    for n,oid in enumerate((9094,9095)):
        node,table=RAM+0x4200+n*0x200,RAM+0x4300+n*0x200
        p.word(RAM+0x4100+4*n,node);p.word(node+0x18,oid);p.word(node+0x1c,parent)
        p.word(node+0x40,2);p.word(node+0x4c,table)
        for i,(plugin,props) in enumerate(((0xc2dff5f4,13),
            (0xc2e033e0,11) if n==0 else (0xc2e03b9c,8))):
            comp=RAM+0x5000+n*0x400+i*0x100
            p.word(table+4*i,comp);p.word(comp+0x18,plugin);p.word(comp+0x14,props)
            components.append(comp)
    return root,components


def frame_scene(p, root):
    magnify = p.words(p.words(root+0x60)[0])[0]
    p.word(root+0x54,2);p.word(root+0x60,RAM+0x6f00)
    p.word(RAM+0x6f00,magnify);p.word(RAM+0x6f04,RAM+0x7000)
    parent=root
    for i,oid in enumerate((8008,26,28)):
        node=RAM+0x7000+i*0x200
        p.word(node+0x18,oid);p.word(node+0x1c,parent)
        if i:
            p.word(parent+0x54,1);p.word(parent+0x60,parent+0x100)
            p.word(parent+0x100,node)
        parent=node
    p.word(parent+0x54,3);p.word(parent+0x60,RAM+0x7500)
    for i,oid in enumerate((29,30,31)):
        node=RAM+0x7600+i*0x200
        p.word(RAM+0x7500+i*4,node);p.word(node+0x18,oid);p.word(node+0x1c,parent)
        p.word(node+0x40,3);p.word(node+0x4c,node+0x100)
        for j in (1,2):
            comp=RAM+0x9000+i*0x400+j*0x100
            p.word(node+0x100+j*4,comp);p.word(comp+0x18,0xc2e033e0)
            p.word(comp+0x14,11)
