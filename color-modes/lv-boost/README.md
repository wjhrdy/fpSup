# LV Boost (Live View Boost): STILL preview +1 / +2 / +3

Part of [Color modes](../README.md). [RAW View](../../releases/fpsup-raw-view-v0.2.0test/) remains under the RAW tools.

Development module for **SIGMA fp firmware 5.02**. LV Boost adds a COLOR-menu
row that brightens the preview at a fixed capture exposure. The v0.6.1 merge
candidate restores the last selected LV Boost level after stable STILL live view begins. First use defaults to **+2**.
Selecting OFF or a native color preset saves LV Boost as disabled; the next
boot leaves the native color choice alone. A manual menu selection cancels a
pending startup restore.

[Download the v0.6.1 merge candidate](LV-Boost-v0.6.1-Merge-Sigma-fp-5.02.zip).
It contains an ordinary card with **no Fast Start 2 and no bundled USB shell**.
It is deliberately outside the release catalogue pending maintainer review and
camera validation. The old v0.6.0 FS2 ZIP remains a standalone development card;
do not upload its BIN to Merge.

For a ready-to-install test card, use the
[Merge-built LV Boost + Shell + Fast Start 2 package](LV-Boost-v0.6.1-Shell-FS2-Camera-Test.zip).
It includes the complete AutoRun/BIN/FPSUPUI set and test instructions, with
EP83 off. Its exact files passed all three emulated loading paths; physical
camera validation is pending. This combined card is not a Merge input.

## fpSup-Merge compatibility

