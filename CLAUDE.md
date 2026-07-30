# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Static firmware update web app for **PrimaSTEM** robotics devices (ESP32 and ESP32-S3), deployed via GitHub Pages at `update.primastem.com`. No build process — all changes deploy on push to `main`.

## Architecture

### Single-page app (`index.html`)
- Uses [`esp-web-tools`](https://github.com/esphome/esp-web-tools) v10 from CDN (`unpkg.com`) for WebUSB-based device flashing
- A radio button group sets `button.manifest` on the `<esp-web-install-button>` element
- Four device types: `robot`, `control`, `devrobot`, `devcontrol`
- Each maps to a manifest file: `manifest_{type}.json`

### Manifest files (JSON)
Each manifest defines firmware `builds` per `chipFamily` (ESP32 or ESP32-S3), listing binary `parts` with memory `offset` values:

| Manifest | Device | Chips |
|---|---|---|
| `manifest_robot.json` | Robot (production) | ESP32, ESP32-S3 |
| `manifest_control.json` | Control board (production) | ESP32, ESP32-S3 |
| `manifest_devrobot.json` | Robot (dev/test) | ESP32-S3 only |
| `manifest_devcontrol.json` | Control board (dev/test) | ESP32-S3 only |

### Firmware directory layout
```
firmware/
├── s3/
│   ├── stable/{robot,control}/       # bootloader.bin, partition-table.bin, {robot,control}.bin
│   ├── development/{robot,control}/   # ESP32-S3 dev/test builds (same three files)
│   └── audio/{lang}/storage.bin       # shared localized audio, 18 languages (14.5 MB each)
├── esp32/                             # legacy ESP32 (non-S3), slated for removal ~1 year
│   └── stable/
│       ├── robot/                     # bootloader.bin, partition-table.bin, robot.bin, storage.bin
│       └── control/                   # bootloader.bin, partition-table.bin, control.bin
└── _archive/                          # archived releases, old partition tables, dated snapshots
```

Layout rule: `firmware/{chip}/{stable|development}/{device}/`. Audio is pulled
out to `firmware/s3/audio/{lang}/` because it is byte-identical across all
devices and channels — one image instead of 38.

**Important**: All four S3 manifests point at the same base `firmware/s3/audio/en/storage.bin`. `index.html` fetches the manifest, rewrites that path to the selected locale (regex swap `en` → chosen `{lang}`), and serves it as a Blob URL. The language selector is shown for all devices, including dev. ESP32 `storage.bin` (robot only) is NOT localized and is not rewritten.

### Memory offsets (critical — do not change without verifying against the firmware build)
- ESP32 bootloader: `0x1000` (4096)
- ESP32-S3 bootloader: `0x0` (0)
- Partition table: `0x8000` (32768) for both
- Application: `0x10000` (65536) for most; Robot ESP32 uses `0x20000` (131072)
- Storage: varies per device (`0x110000` = 1114112 for S3; `0xE8000` = 950272 for Robot ESP32)

## Common Tasks

### Adding/updating firmware
1. Drop new `.bin` files into the appropriate `firmware/` subdirectory
2. Update the corresponding manifest JSON — verify `path` and `offset` values match the ESP-IDF build output
3. Run `python tools/verify_manifests.py` — confirms every manifest path exists and every language has its audio image
4. Archive the old `.bin` under `firmware/_archive/` if needed

### Adding/rebuilding audio
Drop MP3s into `source/{lang}/`, run `python tools/build_storage.py {lang}` (or no arg for all). Output goes to the shared `firmware/s3/audio/{lang}/storage.bin`. Add the language to `ALL_LANGS` in `index.html` so the site offers it.

### Deploying
Push to `main` — GitHub Pages auto-deploys. The site lives at `https://update.primastem.com`.
