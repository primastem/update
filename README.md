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
2. Generate the storage image (10 MB partition, S3):
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

All ESP32-S3 targets (production and development) use the same **10 MB** SPIFFS partition.

```bash
# All languages found in source/, production only
python tools/build_storage.py

# Single language, production only
python tools/build_storage.py en

# Multiple languages, production only
python tools/build_storage.py en fr ru

# Production EN + development EN (both 10 MB)
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
│       ├── {lang}/storage.bin      # localized audio (10 MB per language)
│       └── arhiv/                  # archived releases + previous partition tables
├── control/
│   └── (same structure)
└── development/
    ├── robot/                      # dev/test builds (10 MB storage.bin)
    └── control/
```

## Partition map (ESP32-S3, unified prod and dev)

| Partition | Offset | Size |
|---|---|---|
| nvs       | 0x009000 | 24 KB |
| phy_init  | 0x00F000 | 4 KB  |
| factory   | 0x010000 | 1 MB  |
| storage   | 0x110000 | **10 MB** |

End of storage: `0x110000 + 0xA00000 = 0xB10000` (≈ 11.06 MB).
Required flash size: **16 MB** (standard for ESP32-S3-WROOM-1 N16R8).

> Until 2026-05-11 production used an 8 MB storage partition while development used 10 MB. The maps were unified to 10 MB across both. Old 8 MB partition-tables are archived in `firmware/{robot,control}/s3/arhiv/partition-table_8MB_2026-05-11.bin`.