Guidance/source: [fpSup-Merge](https://github.com/ijigen/fpSup/tree/main/tools/card-composer)
and [build contract](../../SUP_BUILD_RULES.en.md), checked against upstream
`ba5f607f87baa741ea05007c7be0b6882d217b84` on 2026-09-26. Merge lives inside
fpSup's `tools/card-composer/`, not a separate repository.

1. Extract the v0.6.1 ZIP and upload **fpSup.BIN** to
   [fpSup-Merge](https://ijigen.github.io/fpSup/tools/card-composer/).
2. Select the other Sups you want. Add Shell there for USB diagnostics; enable
   Fast Start 2 there if wanted. Use only one gyro edition and one OpenGate.
3. Download Merge's ZIP and use its complete `AutoRun.txt`, `fpSup.BIN`, and
   `FPSUPUI` folder together. Do not mix an ordinary BIN with an old FS2 AutoRun.

**Do not combine with RAW View**, including an uploaded RAW View BIN. Both own
COLOR/menu and preview hooks; identical stock-word journal records may be
folded together by Merge without detecting that runtime conflict. Packaging
success alone cannot make that combination valid. A future catalogue listing
must declare RAW View and LV Boost mutually exclusive.

The input has one position-independent launcher entry, no nested entry table,
no pool-offset sections, and no private loader. It allocates 0x7000 bytes from
USER memory for its resident code/tables and requests an 8 KiB task stack.
Sixteen 8-byte veneers use stage2's shared cave allocator. It does not publish
or overwrite the gyro pool pointer at `0xC3757A7C`. Firmware patch sites are
stock-word records for the shared shutdown journal. The existing experimental
preference word and its hardware-validation limits below remain unchanged.

Offline checks cover all 54 legal combinations in that Merge snapshot: LV Boost
alone and with Shell 3.3.0, either gyro 1.14.0 edition, and either OG3K 0.2.6a or
OG2K 0.1.3a, normal/Fast, Shell EP83 off/on. RAW View is not in that snapshot's
catalogue and is explicitly excluded. Maximum used BIN size is 57,252 of
61,440 bytes. These results do not imply compatibility with future releases.

## Install and use

For standalone ordinary loading, back up your existing card files and copy both
`AutoRun.txt` and `fpSup.BIN` from the v0.6.1 ZIP to the card root. This ordinary
input uses the shared loader's text screen and needs no FPSUPUI assets. For
Fast Start 2 or other Sups, use the complete ZIP produced by Merge as above.
Boot with USB unplugged; attach USB after boot if Shell was selected in Merge.

**Migrating from v0.5.x/v0.6.0 FS2 requires both AutoRun and BIN to change** because
this release separates Fast/Shell from the merge input. Later payload-only
updates with unchanged packaging can still replace only the BIN. The historical
v0.6.0 FS2 update was BIN-only; that instruction does not apply to this ordinary
merge input.

Select LV BOOST in COLOR and adjust it to +1, +2, or +3. Turn the camera off
normally to let its existing settings save complete. On next boot, the saved
level is applied once after ten consecutive 100 ms samples of stable STILL.
Selecting OFF or another color preset disables automatic LV Boost restoration
while retaining its last level for when you select LV BOOST again. A battery
removal before normal shutdown may lose the latest change. Reset/invalid
settings fall back to the built-in +2 default.
The menu icon reads LV BOOST. The full color title may still read OFF because the native firmware sees OFF
plus private mod state. The lifted display is not an exposure/clipping reference.

FS2 uses the existing shared loader's stored bootstrap and warm-restart hook.
It writes loader bytes to the camera's persistent common settings area;
deleting the card files does not erase those bytes or the saved LV Boost preference.

## Build

Requirements: Python 3, Clang with the `armv7-none-eabi` target, and the existing
build/test dependencies:

```sh
python3 -m pip install numpy capstone unicorn pillow
```

Supply these extracted **5.02** firmware segments in the repository's `out/`
directory. Firmware images are not included in this PR. If using the full
research devkit, these are the same segments its builders use; its extracted
`DAT1_c2ef6e00.bin` is copied as `seg1_c2ef6e00.bin`.

| File | SHA-256 |
|---|---|
| `out/MAIN_c0000000.bin` | `aaa5208a028d9c4aebb9cc8614add723d456e96b2a95914f433079954320e622` |
| `out/seg1_c2ef6e00.bin` | `0dcaca8f5441fe4ddc6ed801cb888e325df4e76006e4f53a1c3219809b22ce7b` |

Archived ZIPs retain their original documentation and checksums. Use the current
build paths below rather than the older paths inside those archives.

From the repository root, build into a fresh directory:

```sh
python3 color-modes/lv-boost/build/build_lv_boost.py --out /tmp/lv-boost-ordinary
python3 color-modes/lv-boost/test_lv_boost.py -v
node color-modes/lv-boost/test_merge.js /tmp/lv-boost-ordinary/fpSup.BIN /tmp/lv-boost-matrix
python3 color-modes/lv-boost/verify_card.py /tmp/lv-boost-ordinary /tmp/lv-boost-matrix/lv-*
```

`--default-level 1|2|3` selects the first-use/fallback level (default: 2); a valid
saved preference takes precedence. The default is an ordinary merge input.
`--shell` and `--fs2` are opt-ins for standalone development cards only; those
cards must not be uploaded to Merge. `--no-shell` remains a supported alias for
the default. To reproduce the old v0.6.0 card, use `--shell --fs2`.
The Node check uses the actual page's parser and composer, not a second merger;
its optional third argument selects a different downloaded Merge HTML snapshot.
Matrix output must be a new directory; it refuses to overwrite prior evidence.
The builder uses the repository's shared `fp_usb_shell/build_autorun.py` and
its existing loader, stage2, journal, Fast bootstrap and splash resources.
There is no separate loader implementation. Generated includes and local
build output are ignored. Do not commit extracted firmware images.

The `rv_*` sources are derived from the research devkit's RAW View implementation.
Its LV_BOOST assembly variant is retained to preserve the tested startup and tone behavior. The Python wrapper is restricted to LV Boost and uses this repository's
paths, so no external research-tree modules or data are required after supplying
the firmware segments. The unused matrix buffers retain their original layout;
the LV Boost hooks do not install the RAW gain, global tone/matrix-root, or
DNG-writer patches.

## Implementation

Three 2048-entry tone curves apply +1/+2/+3 stops in linear light with a soft
highlight shoulder. The tone-pointer hook replaces only the stock OFF table
for context 0, native single-table dispatch, and live-view attribute 1 with
application status 2 or 5. The gain hook only invalidates the preview tone
cache when the selection changes; it preserves the original gain-state result.
All firmware hook sites are declared for the shared loader's shutdown journal.

A priority-28 task with an 8 KiB stack waits for stable STILL, requests OFF
through the native settings facade with the private LV Boost selection,
checks the result, and parks. It does not call settings APIs from ISP hooks,
retry failed selections, or hold pointers into the freed staging buffer.

Preferences occupy one aligned word at `0xC307544C` (`XC_CommonSaveData +0x210`):
`0x4C560100 | (enabled << 2) | level_index`, where the index is 0..2. The
upper 29 bits identify format version 1; both invalid index encodings are
rejected. Installation only reads it. Successful startup, menu selection, and
level changes update the RAM mirror; the camera's normal shutdown saves it.
Native initialization/apply callbacks do not overwrite it before restoration.
No new file I/O, explicit flash writes, or polling saves are introduced.
This preference deliberately stays out of the firmware-patch shutdown journal.

The full devkit's `research/firmware/notes/PERSISTENT_STORE_COMMONSAVE.md`
records power-cycle survival of the +0x210..+0x280 span. This word is outside
Fast's entire +0x028..+0x200 reservation and OpenGate's +0x290 preference.
Those research notes are not bundled here. Historical survival does not prove
that no untested native feature uses this reserved area; this remains an
experimental allocation for fp 5.02 and needs camera power-cycle validation.

With an already connected USB shell, read diagnostics without changing settings:

```sh
python3 color-modes/lv-boost/read_diagnostics.py --out /path/to/diagnostics.json
```

`startup_state`: 0 waiting, 1 applied, 2 manual menu override, 3 applying,
4 verification failed, 5 saved disabled. `startup_task` and `startup_task_result` report native
task creation/start results. A task id at or below zero is a creation failure
(the JSON reader presents native words as unsigned integers).

v0.6.1 ordinary merge-input `fpSup.BIN` SHA-256:
`bde12037c8d2a77f1d4ad00715a0958ec700c26fd163bf3a478a7c3947682d31`.
The candidate ZIP includes its card-file checksums.

## Validation and limits

- v0.6.1 changes packaging defaults only; its LV Boost launcher/resident/tables
  are byte-identical to v0.6.0. `--shell --fs2` still reproduces the old BIN.
- The 54 composed cards pass exact-card emulation: real loader, stage2, entry
  trampoline and all selected payload entries execute and return. The verifier
  models ordinary reloads and both Fast paths, clears BSS/heap on restart,
  restores the saved settings mirror, poisons freed staging, exercises the
  resident preview hook afterward, and checks the complete declared firmware
  journal at shutdown. Native allocation, I/O, settings facade and scheduling
  are mocked; this is not a recording/USB/OpenGate functional test.
- A mutation that returns before installing LV Boost fails exact-card verification.
  The merge-input check rejects the old bundled Shell/FS2 layout.
- A first-use level change leaves ordinary AutoRun byte-identical. Merge also
  keeps AutoRun byte-identical for payload selection changes within the same
  Fast/Shell configuration.

- On-camera feedback: the v0.4 curve visibly lifted STILL preview. The user
  subsequently confirmed v0.5.0 automatically selected +3 and worked when
  powering up in STILL. Cold versus warm startup was not distinguished.
- v0.5.1 +2 was installed, fully read back and safely ejected. Physical +2
  startup confirmation is still pending.
- All 16 LV Boost tests pass in this repository, including native tone lookup,
  restricted navigation, selection/disable, startup +2, transitions, cancellation,
  task/selection failure handling, saved levels/disabled state, invalid data,
  boot callback protection, and writes confined to the preference word.
- Exact-card emulation runs the actual payloads through ordinary, stored-bootstrap
  and warm-hook loading, checking task creation and shutdown restoration.
  Native I/O, task scheduling, and settings side effects are mocked.
- Before the rename, the standalone sources reproduced all seven installed
  v0.5.1 card files byte-for-byte. The renamed v0.5.2 package was rebuilt and
  passed the same 13 tests and exact-card emulation; it has not booted on camera.
  The shared loader/splash suite and composer checks were also exercised.
- v0.6.0 passes all 16 tests and exact-card emulation of all three loading paths.
  Fast provisioning and shutdown preserve the preference word. Saved settings
  have not yet been validated on the camera; flash persistence and native task
  scheduling are not simulated.
- Development mutation checks caught a shortened stabilization wait and an OFF
  request substituted for the private LV Boost request. Removing the saved-word
  store also makes the new persistence test fail for all three levels.

No native startup gate was bypassed: FS2 still depends on the existing AutoRun
trigger. The STILL power-up report is not evidence that every cold-start path
works. Repeated idle power cycles, capture/JPEG/embedded-preview isolation,
AE behavior, focus magnification, and HDMI/EVF behavior remain unverified.
This is a development PR, not a production-readiness claim.

v0.6.0 `fpSup.BIN` SHA-256:
`02da37e5f987350114dcadde56f72fe5eaaf4344b23de5cf5b08a54a30909281`.
The ZIP includes checksums for every card file.
