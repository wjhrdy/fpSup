# Custom modes — Indoor (IN)

Experimental **SIGMA fp firmware 5.02** mod. A custom stills P preset named
**Indoor** selects shutter times matched to 60 Hz lighting, without waiting
for flicker detection. Use **IN** for the preset's two-letter abbreviation.

[Download Indoor 0.2 for fpSup-Merge](Indoor-v0.2-Merge-Sigma-fp-5.02.zip).
This is an ordinary input, with no bundled Shell or Fast Start 2. It follows
the repository's experimental BIN-upload workflow; it is not a built-in
catalogue tile or a hardware-validated release.

## Install with fpSup-Merge

1. Extract the ZIP and upload its **fpSup.BIN** to
   [fpSup-Merge](https://ijigen.github.io/fpSup/tools/card-composer/), or open
   [the local merger](../tools/card-composer/index.html) in your browser.
2. Select the other mods you need. Enable **Fast Start 2** there if wanted.
3. Download Merge's ZIP. Copy its complete **AutoRun.txt**, **fpSup.BIN** and
   **FPSUPUI** folder to the card root.

Use that complete output when migrating from an earlier standalone Fast build.
Do not upload an already-Fast BIN or combine this with another flicker/BF
exposure experiment. Additional uploaded mods are not covered by the catalogue
combination checks below. The merger cannot detect every runtime hook conflict.

For ordinary standalone loading, this input's AutoRun.txt and fpSup.BIN can be
used together; Fast and the loading-screen assets belong to final Merge output.

## Save and select Indoor

In STILL, select **P**, set your preferred aperture/ISO options, and save to a
C1–C6 slot through **SYSTEM → Custom Mode Setting**. On the Mode selection
screen, highlight that slot and press **AEL** to edit its full name to
**Indoor** and its short abbreviation to **IN**. Select that slot afterward.
The native workflow is in the [fp manual, pages 106–108](https://www.sigma-global.com/en/support/download/fp_Manual_FW_Ver.5.0_EN_2.pdf).

The full name is the switch: case does not matter, but extra spaces or suffixes
do. The abbreviation is cosmetic. Selecting ordinary P or a differently named
slot disables Indoor. Keep program shift at zero. A/S/M, CINE, flash programs
and unsupported native limits retain stock behavior. No new menu field or
automatic preset renaming is installed.

## Shutter family

Approximately **1/120, 1/60, 1/40, 1/30, 1/20, 1/15** seconds, then longer
matching times. The native program varies aperture/ISO within each shutter
plateau; native limits and compensation headroom determine which steps exist.
Fixed ISO uses aperture compensation. There is no detector timer or latched
60 Hz flag. Selection takes effect when the native program table is rebuilt.

1/120 targets light pulsing at 120 Hz on 60 Hz mains; it does not average a full
60 Hz light cycle. The camera's displayed label for that internal timing has
not been verified. Bright scenes can overexpose once aperture/ISO reach their
limits because this mode caps the fastest exposure at about 1/120. Switch to
ordinary P outdoors. Arbitrary LED PWM frequencies may need different timing.

## Build and verification

Requires Python 3 and Clang with the ARM target. Put your extracted fp 5.02
images at `../out/MAIN_c0000000.bin` and `../out/seg1_c2ef6e00.bin` relative to
the repository root, matching the shared emulator's layout. Firmware is not
included. Tests additionally require Unicorn and Node.js.

```sh
python3 -B custom-modes/build_indoor.py --out /tmp/indoor-new
python3 -B custom-modes/test_indoor.py
node custom-modes/test_merge.js /tmp/indoor-new/fpSup.BIN
```

Use a fresh output directory. `--tv60` retains the timing calibration knob
(default 6049 APEX ×1024); Indoor adds 1024 for its 1/120 base, 7073.
`SHA256SUMS` identifies the exact download. The ZIP also records its two card
file hashes. No new loader, stage2, worker, detector or BF solver is included.

Offline checks passed against the Merge catalogue at repository commit
`2233fe87c83af860526669a44831217ff63d01f0`:

- All 54 legal upload combinations: Indoor alone, Shell 3.3.0, either gyro
  1.14.0 edition, either OG3K 0.2.6a or OG2K 0.1.3a, normal/Fast, EP83 off/on.
  Maximum used size: 35,812 of 61,440 bytes. Launcher bytes and entry relocation
  are checked in the actual page's composer, with unchanged AutoRun per mode.
- Actual ARM program generation and interpolation across 12 native models,
  fixed/Auto ISO, brightness sweeps, transition boundaries and timing conversion.
- All six slots, both settings banks and dial fields, exact case-insensitive
  naming, entry/exit on one running instance, mode guards and mutation checks.
- Actual Merge-generated Indoor-only outputs execute under emulation through
  normal, cold Fast and warm Fast startup, apply the family, exit to ordinary P,
  and restore the five current/legacy hook sites at shutdown.

The three test methods cover these matrices. OS/file/heap/cache/lock services
are mocked. Other mods' resident code is not executed by the combination
matrix. Sensor behavior, capture completion and physical power-cycle testing
remain pending; no card was written during this work. First camera checks:
take and save photos at several shutter steps, switch Indoor ↔ ordinary P,
then verify the saved preset and repeated normal shutdown/startup cycles.

## Implementation

`indoor.S` wraps the program builder call at `0xC021EE94`. It repairs the fixed
shutter curve and adds equal-brightness transitions, so native interpolation
never ramps between matching shutter times. Code lives in owned heap and uses
one 8-byte veneer from the shared cave allocator. Stock-word sections let the
shared loader journal and restore runtime patches and clear older experiments.

The native DialMode storage accessor `0xC00B4BE8` selects the settings bank and
dial field. Values 4–9 map to C1–C6. `0xC00B7EB0` reads the explicit slot's saved
long name. This gate is checked on each eligible program build; there is no
remembered result. The mod reads native settings without adding a persistent
field; optional Fast Start 2 retains the shared loader's existing persistent
settings behavior.
