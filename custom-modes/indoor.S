.syntax unified
.arm
.text
.global entry
.macro LDA reg, value
    movw \reg, #:lower16:\value
    movt \reg, #:upper16:\value
.endm
.equ SITE, 0xC0210118
.equ NATIVE, 0xC0224E70
.equ DRAW_SITE, 0xC052884C
.equ RESULT_SITE, 0xC02100E4
/* Run in staging; only the resident portion survives the entry's return. */
entry:
    push {r4-r8, lr}
    mov r8, sp
    bic sp, sp, #7
    sub sp, sp, #16
    LDA r4, SITE
    ldr r0, [r4]
    LDA r1, 0xE92D4010
    cmp r0, r1
    bne done
    LDA r0, RESULT_SITE
    ldr r0, [r0]
    LDA r1, 0xEB000173
    cmp r0, r1
    bne done
    LDA r0, DRAW_SITE
    ldr r0, [r0]
    LDA r1, 0xE1A03000
    cmp r0, r1
    bne done
    LDA r6, 0xC072E060
    ldr r5, [r6]
    tst r5, #3
    bne done
    LDA r0, 0xC072E064
    cmp r5, r0
    blo done
    LDA r0, 0xC072EF8C
    cmp r5, r0
    bhi done
    mov r0, sp
    mov r1, #0
    movw r2, #:lower16:(resident_end-resident)
    mov r3, #0
    LDA ip, 0xC001D740
    blx ip
    mov r0, sp
    LDA ip, 0xC001D7F0
    blx ip
    cmp r0, #0
    beq done
    mov r7, r0
    adr r1, resident
    movw r2, #:lower16:((resident_end-resident)/4)
