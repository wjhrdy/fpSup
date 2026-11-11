Indoor 0.4.5 + LV Boost 0.6.1 — Loader v4 test release
SIGMA fp firmware 5.02 only (not fp L).

Merge v4 ZIP: extract Indoor_v0.4.5.BIN and LV-Boost_v0.6.1.BIN. Use
"Add a .BIN" on the current fpSup Merge page to add either or both modules,
select other compatible v4 modules, then download the card from Merge:
https://ijigen.github.io/fpSup/tools/card-composer/
Do not copy the two upload files on their own to a blank card.

Loader v4 Fast Start ZIP: the two modules with SupManager and both Instant
Start and Fast Start already enabled. Unzip and copy AutoRun.txt and the
whole fpSup folder to the SD card root. Back up old card files; remove the
old fpSup folder, old AutoRun.txt, and any legacy fpSup.BIN or FPSUPUI first,
so stale modules and scripts cannot load. This is a complete card; do not
upload LOADER.BIN to Merge. Start from a cold boot when switching loader
formats so the previous card's warm hook does not run.

The separate Legacy Compact Startup ZIP is for the older single-file
format. Do not mix its AutoRun or BIN with the v4 files.

In STILL P, use a saved custom preset named Indoor50 (50 Hz) or Indoor60
(60 Hz). Indoor is the older 60 Hz alias. The BANDING RISK warning uses the
camera's displayed shutter speed. In COLOR, select LV BOOST for +1/+2/+3
preview brightness. LV Boost keeps its existing saved preference.

Do not combine LV Boost with RAW View, or Indoor with another flicker or
exposure experiment. The ready card has no USB Shell, Focus Inset or LCD
gamma mod. The Fast Start switch provisions loader bytes in the existing
persistent settings area. The normal LV Boost preference also persists.
Offline verified; this exact Loader v4 card has not been tested on hardware.

Release and build source:
https://github.com/wjhrdy/fpSup/releases/tag/fpsup-indoor-lvboost-v1.4.0test
The tag contains the v4 integration sources in custom-modes/loader-v4/.
The ready card bundles the unchanged boot files and SupManager from
fpSup by bei (ijigen), GPL-3.0-or-later; corresponding upstream source:
https://github.com/ijigen/fpSup/tree/21bcc5578e0d17d6f71872c0664e8132b2b28fe4/fpSup
No SIGMA firmware image is included. SHA256SUMS identifies the packaged files.
