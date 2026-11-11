.syntax unified
.arm
.text
.global entry
entry:
    push {r4-r8, lr}
    sub sp, sp, #8
    mov r4, r1
    adr r5, claims
    mov r6, #CLAIM_COUNT
    mov r7, #2                     @ SL_EXCL
    str r7, [sp]                   @ fifth argument to claim()
1:  mov r0, r4
    ldr r1, [r5], #4
    mov r2, #4
    mov r3, r5
    ldr ip, [r4, #8]              @ svc->claim
    blx ip
    cmp r0, #0
    bne 2f                        @ v4 rolls back earlier claims on release
    add r5, r5, #4
    subs r6, r6, #1
    bne 1b

    adr r0, install
    mov r1, r4
    blx r0
    adr r5, claims
    ldm r5, {r1, r2}
    ldr r1, [r1]                  @ first record is an install sentinel
    cmp r1, r2
    movne r0, #0                  @ SL_KEEP
    bne 3f
2:  mov r0, #1                    @ SL_RELEASE
3:  add sp, sp, #8
    pop {r4-r8, pc}

claims:
    .incbin CLAIM_FILE
install:
    .incbin INSTALL_FILE
