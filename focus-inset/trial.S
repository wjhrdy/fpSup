.syntax unified
.arm
.fpu vfpv3
.text
.global entry
.macro LDA reg, value
 movw \reg, #:lower16:\value
 movt \reg, #:upper16:\value
.endm
.macro REL reg, target
 movw \reg, #:lower16:(\target-99f-8)
 movt \reg, #:upper16:(\target-99f-8)
99: add \reg, pc, \reg
.endm
.macro CORE offset
 /* Larger resident adapters can exceed ARM ADR's immediate range. */
 adr ip, 99f
 movw lr, #:lower16:(core-99f)
99:
 add ip, ip, lr
 movw lr, #\offset
 add ip, ip, lr
 blx ip
.endm
entry:
 push {r4-r10,lr}
 mov r8, sp
 bic sp, sp, #7
 sub sp, sp, #16
 adr r4, hooks
 mov r9, #HOOK_COUNT
1:
 ldr r0, [r4]
 ldr r1, [r4,#4]
 ldr r0, [r0]
 cmp r0,r1
 bne done
 add r4,r4,#16
 subs r9,r9,#1
 bne 1b
 LDA r6, 0xc072e060
 ldr r5,[r6]
 tst r5,#3
 bne done
 LDA r0, 0xc072e064
 cmp r5,r0
 blo done
 LDA r0, (0xc072efb4-HOOK_COUNT*8)
 cmp r5,r0
 bhi done
 mov r0,sp
 mov r1,#0
 movw r2,#:lower16:(resident_end-resident)
 mov r3,#0
 LDA ip,0xc001d740
 blx ip
 mov r0,sp
 LDA ip,0xc001d7f0
 blx ip
 cmp r0,#0
 beq done
 mov r7,r0
 adr r1,resident
 movw r2,#:lower16:((resident_end-resident)/4)
2:
 ldr r3,[r1],#4
 str r3,[r0],#4
 subs r2,r2,#1
 bne 2b
 adr r4,hooks
 mov r9,#HOOK_COUNT
 mov r10,r5
3:
 ldr r0,[r4,#12]
 cmp r0,#3
 LDA r0,0xe51ff004
 movweq r0,#0xf8df
 movteq r0,#0xf000
 str r0,[r10],#4
 ldr r0,[r4,#8]
 add r0,r7,r0
 str r0,[r10],#4
 add r4,r4,#16
 subs r9,r9,#1
 bne 3b
 str r10,[r6]
 LDA ip,0xc000e91c
 blx ip
 LDA ip,0xc000eabc
 blx ip
 adr r4,hooks
 mov r9,#HOOK_COUNT
4:
 ldr r1,[r4]
 ldr r2,[r4,#12]
 cmp r2,#2
 beq pointer
 cmp r2,#3
 beq thumb_branch
 sub r0,r5,r1
 sub r0,r0,#8
 asr r0,r0,#2
 bic r0,r0,#0xff000000
 cmp r2,#0
 orreq r0,r0,#0xeb000000
 orrne r0,r0,#0xea000000
 b arm
pointer:
 ldr r0,[r4,#8]
 add r0,r7,r0
 b arm
thumb_branch:
 /* Current Thumb sites are below the cave by less than 8 MiB. */
 sub r0,r5,r1
 sub r0,r0,#4
 ubfx r2,r0,#12,#10
 movw r3,#0xf000
 orr r2,r2,r3
 ubfx r3,r0,#22,#1
 ubfx r0,r0,#1,#11
 eor r0,r0,r3,lsl #11
 eor r0,r0,#0xb800
 orr r0,r2,r0,lsl #16
arm:
 str r0,[r1]
 add r5,r5,#8
 add r4,r4,#16
 subs r9,r9,#1
 bne 4b
 LDA ip,0xc000e91c
 blx ip
 LDA ip,0xc000eabc
 blx ip
done:
 mov sp,r8
 pop {r4-r10,pc}
.balign 4
hooks:
#include HOOK_TABLE
resident:
initial_crop:
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 sub sp,sp,#32
 vpush {d0-d7}
 vmrs r4,fpscr
 add r0,sp,#64
 ldr r1,[r8]
 CORE INITIAL_CROP_OFF
 mov r5,r0
 vmsr fpscr,r4
 vpop {d0-d7}
 cmp r5,#0
 moveq r0,r8
 ldreq r0,[r0]
 movne r0,sp
 LDA ip,0xc042a178
 blx ip
 mov sp,r8
 add sp,sp,#16
 pop {r4-r8,pc}
peaking:
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 adr ip,peaking_native
 blx ip
 /* Preserve the native return and caller VFP state around the lens query. */
 mov r6,r0
 vpush {d0-d7}
 vmrs r4,fpscr
 ldr r0,[r8]
 ldr r1,[r8,#8]
 CORE PEAKING_OFF
 vmsr fpscr,r4
 vpop {d0-d7}
 mov r0,r6
 mov sp,r8
 add sp,sp,#16
 pop {r4-r8,pc}
peaking_native:
 push {r4-r9,r11,lr}
 LDA ip,0xc0305b9c
 bx ip
controls:
 /* Native variable dispatch has five arguments; forward its stack argument. */
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 sub sp,sp,#8
 ldr ip,[r8,#40]
 str ip,[sp]
 adr ip,controls_native
 orr ip,ip,#1
 blx ip
 mov r6,r0
 vpush {d0-d7}
 vmrs r4,fpscr
 REL r5,diagnostic
 ldr r0,[r8]
 cmp r0,#0
 ldrne r0,[r0,#0x84c]
 CORE CONTROLS_OFF
 ldr r1,[r5,#248]
 add r1,r1,#1
 str r1,[r5,#248]
 cmp r0,#1
 ldreq r1,[r5,#252]
 addeq r1,r1,#1
 streq r1,[r5,#252]
 vmsr fpscr,r4
 vpop {d0-d7}
 mov r0,r6
 mov sp,r8
 add sp,sp,#16
 pop {r4-r8,pc}
.thumb
controls_native:
 push.w {r4-r11,lr}
 ldr.w pc,controls_cont
.balign 4
controls_cont: .word 0xc05dc17d
.arm
visible:
 /* Keep the original null guard and effective-visibility ancestor walk. */
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 adr ip,visible_native
 orr ip,ip,#1
 blx ip
 mov r6,r0
 vpush {d0-d7}
 vmrs r4,fpscr
 REL r5,diagnostic
 mov r1,r0
 ldr r0,[r8]
 CORE VISIBLE_OFF
 ldr r2,[r5,#240]
 add r2,r2,#1
 str r2,[r5,#240]
 cmp r0,r6
 ldrne r2,[r5,#244]
 addne r2,r2,#1
 strne r2,[r5,#244]
visible_exit:
 vmsr fpscr,r4
 vpop {d0-d7}
 mov sp,r8
 add sp,sp,#16
 pop {r4-r8,pc}
.thumb
visible_native:
 cmp r0,#0
 it eq
 bxeq lr
 ldr.w pc,visible_cont
.balign 4
visible_cont: .word 0xc05d028f
.arm
transition:
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 ldr r7,[r0,#4]
 cmp r7,#0
 ldrne r7,[r7]
 adr ip,transition_native
 blx ip
 mov r6,r0
 vpush {d0-d7}
 vmrs r4,fpscr
 REL r5,diagnostic
 ldr r0,[r5,#224]
 add r0,r0,#1
 str r0,[r5,#224]
 str r7,[r5,#232]
 ldr r0,[r8]
 mov r1,r7
 CORE REFRESH_OFF
 ldr r1,[r5,#228]
 add r1,r1,r0
 str r1,[r5,#228]
 ldr r0,[r8]
 ldr r0,[r0,#4]
 cmp r0,#0
 ldrne r0,[r0]
 str r0,[r5,#236]
 vmsr fpscr,r4
 vpop {d0-d7}
 mov r0,r6
 mov sp,r8
 add sp,sp,#16
 pop {r4-r8,pc}
transition_native:
 push {r4-r7,lr}
 ldr pc,transition_cont
transition_cont: .word 0xc0481a0c
preview:
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 LDA ip,0xc0436b80
 blx ip
 mov r6,r0
 vpush {d0-d7}
 vmrs r4,fpscr
 REL r5,diagnostic
 ldr r0,[r5,#208]
 add r0,r0,#1
 str r0,[r5,#208]
 ldm r8,{r0-r3}
 CORE PREVIEW_OFF
 str r0,[r5,#212]
 /* Preserve the first eight startup preparations before USB/menu actions
  * rebuild them. Read-only snapshots in this allocation, never file I/O. */
 ldr r0,[r5,#208]
 cmp r0,#8
 bhi preview_logged
 sub r1,r0,#1
 add r7,r5,#256
 add r7,r7,r1,lsl #8
 str r0,[r7],#4
 ldr r1,[r8,#4]
 str r1,[r7],#4
 mov r2,#22
preview_log_out:
 ldr r3,[r1],#4
 str r3,[r7],#4
 subs r2,r2,#1
 bne preview_log_out
 ldr r1,[r8,#8]
 add r1,r1,#0x580
 add r1,r1,#12
 mov r2,#15
preview_log_common:
 ldr r3,[r1],#4
 str r3,[r7],#4
 subs r2,r2,#1
 bne preview_log_common
 LDA r1,0xc31e11e8
 mov r2,#18
preview_log_pip:
 ldr r3,[r1],#4
 str r3,[r7],#4
 subs r2,r2,#1
 bne preview_log_pip
 LDA r1,0xc31e10f4
 mov r2,#7
preview_log_main:
 ldr r3,[r1],#4
 str r3,[r7],#4
 subs r2,r2,#1
 bne preview_log_main
preview_logged:
 vmsr fpscr,r4
 vpop {d0-d7}
 mov r0,r6
 mov sp,r8
 add sp,sp,#16
 pop {r4-r8,pc}
crop:
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 vpush {d0-d7}
 vmrs r4,fpscr
 REL r5,diagnostic
 ldr r0,[r5,#216]
 add r0,r0,#1
 str r0,[r5,#216]
 cmp r0,#1
 bne crop_logged
 LDA r1,0xc375d844
 ldr r1,[r1]
 str r1,[r5]
 ldr r1,[r8,#28]             /* native r7 = current output params + 8 */
 str r1,[r5,#4]
crop_logged:
 ldr r0,[r8,#4]
 CORE CROP_OFF
 str r0,[r8,#4]
 str r0,[r5,#220]
 vmsr fpscr,r4
 vpop {d0-d7}
 mov sp,r8
 pop {r0-r8,lr}
 LDA ip,0xc030cc90
 bx ip
layout:
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 vpush {d0-d7}
 vmrs r4,fpscr
 REL r5,diagnostic
 /* Native variable listeners run before the property-dispatch mutex is
  * acquired. Property setters may notify listeners; skip recursive entry. */
 ldr r0,[r5,#196]
 cmp r0,#0
 bne layout_exit
 mov r0,#1
 str r0,[r5,#196]
 ldr r0,[r5,#164]
 add r0,r0,#1
 str r0,[r5,#164]
 ldr r0,[r8]
 cmp r0,#0
 ldrne r0,[r0,#0x84c] /* Listener receives the app; resolve its active screen. */
 cmp r0,#0
 ldrne r0,[r0,#12]
 str r0,[r5,#168]
 CORE LAYOUT_OFF
 str r0,[r5,#172]
 mov r0,#0
 str r0,[r5,#196]
layout_exit:
 vmsr fpscr,r4
 vpop {d0-d7}
 mov sp,r8
 pop {r0-r8,lr}
 adr ip,layout_native
 orr ip,ip,#1
 bx ip
.thumb
layout_native:
 push {r4-r6,lr}
 mov r5,r1
 ldr.w pc,layout_cont
.balign 4
layout_cont: .word 0xc05d9f95
.arm
submit:
 push {r4-r10,lr}
 mov r8,sp
 bic sp,sp,#7
 mov r5,r0
 REL r4,diagnostic
 ldr r0,[r4,#176]
 add r0,r0,#1
 str r0,[r4,#176]
 ldr r0,[r5]
 str r0,[r4,#180]
 /* Bank 3 carries the live preview ring on this camera. Capture its input
  * only: no live picture descriptor is changed by this trial. */
 cmp r0,#3
 bne 6f
 add r0,r4,#8
 mov r1,r5
 mov r6,#39
5:
 ldr r2,[r1],#4
 str r2,[r0],#4
 subs r6,r6,#1
 bne 5b
6:
submit_stock:
 mov r0,r5
 adr ip,submit_native
 orr ip,ip,#1
 blx ip
 mov sp,r8
 pop {r4-r10,pc}
.thumb
submit_native:
 push {r4-r7,lr}
 sub sp,#0xac
 ldr.w pc,submit_cont
.balign 4
submit_cont: .word 0xc00e9c25
.arm
.balign 4
picture:
 push {r0-r8,lr}
 mov r8,sp
 bic sp,sp,#7
 vpush {d0-d7}
 vmrs r4,fpscr
 sub sp,sp,#56
 mov r6,sp
 REL r5,diagnostic
 ldr r0,[r5,#200]
 add r0,r0,#1
 str r0,[r5,#200]
 mov r0,r6
 ldr r1,[r8]
 ldr r2,[r8,#4]
 ldr r3,[r8,#8]
 CORE PICTURE_OFF
 str r0,[r5,#204]
 ldr r0,[r5,#200]
 cmp r0,#1
 bne picture_logged
 add r7,r5,#2304
 ldr r1,[r8,#8]
 mov r2,#14
picture_log_input:
 ldr r3,[r1],#4
 str r3,[r7],#4
 subs r2,r2,#1
 bne picture_log_input
 mov r1,r6
 mov r2,#14
picture_log_output:
 ldr r3,[r1],#4
 str r3,[r7],#4
 subs r2,r2,#1
 bne picture_log_output
 LDA r1,0xc3033a84
 mov r2,#16
picture_log_applied:
 ldr r3,[r1],#4
 str r3,[r7],#4
 subs r2,r2,#1
 bne picture_log_applied
picture_logged:
 /* Additional lens query cannot alter incoming VFP/FPSCR inputs. */
 add sp,sp,#56
 vmsr fpscr,r4
 vpop {d0-d7}
 sub sp,sp,#120 /* Keep the local descriptor below the native call stack. */
 ldr r0,[r8]
 ldr r1,[r8,#4]
 mov r2,r6
 ldr r3,[r8,#12]
 LDA ip,0xc01d69d1
 blx ip
 mov sp,r8
 add sp,sp,#16
 pop {r4-r8,pc}
.balign 4
diagnostic: .space 2480
.balign 4
core:
.incbin CORE_FILE
.balign 4
resident_end:
