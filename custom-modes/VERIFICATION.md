# Indoor 0.3.0 verification

Firmware: SIGMA fp 5.02. MAIN SHA256:
`aaa5208a028d9c4aebb9cc8614add723d456e96b2a95914f433079954320e622`.

Build uses `custom-modes/build_indoor.py`, `indoor.S` and the shared
`fp_usb_shell/build_autorun.py --loader --no-shell`. No firmware is distributed.

Artifact SHA256:

```text
b3ab01d3ca08bcbcfc7093aa170a20855484395f6d8c5872ce833e40f99679d2  Indoor-v0.3.0-Merge-Sigma-fp-5.02.zip
f5857e5ba4ab76a238aacf754fdfa679b03b5effa1b509024ea93fca52a00617  AutoRun.txt
9cecdb92b83cc9e86a36737d63633b3028edaf419429566e5e462fc3aacdff0e  fpSup.BIN
```

The builder output is byte-identical to the previously tested native warning
ordinary input. Its AutoRun is unchanged. The upload contains two address-zero
records (shared stage2 + Indoor launcher), with one Indoor entry and no Shell,
Fast provisioning, LV Boost, or entry chain. Fast belongs to final Merge output.

## Offline checks

- All **54** legal combinations in the actual repository Merge composer:
  Indoor alone or with Shell 3.3.0, either gyro 1.14.0 edition and either OG3K
  0.2.6a or OG2K 0.1.3a, ordinary/Fast, EP83 off/on where applicable.
  Maximum size **35,880 / 61,440** bytes. Entries and launcher relocation checked;
  AutoRun does not change with payload selection within the same packaging mode.
- Actual native getter, program model selection and interpolation; both settings
  banks/dial fields, all slots and case-insensitive exact name matching; mode,
  shift, missing-context, stock override and entry/exit cases. Bright native
  faster-shutter escape remains intact; no custom shutter family installed.
- Real native iris helper chain for NoLensIris; warning threshold and controlled
  aperture exclusions. Exact native font pixels checked against ROM glyphs;
  space glyph confirms that one bits are background, zero bits are text.
- Three-buffer clearing, dial/name/mode/app transitions, register/flag and SP
  preservation, freed staging, failed allocation and mutated name-gate check.
- Ordinary, direct Fast and warm startup; actual Merge-generated Indoor-only
  ordinary/Fast/warm outputs; every current/legacy journaled hook restored at
  shutdown. No detector/override/settings-bank writes added by the payload.

The emulator mocks OS/file/heap/cache/lock services. The composition matrix
checks placement and entries; it does not execute every peer mod's resident
code. Camera results are separate: the user reported native Indoor and the
manual-lens warning working, but this exact ordinary upload package and the
corrected red-background palette have not been independently hardware-tested.
No camera or SD card operation was performed for this PR.
