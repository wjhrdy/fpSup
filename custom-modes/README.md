# Custom modes — Indoor (IN)

**SIGMA fp firmware 5.02.** A saved stills P preset named **Indoor** immediately
selects the camera's native 60 Hz compensation program, without waiting for
flicker detection. With a non-electronic manual lens, a white **BANDING RISK**
label on a red background warns when the native selected shutter becomes too
fast for the compensation target.

[Download Indoor 0.3.0 for fpSup-Merge](Indoor-v0.3.0-Merge-Sigma-fp-5.02.zip).
This is an ordinary merge input containing **only Indoor**. USB Shell, LV Boost
and Fast Start 2 are not bundled; select them separately in Merge if wanted.
It uses the existing BIN-upload workflow rather than a built-in catalogue tile.

## Install with fpSup-Merge

1. Extract the ZIP and upload its **fpSup.BIN** to
   [fpSup-Merge](https://ijigen.github.io/fpSup/tools/card-composer/), or use
   [the local merger](../tools/card-composer/index.html).
2. Select any other mods and enable Fast Start 2 if wanted.
3. Download Merge's ZIP and copy its **AutoRun.txt**, **fpSup.BIN**, and
   **FPSUPUI** folder to the SD card root, preserving your existing files first.

This input's AutoRun.txt and fpSup.BIN also support ordinary standalone loading.
Do not upload an already-Fast combined BIN or combine Indoor with another
flicker/BF exposure experiment. The merger cannot detect every runtime hook
conflict, especially with other uploaded mods.

## Save and select Indoor

In STILL, select **P**, choose your preferred settings, and save to any C1–C6
slot through **SYSTEM → Custom Mode Setting**. On the Mode selection screen,
highlight that slot and press **AEL** to set its full name to **Indoor** and
short abbreviation to **IN**. Select that slot afterward. The native workflow
is in the [fp manual, pages 106–108](https://www.sigma-global.com/en/support/download/fp_Manual_FW_Ver.5.0_EN_2.pdf).

The full name activates Indoor: case does not matter, but extra spaces and
suffixes do. IN is cosmetic. No slot is reserved or renamed automatically.
Ordinary P, differently named slots, A/S/M, CINE and program shift use the stock
classification getter. No exposure-menu setting is added by this version.

## Compensation and warning

Indoor returns the native effective classification **2 (60 Hz)** while eligible.
The native firmware chooses the exposure, aperture and ISO; this version does
not insert a custom shutter family, replace the exposure solver, or run a new
light detector. Native limits and bright-scene escape behavior remain intact.
It commonly settles near the reported displayed **1/125** with aperture control.
The native internal compensation target is approximately **1/120** (Tv=7073,
APEX ×1024); the warning compares this internal value rather than a UI label.

**BANDING RISK** appears during STILL live view when:

- Indoor is active in P with no program shift;
- the native aperture driver is NoLensIris, as with an ordinary non-electronic
  manual lens;
- the native selected shutter is faster than the 1/120 compensation target.

It clears when the shutter slows to that target or below, an electronic
aperture driver is selected, or Indoor/live-view eligibility ends. The warning
is a timing-risk indication, not measured bands. It does not classify slower
off-cycle exposures or adapters reporting electronic iris control despite a
manual aperture. Absence of a warning does not guarantee flicker-free images;
arbitrary LED PWM can require different timing.

## Build and verification

Requires Python 3 and Clang with ARM target support. Tests additionally require
Unicorn and Node.js. Place extracted fp 5.02 images at
`../out/MAIN_c0000000.bin` and `../out/seg1_c2ef6e00.bin`, relative to the
repository root, matching the shared loader emulator. Firmware is not included.

```sh
python3 -B custom-modes/build_indoor.py --out /tmp/indoor-new
python3 -B custom-modes/test_indoor.py
node custom-modes/test_merge.js /tmp/indoor-new/fpSup.BIN
```

Use a fresh output directory. The ordinary builder uses the shared loader with
`--no-shell`; Fast builds are exercised only by the tests and final Merge
packaging. The previous custom-family `--tv60` calibration option is removed.
See [VERIFICATION.md](VERIFICATION.md) and SHA256SUMS for exact artifact hashes
and offline results. The ZIP includes its card-file hashes and manifest.

The user reported the native Indoor/manual-lens warning behavior working on
camera. The corrected red-background palette and this exact standalone merge
package are checked offline and have not been separately hardware-validated.
OS/file/heap/cache/lock services are mocked; composition checks for other mods
do not execute all of those mods' resident code. Photo capture and repeated
physical power-cycle checks remain separate from the emulator results.

## Implementation

`indoor.S` wraps the effective flicker getter at **0xC0210118** and reads the
saved custom-slot name using native DialMode/name property accessors. Eligible
Indoor returns 2; other modes tail into the displaced stock getter. Native
program model generation and interpolation remain unchanged.

The display hook at **0xC052884C** reads native selected Tv at **0xC3202C78** and
the iris-driver selector at **0xC347B1D4**, independently of manual-focus status.
It makes no lens-driver calls, property-lock calls or exposure writes in the
draw thread. The native simple-font bitmap is inverted: zero bits form white
glyphs (palette 1), one bits form the red background (palette 3). The fixed
192×32 rectangle at (400,64) is cleared separately on each of three OSD buffers.
Native observers draw afterward.

Resident code/state live in owned heap, with short veneers in the shared cave.
Stock-word sections let the shared loader journal and restore both runtime
hooks and clean up the older Indoor/BF experimental hooks. No new persistent
setting, detector-state write, task or private loader is added. Optional Fast
Start 2 retains the shared loader's existing persistent-settings behavior.
