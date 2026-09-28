.syntax unified
.arm
.text
.global entry
.macro LDA reg, value
    movw \reg, #:lower16:\value
    movt \reg, #:upper16:\value
.endm
.equ SITE, 0xC021EE94
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
    LDA r1, 0xEB0017F5
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
    LDA r0, 0xC072EF94
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
    add r0, r5, #8
    str r0, [r6]
    LDA ip, 0xC000E91C
    blx ip
    LDA ip, 0xC000EABC
    blx ip
    sub r0, r5, r4
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
/* Wrap just the program-line builder call in c021ee28, not all its callers.
 * Native builder still owns aperture, ISO, metering and exposure warnings.
 * Indoor extends the repaired fixed-shutter curve with equal-BV transitions.
 */
resident:
    push {r4-r10, lr}
    mov r8, sp
    bic sp, sp, #7
    sub sp, sp, #8
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r9, #0 @ whether this call was constrained
    cmp r4, #0
    beq native
    LDA r0, 0xC3202CF0
    ldr r0, [r0]
    cmp r0, #0 @ stills only
    bne native
    ldr r0, [r4, #8]
gate_p:
    cmp r0, #2 @ M=1, P=2, A=3, S=4
    bne native
    ldr r0, [r4, #0x10]
    cmp r0, #0x10 @ ordinary non-flash program only
    bne native
    LDA r0, 0xC3202D00
    ldr r0, [r0]
    cmp r0, #0 @ shifted P remains stock
    bne native
    ldr r0, [r4, #0x70]
    cmp r0, #1 @ known monitor/acquisition paths only
    bhi native
    bl indoor_selected
    cmp r0, #0
    beq native
    movw r7, #(TV60 + 1024) @ 1/120 base; keep the existing 60 Hz calibration
check_bounds:
    ldr r0, [r4, #0xac]
    cmp r7, r0
    blt native
    ldr r0, [r4, #0xb0]
    cmp r7, r0
    bgt native
    ldr r0, [r4, #0x7c] @ native model has additional Tv limits
    cmp r0, #0
    beq native
    ldr r1, [r0, #4]
    cmp r7, r1
    blt native
    ldr r1, [r0, #8]
    cmp r7, r1
    bgt native
    ldr r1, [r0, #4]
    ldr r2, [r4, #0xac]
    cmp r1, r2
    movlt r1, r2
    str r1, [sp] @ retain original effective slow-shutter bound
    str r7, [r4] @ fixed Tv
    str r7, [r4, #0xac] @ lower and upper Tv bounds
    str r7, [r4, #0xb0]
    mov r0, #2
    str r0, [r4, #0x8c] @ native fixed-shutter flag
    mov r9, #1
native:
    mov r0, r4
    mov r1, r5
    mov r2, r6
    LDA ip, NATIVE
    blx ip
    cmp r9, #0
    beq returned
    cmp r0, #0
    bne returned
    /* Native aperture transitions can insert Tv ramps outside equal bounds.
     * Rebuild their BV BEFORE native interpolation: BV = Av + Tv + ND - Sv.
     * This allows the existing interpolator to vary Av/Sv at a fixed Tv.
     * No selected exposure or sensor register is overwritten afterward.
     */
    mov r9, r5
    mov r10, #100
points:
    ldr r0, [r9, #4]
    ldr r1, [r9, #12]
    orrs r2, r0, r1
    beq repaired
    str r7, [r9, #8]
    add r0, r0, r7
    sub r0, r0, r1
    ldr r1, [r9, #16]
    add r0, r0, r1
    str r0, [r9]
    add r9, r9, #28
    subs r10, r10, #1
    bne points
repaired:
    mov r0, r5
    LDA ip, 0xC0224D08 @ native monotonic program-table repair
    blx ip
    mov r0, r5
    ldr r1, [sp]
    mov r2, r7
    bl extend_family
    cmp r6, #0
    beq success
    mov r9, #0
ranges:
    mov r0, #0
    mov r1, r9
    mov r2, r5
    LDA ip, 0xC0220740
    blx ip
    str r0, [r6], #4
    mov r0, #1
    mov r1, r9
    mov r2, r5
    LDA ip, 0xC0220740
    blx ip
    str r0, [r6], #4
    add r9, r9, #1
    cmp r9, #4
    blo ranges
success:
    mov r0, #0
returned:
    mov sp, r8
    pop {r4-r10, pc}
/* Use the stock property storage accessors: they select the current settings
 * bank and STILL/CINE-linked dial field. Explicit slot index avoids the native
 * "current slot" fallback to C1 in ordinary P. No detector or sticky state.
 * ponytail: the saved name is the switch; add a menu field only if independent
 * naming becomes necessary. Stock name length is 16 characters plus NUL.
 */
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
    ldr r0, [r0]
    sub r0, r0, #4 @ C1..C6 = DialMode 4..9
    cmp r0, #5
    bhi indoor_no
    mov r1, r4
    LDA ip, 0xC00B7EB0 @ saved long name for explicit slot 0..5
    blx ip
    adr r1, indoor_name
indoor_compare:
    ldrb r2, [r1], #1
    ldrb r3, [r0], #1
    cmp r2, #0
    beq indoor_end
    orr r3, r3, #0x20 @ ASCII case folding for "indoor"
    cmp r2, r3
    beq indoor_compare
indoor_no:
    mov r0, #0
    pop {r4-r6, pc}
indoor_end:
    cmp r3, #0
    mov r0, #0
    moveq r0, #1
    pop {r4-r6, pc}
indoor_name:
    .asciz "indoor"
    .balign 4
/* Extend only the dark end of the native curve. Each shutter transition has
 * two equal-BV points; the native interpolator therefore never ramps Tv.
 * Within a plateau exactly ONE of Sv/Av changes, matching c0224b80's contract.
 * All storage is the caller's 100-point table, with a reserved zero terminator.
 * ponytail: sparse integer-cycle family (1,2,3,4,6,8,...); add denser steps only
 * if camera testing calls for them. No detector, display hook, or shared state.
 */
extend_family:
    push {r4-r11, lr}
    mov r4, r0
    mov r5, r1
    mov r10, r2
    ldr r6, [r4, #4] @ maximum Av seen in native curve
    ldr r7, [r4, #12] @ minimum Sv seen in native curve
    mov r9, #100
family_find_end:
    ldr r0, [r4, #4]
    ldr r1, [r4, #12]
    orrs r2, r0, r1
    beq family_found_end
    cmp r0, r6
    movgt r6, r0
    cmp r1, r7
    movlt r7, r1
    add r4, r4, #28
    subs r9, r9, #1
    bne family_find_end
    b family_done
family_found_end:
    cmp r9, #100
    beq family_done
    adr r8, family_offsets
family_next:
    cmp r9, #3 @ two points plus terminator
    blo family_done
    ldr r0, [r8], #4
    cmp r0, #0
    beq family_done
    sub r11, r10, r0
    cmp r11, r5
    blt family_done
    ldr r0, [r4, #-20] @ previous Tv
    sub r2, r0, r11 @ exposure increment in APEX units
    ldr r0, [r4, #-16] @ previous Sv
    sub r0, r0, r7
    cmp r0, r2
    movge r3, #12 @ compensate with ISO when there is room
    bge family_copy
    ldr r0, [r4, #-24] @ otherwise close aperture within native range
    sub r0, r6, r0
    cmp r0, r2
    blt family_done @ cannot make an exposure-balanced transition
    mov r3, #4
family_copy:
    mov ip, #0
family_copy_word:
    sub r1, r4, #28
    ldr r0, [r1, ip]
    str r0, [r4, ip]
    add r1, r4, #28
    str r0, [r1, ip]
    add ip, ip, #4
    cmp ip, #28
    blo family_copy_word
    str r11, [r4, #8]
    str r11, [r4, #36]
    ldr r0, [r4, r3]
    cmp r3, #12
    subeq r0, r0, r2
    addne r0, r0, r2
    str r0, [r4, r3] @ equal-BV start; Av/Sv endpoint stays native
    ldr r0, [r4]
    sub r0, r0, r2
    str r0, [r4, #28] @ lower-BV end of this plateau
    mov r0, #0
    str r0, [r4, #24] @ interpolation within each new plateau
    str r0, [r4, #52]
    add r4, r4, #56
    sub r9, r9, #2
    str r0, [r4, #4] @ next record is the native terminator
    str r0, [r4, #12]
    b family_next
family_done:
    pop {r4-r11, pc}
.align 2
family_offsets:
    /* round(1024*log2(n)), n=2,3,4,6,...,1536. */
    .word 1024,1623,2048,2647,3072,3671,4096,4695,5120,5719
    .word 6144,6743,7168,7767,8192,8791,9216,9815,10240,10839
    .word 11264,11863 @ preserve the earlier family's longest duration
    .word 0
resident_end:
