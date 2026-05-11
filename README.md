# PrimaSTEM Firmware Updater

Web-based firmware update page for [PrimaSTEM](https://primastem.com/) devices.
Live at **[update.primastem.com](https://update.primastem.com/)** — works in Chrome and Edge via WebUSB.

## Supported devices

| Device | Chip |
|---|---|
| Robot | ESP32, ESP32-S3 |
| Control board | ESP32, ESP32-S3 |

## Adding a new language

1. Put MP3 files into `source/{lang}/` (e.g. `source/de/`)
2. Generate the storage image (13 MB partition, S3):
   ```bash
   python tools/build_storage.py de
   ```
   This writes `firmware/robot/s3/de/storage.bin` and `firmware/control/s3/de/storage.bin`.
3. Add the language to `ALL_LANGS` in `index.html`:
   ```js
   { code: 'de', name: 'Deutsch' },
   ```
4. Commit and push — the language appears on the site automatically.

> `tools/spiffsgen.py` is not tracked in git. Copy it once from your ESP-IDF installation:
> ```bash
> cp $IDF_PATH/components/spiffs/spiffsgen.py tools/
> ```

## Building the storage image

`tools/build_storage.py` is hardened — it fails loudly on any `spiffsgen` error and verifies the output file size after every build. It will never leave a silent zero-byte `storage.bin`.

All ESP32-S3 targets (production and development) use the same **13 MB** SPIFFS partition.

```bash
# All languages found in source/, production only
python tools/build_storage.py

# Single language, production only
python tools/build_storage.py en

# Multiple languages, production only
python tools/build_storage.py en fr ru

# Production EN + development EN (both 13 MB)
python tools/build_storage.py en --dev

# Only the development image (e.g. switch the dev bundle from EN to RU)
python tools/build_storage.py ru --dev-only
```

The dev firmware uses a single `storage.bin` (no per-language folder), so `--dev` bundles exactly one language at a time — the last positional argument wins.

## Firmware layout

```
firmware/
├── robot/
│   ├── esp32/                      # ESP32 firmware
│   └── s3/                         # ESP32-S3 firmware
│       ├── {lang}/storage.bin      # localized audio (13 MB per language)
│       └── arhiv/                  # archived releases + previous partition tables
├── control/
│   └── (same structure)
└── development/
    ├── robot/                      # dev/test builds (13 MB storage.bin)
    └── control/
```

## Partition map (ESP32-S3, unified prod and dev)

| Partition | Offset | Size |
|---|---|---|
| nvs       | 0x009000 | 24 KB |
| phy_init  | 0x00F000 | 4 KB  |
| factory   | 0x010000 | 1 MB  |
| storage   | 0x110000 | **13 MB** |

End of storage: `0x110000 + 0xD00000 = 0xE10000` (≈ 14.06 MB).
Required flash size: **16 MB** (standard for ESP32-S3-WROOM-1 N16R8).

> Change log: production was originally 8 MB / dev 10 MB. Both unified to 10 MB on 2026-05-11, then bumped to 13 MB the same day after the audio set was expanded (de/es/nl/sv no longer fit in 10 MB). Old 8 MB and 10 MB partition-tables archived under `firmware/{robot,control}/s3/arhiv/` and `firmware/development/{robot,control}/arhiv/`.
