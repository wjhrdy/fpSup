# Indoor 0.4.0 verification

Firmware: SIGMA fp 5.02. MAIN SHA256:
`aaa5208a028d9c4aebb9cc8614add723d456e96b2a95914f433079954320e622`.

Build: `python3 -B custom-modes/build_indoor.py --out <fresh-directory>`.
Tests: `python3 -B custom-modes/test_indoor.py`.
The builder uses the shared `--loader --no-shell` path. No firmware is included.

Artifact SHA256:

```text
fabde506ec411b8d6e218a8251e5036115fa2f422f8a19d94853d515df2f44eb  Indoor-v0.4.0-Merge-Sigma-fp-5.02.zip
f5857e5ba4ab76a238aacf754fdfa679b03b5effa1b509024ea93fca52a00617  AutoRun.txt
8579b92fa30935da14544cc00e1425f3760c7f800f5e701beed6f1547e36f328  fpSup.BIN
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
| Indoor60 / Indoor | 0x6C | 0x7A | 7073 (1/120) |
| Indoor50 | 0x6B | 0x79 | 6803 (1/100) |
| Outdoor | 0x65 | 0x65 | inactive |

Both native paths retain their bright-scene faster-shutter escape. The OSD
uses the same pure name parser, checks that its result matches the getter's
cached classification, and suppresses a stale warning while names change.
No new driver calls, property locks, exposure writes or detector timer.

## Passed offline checks

- All **54** supported combinations in the actual Merge composer, including
  ordinary/Fast, Shell/gyro/OG alternatives and EP83 off/on where applicable.
  Maximum used size **35,928 / 61,440** bytes. Entry relocation and AutoRun
  stability per packaging mode checked.
- All six slots, both settings banks and dial fields for all three names;
  mixed case and rejected malformed names; mode/shift/context guards.
- Real native getter/model generation/interpolation and NoLensIris helper.
  Selected-model tests independently distinguish native 50 and 60 Hz policies.
- Exact white glyph/red background pixels, inverted space-glyph confirmation,
  manual versus controlled aperture and both threshold boundaries, triple-buffer
  clearing. Switching Indoor60 → Indoor50 → Indoor60 at Tv=7000 changes warning
  off → on → off, without changing selected Tv.
- Register/flag/SP preservation; freed staging, failed allocation, mutated
  name-gate negative check; ordinary/direct-Fast/warm and actual Merge-generated
  ordinary/Fast/warm startup; current and legacy hooks restored at shutdown.

OS/file/heap/cache/lock services are mocked. The combination matrix checks
composition, not every peer mod's resident behavior. The user previously
reported 60 Hz Indoor/manual-lens warning behavior working; the new 50 Hz mode,
corrected red-background palette and this exact standalone upload have offline
validation only. No camera or card operation was performed for this PR update.
