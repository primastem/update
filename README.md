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
2. Generate storage image:
   ```bash
   python tools/build_storage.py de
   ```
3. Add the language to `ALL_LANGS` in `index.html`:
   ```js
   { code: 'de', name: 'Deutsch' },
   ```
4. Commit and push — the language appears on the site automatically.

> `tools/spiffsgen.py` is not tracked in git. Copy it once from your ESP-IDF installation:
> ```bash
> cp /path/to/esp-idf/components/spiffs/spiffsgen.py tools/
> ```

## Firmware layout

```
firmware/
├── robot/
│   ├── esp32/                      # ESP32 firmware
│   └── s3/                         # ESP32-S3 firmware
│       ├── {lang}/storage.bin      # localized audio (one per language)
│       └── arhiv/                  # archived releases
├── control/
│   └── (same structure)
└── development/
    ├── robot/                      # dev/test builds
    └── control/
```
