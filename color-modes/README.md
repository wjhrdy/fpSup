# Color modes

Self-contained camera COLOR-menu modes and preview tools for SIGMA fp.

| Module | Purpose | Status |
|---|---|---|
| [LV Boost](lv-boost/) | +1/+2/+3 STILL preview brightness with saved settings | Experimental; fpSup-Merge input and camera-test package |

Each module owns its source, build instructions, tests and packages. Grouping
modules here does not imply they can be combined: LV Boost and
[RAW View](../releases/fpsup-raw-view-v0.2.0test/) share hooks and are mutually
exclusive. RAW View remains in the existing RAW tools layout.
