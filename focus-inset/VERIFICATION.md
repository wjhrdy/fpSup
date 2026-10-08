# Focus Inset 0.1.0test verification

Date: 2026-10-08. Firmware: SIGMA fp 5.02 only.

The portable build reproduces the camera-tested v0.20 resident module exactly.
All four public combined candidates reproduce the prior tested-candidate bytes.
The exact USB-debug card was confirmed on-camera after a normal fast restart;
standard/no-Shell and standalone variants have offline validation. Ten repeated
non-recording power cycles and an older-card transition remain unverified.

## Passed checks

- Actual shared-loader initialization, ten journaled hooks, owned resident copy,
  native descriptors, GUI entry/exit redraw, thin outline and both shutdown paths.
- Native startup crop regression: stock empty processing cache reproduced; the
  initial adapter matches the native ready-state crop. Deliberate adapter bypass
  failed the regression before packaging.
- Native peaking region and AF/CINE/fullscreen/capture pass-through.
- 216 current Merge combinations; maximum 117664 / 126976 bytes.
- All four combined variants; ordinary, stored and warm startup where applicable;
  Indoor thresholds, LV Boost resident behavior and both shutdown callbacks.
- Native full OSD draw/submission routing: warning reaches group 3; clearing and
  menu integrity verified. The user confirmed the warning visible on camera.
- 30 shared loader/boot/splash tests. Journal setup/registration failures prevent
  payload placement/execution; legacy unguarded card is the negative control.
- Fresh catalogue generation checked its existing native OG/Gyro reference cards.
  These are offline composition checks, not hardware validation of those peers.

The separate research `test_boot_entry_chain.py` could not run its 14 cases:
its Open Gate builder rejects the available firmware image (SHA-256
`aaa5208a028d9c4aebb9cc8614add723d456e96b2a95914f433079954320e622`).
This is an uncompleted regression gate, not a passing result. Existing catalogue
reference checks and the 30 shared boot/loader/splash tests above passed.

Fast AutoRun and FPSUPUI match the previous Fast Start 3 release. The new
guarded shared stage2 requires the updated Merge HTML included in this release;
the current Pages tool is updated when this PR is merged. The loader ABI and
Fast stored-loader magic do not change. No extracted firmware is published.

## SHA-256

| File | SHA-256 |
|---|---|
| module | `b7e636c8f8250cf2166474aef9d42f5f9f1bbad0e3f55ad6ea3472a297496868` |
| focus merge BIN | `fba6fdfa02ee1cb98787ce9e47d6bdd07439d1d4a05020565cd1f4d6698091f6` |
| Indoor merge BIN | `edf04d5566a9b2099a8790323f6d7e37e47dfc6d77d0cbb8772f9d8f247f66aa` |
| standard combined BIN | `12050880c7b0fe607e74f8a72666aeda1747f457b4ed62af574693da2e457b11` |
| USB-debug combined BIN | `08154707fc570256c52168402e622cb7efb11e116e13186a261a73882bb196e5` |
| Fast AutoRun | `b00ce0dc23fbee33d46267798c417c43800818d951b4da0d3e671de7809d9665` |