copy:
    ldr r3, [r1], #4
    str r3, [r0], #4
    subs r2, r2, #1
    bne copy
    LDA r0, 0xE51FF004
    str r0, [r5]
    str r7, [r5, #4]
    str r0, [r5, #8]
    movw r1, #:lower16:(draw-resident)
    add r1, r7, r1
    str r1, [r5, #12]
    add r0, r5, #16
    str r0, [r6]
    LDA ip, 0xC000E91C
    blx ip
    LDA ip, 0xC000EABC
    blx ip
    sub r0, r5, r4
    sub r0, r0, #8
    asr r0, r0, #2
    bic r0, r0, #0xFF000000
    orr r0, r0, #0xEA000000
    str r0, [r4]
    LDA r4, DRAW_SITE
    add r0, r5, #8
    sub r0, r0, r4
    sub r0, r0, #8
    asr r0, r0, #2
    bic r0, r0, #0xFF000000
    orr r0, r0, #0xEB000000
    str r0, [r4]
    LDA ip, 0xC000E91C
    blx ip
    LDA ip, 0xC000EABC
    blx ip
done:
    mov sp, r8
    pop {r4-r8, pc}
/* Override only the effective classification. No writes to detector state,
 * settings, AE tables, selected exposures or sensor timing. Native exposure
 * selection remains intact; ordinary P / other modes use the original getter.
 */
resident:
    push {r4-r8, lr}
    mov r8, sp
    bic sp, sp, #7
    mov r4, r0
    adr r5, active
    mov r0, #0
    str r0, [r5]
    LDA r0, 0xC3202CF0
    ldr r0, [r0]
    cmp r0, #0
    bne stock
    LDA r0, 0xC3202CB4
    ldr r0, [r0]
    cmp r0, #2
    bne stock
    LDA r0, 0xC3202D00
    ldr r0, [r0]
    cmp r0, #0
    bne stock
    bl indoor_selected
    cmp r0, #0
    beq stock
    str r0, [r5] @ retain native classification: 1=50 Hz, 2=60 Hz
    mov sp, r8
    pop {r4-r8, pc}
stock:
    mov r0, r4
    mov sp, r8
    pop {r4-r8, lr}
    push {r4, lr} @ displaced stock instruction
    LDA ip, 0xC021011C
    bx ip
indoor_selected:
    push {r4-r6, lr}
    LDA r0, 0xC31CAA80
    ldr r4, [r0]
    cmp r4, #0
    beq indoor_no
    mov r1, r4
    mov r0, #0
    LDA ip, 0xC00B4BE8 @ raw DialMode property pointer
    blx ip
    adr r1, dial_watch
    str r0, [r1]
    ldr r0, [r0]
    str r0, [r1, #4]
    sub r0, r0, #4 @ C1..C6 = DialMode 4..9
    cmp r0, #5
    bhi indoor_no
    mov r1, r4
    LDA ip, 0xC00B7EB0 @ saved long name for explicit slot 0..5
    blx ip
    adr r1, name_watch
    str r0, [r1]
    bl match_name
    pop {r4-r6, pc}
indoor_no:
    mov r0, #0
    pop {r4-r6, pc}
/* Pure string parser, shared with the OSD thread. No property/driver calls.
 * Exact case-insensitive Indoor (legacy 60), Indoor60, or Indoor50 only.
 */
match_name:
    adr r1, indoor_name
name_compare:
    ldrb r2, [r1], #1
    ldrb r3, [r0], #1
    cmp r2, #0
    beq name_suffix
    orr r3, r3, #0x20
    cmp r2, r3
    beq name_compare
name_no:
    mov r0, #0
    bx lr
name_suffix:
    cmp r3, #0
    moveq r0, #2
    bxeq lr
    mov r2, #2
    cmp r3, #'6'
    beq name_digits
    cmp r3, #'5'
    bne name_no
    mov r2, #1
name_digits:
    ldrb r3, [r0], #1
    cmp r3, #'0'
    bne name_no
    ldrb r3, [r0]
    cmp r3, #0
    bne name_no
    mov r0, r2
    bx lr
indoor_name:
    .asciz "indoor"
    .balign 4
.balign 4

/* Reuse the native OSD renderer; warning concerns fast-shutter risk, not
 * measured bands. Native exposure selection and all camera settings unchanged.
 * ponytail: fast-shutter risk only; slower off-cycle exposures need a
 * separately verified timing policy.
 */
draw:
    push {r0-r12, lr}
    mrs r4, APSR
    mov r8, sp
    bic sp, sp, #7
    sub sp, sp, #48
    cmp r5, #1
    bne draw_return
    cmp r0, #0
    beq draw_return
    ldr r1, [r0]               @ native descriptor: format, pixels, dimensions
    cmp r1, #3                 @ indexed 8bpp only (native c052b550 dispatch)
    bne draw_return
    ldr r6, [r0, #4]
    cmp r6, #0
    beq draw_return
    ldr r1, [r0, #8]
    cmp r1, #0
    beq draw_return
    ldr r7, [r1]
    movw r2, #592
    cmp r7, r2
    blo draw_return
    cmp r7, #4096
    bhi draw_return
    ldr r2, [r1, #4]
    cmp r2, #96
    blo draw_return
    cmp r2, #4096
    bhi draw_return
    str r6, [sp, #8]           @ native text context (16 bytes)
    str r7, [sp, #12]
    str r2, [sp, #16]
    mov r1, #3
    str r1, [sp, #20]
    mov r9, #0
    LDA r1, 0xC3033A44
    ldr r1, [r1]
    cmp r1, #2 @ native STILL app
    bne label_state
    LDA r1, 0xC3033A54
    ldr r1, [r1]
    cmp r1, #1 @ stable STILL live-view, not menu/playback/transition
    bne label_state
    LDA r1, 0xC3202CF0
    ldr r1, [r1]
    cmp r1, #0
    bne label_state
    LDA r1, 0xC3202CB4
    ldr r1, [r1]
    cmp r1, #2
    bne label_state
    LDA r1, 0xC3202D00
    ldr r1, [r1]
    cmp r1, #0
    bne label_state
    adr r1, active
    ldr r1, [r1]
    cmp r1, #1
    blo label_state
    cmp r1, #2
    bhi label_state
    mov r11, r1
    adr r1, dial_watch
    ldm r1, {r2,r3}
    cmp r2, #0
    beq label_state
    ldr r1, [r2]
    cmp r1, r3
    bne label_state
    adr r1, name_watch
    ldr r0, [r1]
    bl match_name
    cmp r0, r11 @ suppress stale classification during a name change
    bne label_state
    @ Warn on actual selected timing, regardless of lens aperture control.
    @ Native AE may exceed the target when aperture/ISO limits are exhausted.
    @ Displayed native selected Tv (APEX x1024), refreshed by C021EF88.
    @ Match native displayed-speed rounding (C0228D48, C09125B4).
    @ Last 1/125 Tv is 7315; last 1/100 Tv is 6967.
    LDA r1, 0xC3202C78
    ldr r1, [r1]
    movw r2, #7315
    cmp r11, #1
    movweq r2, #6967
    cmp r1, r2
    movgt r9, #1
label_state:
    adr r10, painted
    mov r11, #3
find_buffer:
    ldr r1, [r10]
    cmp r1, r6
    beq have_buffer
    add r10, r10, #4
    subs r11, r11, #1
    bne find_buffer
    cmp r9, #0
    beq draw_return            @ never erase a surface we have not marked
    adr r10, painted
    mov r11, #3
find_empty:
    ldr r1, [r10]
    cmp r1, #0
    beq have_buffer
    add r10, r10, #4
    subs r11, r11, #1
    bne find_empty
    adr r10, painted          @ native surface set changed; forget one old address
have_buffer:
    mov r1, #0
    str r1, [r10]
    add r0, r6, r7, lsl #6
    add r0, r0, #400
    mov r2, #32
clear_row:
    mov r3, #192
clear_pixel:
    strb r1, [r0], #1
    subs r3, r3, #1
    bne clear_pixel
    add r0, r0, r7
    sub r0, r0, #192
    subs r2, r2, #1
    bne clear_row
    mov r0, #1
    strb r0, [r8, #81]         @ original sp+0x18+group1: compositor dirty flag
    cmp r9, #0
    beq draw_return
    str r6, [r10]
    mov r0, #400
    mov r1, #64
    mov r2, #192
    mov r3, #32
    add ip, sp, #24
    stm ip, {r0-r3}            @ rect
    mov r0, #1                 @ zero bitmap bits = white glyphs
    mov r1, #3                 @ one bitmap bits = red background
    str r0, [sp, #40]
    str r1, [sp, #44]
    add r0, sp, #40
    str r0, [sp]               @ fifth argument: text colors
    add r0, sp, #8
    mov r1, #0                 @ native simple font
    add r2, sp, #24
    adr r3, label
    LDA ip, 0xC0529CB8
    blx ip
draw_return:
    msr APSR_nzcvq, r4
    mov sp, r8
    pop {r0-r12, lr}
    mov r3, r0                 @ displaced instruction
    bx lr
.align 2
label: .asciz "BANDING RISK"
.align 2
painted: .space 12

.align 2
active: .word 0
dial_watch: .word 0, 0
name_watch: .word 0
resident_end:
