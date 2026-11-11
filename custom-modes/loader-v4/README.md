# Indoor + LV Boost for Loader v4

[Download v1.4.0test](https://github.com/wjhrdy/fpSup/releases/tag/fpsup-indoor-lvboost-v1.4.0test)
for **SIGMA fp firmware 5.02** (not fp L).

- **Merge v4 ZIP:** extract `Indoor_v0.4.5.BIN` and `LV-Boost_v0.6.1.BIN`.
  Add either or both with **Add a .BIN** in the
  [current fpSup Merge page](https://ijigen.github.io/fpSup/tools/card-composer/).
  Select the compatible modules you want, then download the card from Merge.
- **Loader v4 Fast Start ZIP:** ready-to-use Indoor + LV Boost with **Instant Start**
  and **Fast Start** enabled. Upstream calls these options Instant Start and
  Fast Start on Loader v4; it does not call the option “Fast Start 4.”
- **Legacy Compact Startup ZIP:** the earlier single-file card for users who
  want to keep that format. Its `fpSup.BIN` is not a Merge v4 upload.

Do not select RAW View with LV Boost; they use overlapping COLOR and preview
hooks. Do not combine Indoor with other flicker/exposure experiments.
Custom uploads do not carry all this compatibility information into Merge.
At load time, exclusive hook claims stop a conflicting installation.

The v4 card includes SupManager. It has no USB Shell, Focus Inset, or LCD gamma
mod. Indoor activates when a STILL P custom preset is named **Indoor50** or
**Indoor60**; **Indoor** is the older 60 Hz alias. LV BOOST is selected in COLOR.

## Rebuild and verify

Use the official upstream fpSup checkout at
[`21bcc5578e0d17d6f71872c0664e8132b2b28fe4`](https://github.com/ijigen/fpSup/tree/21bcc5578e0d17d6f71872c0664e8132b2b28fe4).
The builder reads the two extracted 5.02 firmware segments from this fork's
`out/` directory (see the [LV Boost build instructions](../../color-modes/lv-boost/#build)).
The upstream emulator also needs its own `out/MAIN_c0000000.bin`.
Use Python with NumPy, Capstone and Unicorn, Clang with ARM support, and Node.js.
From the fork root, with `UPSTREAM` pointing to the pinned checkout:

```sh
python3 -B custom-modes/loader-v4/build.py --upstream "$UPSTREAM" --out out/v4-modules
node custom-modes/loader-v4/compose.js "$UPSTREAM" out/v4-modules out/v4-cards
python3 -B custom-modes/loader-v4/test_cards.py --upstream "$UPSTREAM" --cards out/v4-cards
python3 -B custom-modes/loader-v4/package.py --upstream "$UPSTREAM" --modules out/v4-modules --card out/v4-cards/fast --out out/v4-zips
```

The port keeps the existing resident code, claims stock words through Loader v4
before installing, and uses its veneer allocator. A refused claim or an installer
that leaves its sentinel stock releases the module without arming its hooks.
The current Merge composer accepted both uploads. The exact v4 card passed
ordinary loading, cold fallback and stored-loader hits, warm restarts,
Indoor50/60 warning thresholds, LV Boost tone lookup and shutdown restoration,
including with upstream USB Shell selected. Refusing a conflicting hook and
an allocation failure were checked separately. The legacy module and stock
records are unchanged. This exact v4 card has not been tested on hardware.

The bundled boot and SupManager files come from upstream fpSup by bei (ijigen).
Their [corresponding upstream source](https://github.com/ijigen/fpSup/tree/21bcc5578e0d17d6f71872c0664e8132b2b28fe4/fpSup)
and GPL license are included or linked in the release. No SIGMA firmware image
is redistributed.
