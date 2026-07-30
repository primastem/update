# PrimaSTEM Firmware Updater

Web-based firmware update page for [PrimaSTEM](https://primastem.com/) devices.
Live at **[update.primastem.com](https://update.primastem.com/)** — works in Chrome and Edge via WebUSB.

## Supported devices

| Device | Chip |
|---|---|
| Robot | ESP32, ESP32-S3 |
| Control board | ESP32, ESP32-S3 |

## Supported languages (18, ESP32-S3 only)

`ar` العربية · `ca` Català · `da` Dansk · `de` Deutsch · `en` English ·
`es` Español · `fr` Français · `he` עברית · `it` Italiano · `ja` 日本語 ·
`nb` Norsk · `nl` Nederlands · `pl` Polski · `pt-BR` Português (Brasil) ·
`ru` Русский · `sv` Svenska · `tr` Türkçe · `uk` Українська

Audio is shared across all devices and channels: one 14.5 MB SPIFFS image per
language at `firmware/s3/audio/{lang}/storage.bin`. Robot, Control, stable and
dev all flash the same image; `index.html` swaps the locale at install time.

## Adding a new language

1. Put MP3 files into `source/{lang}/` (e.g. `source/de/`)
2. Generate the storage image (14.5 MB partition, S3):
   ```bash
   python tools/build_storage.py de
   ```
   This writes `firmware/s3/audio/de/storage.bin` (one file, shared by all devices).
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

All S3 audio uses the same **14.5 MB** SPIFFS partition and a single shared output tree (`firmware/s3/audio/`).

```bash
# All languages found in source/
python tools/build_storage.py

# Single language
python tools/build_storage.py en

# Multiple languages
python tools/build_storage.py en fr ru
```

## Verifying consistency

`tools/verify_manifests.py` checks that every `part.path` in all four manifests
exists on disk and that every language listed in `index.html` has its
`firmware/s3/audio/{lang}/storage.bin`. Run it after any structural change:

```bash
python tools/verify_manifests.py
```

## Firmware layout

```
firmware/
├── s3/
│   ├── stable/{robot,control}/       # bootloader · partition-table · {robot,control}.bin
│   ├── development/{robot,control}/   # dev/test builds (same three files)
│   └── audio/{lang}/storage.bin       # shared localized audio (14.5 MB per language)
├── esp32/                             # legacy ESP32 (non-S3), kept for units in the field
│   └── stable/
│       ├── robot/                     # bootloader · partition-table · robot.bin · storage.bin
│       └── control/                   # bootloader · partition-table · control.bin
└── _archive/                          # archived releases, old partition tables, dated snapshots
    ├── s3/{robot,control}/
    └── development/{robot,control}/{arhiv,1705}/
```

Layout rule: `firmware/{chip}/{stable|development}/{device}/`, with audio pulled
out to `firmware/s3/audio/{lang}/` because it is identical across devices. ESP32
is legacy — no dev builds, its (non-localized) robot audio lives in
`esp32/stable/robot/storage.bin`.

## Partition map (ESP32-S3, shared by stable and dev)

| Partition | Offset | Size |
|---|---|---|
| nvs       | 0x009000 | 24 KB |
| phy_init  | 0x00F000 | 4 KB  |
| factory   | 0x010000 | 1 MB  |
| storage   | 0x110000 | **14.5 MB** |

End of storage: `0x110000 + 0xE80000 = 0xF90000` (≈ 15.56 MB).
Required flash size: **16 MB** (standard for ESP32-S3-WROOM-1 N16R8).

See `docs/PARTITIONS.md` for the full flash layout and esptool commands.
