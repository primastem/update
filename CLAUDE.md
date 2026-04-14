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
├── robot/
│   ├── esp32/          # bootloader.bin, partition-table.bin, robot_prima_stem_esp32.bin, storage.bin
│   └── s3/             # bootloader.bin, partition-table.bin, prima_stem_robot.bin
│       ├── en/storage.bin
│       ├── fr/storage.bin
│       ├── ru/storage.bin
│       └── arhiv/      # dated archive of past releases
├── control/
│   ├── esp32/          # bootloader.bin, partition-table.bin, control_prima_stem_esp32.bin
│   └── s3/             # bootloader.bin, partition-table.bin, prima_stem_controll.bin
│       ├── en/storage.bin
│       ├── fr/storage.bin
│       ├── ru/storage.bin
│       └── arhiv/
└── development/
    ├── robot/          # ESP32-S3 dev builds
    └── control/        # ESP32-S3 dev builds
```

**Important**: The production S3 manifests currently point to `en/storage.bin` (English locale). Localized `fr/` and `ru/` variants exist but are not wired into the manifests.

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
3. Archive the old `.bin` in the relevant `arhiv/` folder if needed

### Switching localization for S3 production builds
Change the `storage.bin` path in `manifest_robot.json` or `manifest_control.json` from `en/` to `fr/` or `ru/`.

### Deploying
Push to `main` — GitHub Pages auto-deploys. The site lives at `https://update.primastem.com`.
