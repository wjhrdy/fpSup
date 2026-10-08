# Focus Inset for SIGMA fp 5.02

A small magnified preview stays in the upper-left corner in STILL live view
when the attached lens has no autofocus capability. Enter the camera's normal
non-fullscreen focus assist to move the sampled area, then leave it to resume
normal shooting with the inset still visible.

The window leaves room for the top and left icons. Its outline and the shared
selection rectangle use a light stroke. Focus peaking covers normal live view,
and entering or leaving adjustment refreshes the controls immediately. The
first fast boot initializes the zoom crop before drawing the inset.

## Download and install

The standalone **Focus-Inset-v0.1.0test-Merge-Sigma-fp-5.02.zip** is an ordinary
fpSup-Merge input. Use the updated **fpSup-Merge-v1.3.0test.html**
from the release downloads (save it and open it in a browser). Upload its `fpSup.BIN`
together with the Indoor and LV Boost Merge inputs; add Fast Start 3 once in
the final composer. The focus input contains neither Fast Start nor USB Shell.
It can also be used alone by copying its AutoRun.txt and fpSup.BIN to the SD root.

For a ready-to-use card with all three mods and Fast Start 3, download
**fpsup-indoor-lvboost-v1.3.0test.zip** from the
[fork's release](https://github.com/wjhrdy/fpSup/releases/tag/fpsup-indoor-lvboost-v1.3.0test).
Extract AutoRun.txt, fpSup.BIN and the complete FPSUPUI folder to the SD root.
The optional `-USB-Debug.zip` contains the exact combined card tested on camera.
Complete combined cards are not Merge inputs.

Only SIGMA **fp firmware 5.02** is supported, not fp L. The gate checks native
lens AF capability: an AF lens switched to MF does not enable this feature,
and a disconnected/non-electronic lens cannot be distinguished from no lens.
Native capture, CINE and explicitly fullscreen assist remain outside the mod.
STILL behavior was tested; no video behavior is claimed.

This is a test release. The user confirmed positioning, adjustment entry/exit,
peaking and the fast-start corruption fix on camera. The no-Shell package has
the same three payloads; its exact hardware boot is not separately confirmed.
Ten repeated non-recording power cycles and an older-card transition are still
unverified. Fast Start 3 stores its existing loader block; Focus Inset itself
uses volatile code/UI state and does not write camera preferences.

## Indoor and LV Boost controls

Indoor uses a saved STILL/P custom preset with the exact full name `Indoor60`
(or `Indoor`) for 60 Hz lighting, or `Indoor50` for 50 Hz. Save your preferred
STILL/P settings to a C slot in SYSTEM → Custom Mode Setting, then highlight
that slot on the Mode selection screen and press AEL to edit its full name.
Saving replaces that slot. The optional `IN` abbreviation alone does not
activate the mod. Avoid program shift. The warning appears faster than the
displayed 1/125 in 60 Hz mode, or faster than 1/100 in 50 Hz mode; it warns
about shutter timing rather than detecting bands in the image.

Select LV Boost from the COLOR menu for the preview-only exposure lift. See
[LV Boost controls](../color-modes/lv-boost/README.md) for its existing controls.

## Build and verify

Use Python 3, Clang with ARM target support and the shared builder's existing
assembler dependencies. Offline tests also require Unicorn and Capstone.
Place the extracted, unmodified firmware at `../out/MAIN_c0000000.bin`, following
this repository's existing test layout. Do not commit the firmware.

```sh
python3 -B focus-inset/build_focus_inset.py --firmware ../out/MAIN_c0000000.bin --output out/focus-build
python3 -B focus-inset/test_trial.py out/focus-build
python3 -B focus-inset/test_initial_crop.py out/focus-build
python3 -B focus-inset/test_peaking.py out/focus-build
node focus-inset/test_merge.js out/focus-build/fpSup.BIN
python3 -B custom-modes/build_indoor.py --out out/indoor-build
node focus-inset/build_combined.js out/focus-build out/combined-build out/indoor-build/fpSup.BIN PATH_TO_LV_MERGE/fpSup.BIN
python3 -B focus-inset/test_combined.py out/combined-build/card out/combined-build/ordinary out/combined-build/debug out/combined-build/fast-debug --focus-directory out/focus-build
python3 -B focus-inset/test_warning_order.py out/combined-build/card
python3 -B focus-inset/test_packaging.py out/combined-build/card
```

The position-independent initializer owns its resident allocation and returns.
All ten hook words are separately declared for the shared shutdown journal;
code publication precedes arming hooks. Local descriptor/controller copies
leave saved preferences intact. The ELF extractor is the existing research
helper, retained unchanged to reject relocations and unsupported data sections.
Small RAM-only startup snapshots remain in this camera-tested module; they
perform no file I/O and are not exported automatically.

See [VERIFICATION.md](VERIFICATION.md) for the exact payload and card hashes.

Package: fpsup-indoor-lvboost-v1.3.0test
