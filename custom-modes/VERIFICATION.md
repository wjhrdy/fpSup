# Indoor 0.4.2 verification

Firmware: SIGMA fp 5.02. MAIN SHA256:
`aaa5208a028d9c4aebb9cc8614add723d456e96b2a95914f433079954320e622`.

Build: `python3 -B custom-modes/build_indoor.py --out <fresh-directory>`.
Tests: `python3 -B custom-modes/test_indoor.py`.
The builder uses the shared `--loader --no-shell` path. No firmware is included.

Artifact SHA256:

```text
d3267ec66a44c0b0520b43d15fcdc8b52ad3bf1475788ea1069b7bef513549ab  Indoor-v0.4.2-Merge-Sigma-fp-5.02.zip
f5857e5ba4ab76a238aacf754fdfa679b03b5effa1b509024ea93fca52a00617  AutoRun.txt
cce7eb69ee7d0542a3c410317f734ab3e63b5008c99c205bd1224c3836e5f157  fpSup.BIN
```

Only the BIN changes from the previous ordinary Indoor upload: AutoRun is
byte-identical. The upload has two address-zero records (stage2 + Indoor) and
one module entry. No bundled USB Shell, LV Boost, or Fast Start 2.

## Native frequency paths

The pure case-insensitive parser recognizes exactly Indoor, Indoor60 and
Indoor50; malformed suffixes and spaces are rejected. Indoor is the legacy
60 Hz alias. The getter returns native classification 2 for 60 Hz and 1 for
50 Hz without writing either classification into saved settings or detector RAM.

Actual native acquisition selection was checked for Auto ISO and fixed ISO:

| Name | Auto ISO model | Fixed ISO model | Warning above Tv |
|---|---|---|---|
| Indoor60 / Indoor | 0x6C | 0x7A | 7315 (last displayed 1/125) |
| Indoor50 | 0x6B | 0x79 | 6967 (last displayed 1/100) |
| Outdoor | 0x65 | 0x65 | inactive |

Both native paths retain their bright-scene faster-shutter escape. The OSD
uses the same pure name parser, checks that its result matches the getter's
cached classification, and suppresses a stale warning while names change.
The warning uses only selected shutter timing; the iris-driver check has been
removed. No new driver calls, property locks, exposure writes or detector timer.

## Passed offline checks

- All **54** supported combinations in the actual Merge composer, including
  ordinary/Fast, Shell/gyro/OG alternatives and EP83 off/on where applicable.
  Maximum used size **35,908 / 61,440** bytes. Entry relocation and AutoRun
  stability per packaging mode checked.
- All six slots, both settings banks and dial fields for all three names;
  mixed case and rejected malformed names; mode/shift/context guards.
- Real native getter/model generation/interpolation, including a native bright-scene
  faster-shutter result rendered as a warning with a controlled-aperture lens.
  Selected-model tests independently distinguish native 50 and 60 Hz policies.
- Stock shutter-label formatter `0xC0228D48` executed against its native table:
  Tv 7073, 7133, 7168 and 7315 display 1/125; 7316 displays 1/160.
  Tv 6803 and 6967 display 1/100; 6968 displays 1/125.
  The new warning regression also rejects the previous 0.4.1 payload.
- Exact white glyph/red background pixels, inverted space-glyph confirmation,
  both threshold boundaries across manual and controlled-aperture driver values, triple-buffer
  clearing. Switching Indoor60 → Indoor50 → Indoor60 at Tv=7000 changes warning
  off → on → off, without changing selected Tv.
- Register/flag/SP preservation; freed staging, failed allocation, mutated
  name-gate negative check; ordinary/direct-Fast/warm and actual Merge-generated
  ordinary/Fast/warm startup; current and legacy hooks restored at shutdown.

OS/file/heap/cache/lock services are mocked. The combination matrix checks
composition, not every peer mod's resident behavior. The user previously
reported 60 Hz Indoor/manual-lens warning behavior working; the new 50 Hz mode, all-lens warning,
display-rounding fix and this exact standalone upload have offline
validation only. No camera or card operation was performed for this PR update.
