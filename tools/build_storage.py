#!/usr/bin/env python3
"""
Generate SPIFFS storage.bin for firmware from language source folders.

Usage:
    python tools/build_storage.py           # build all languages found in source/
    python tools/build_storage.py ru        # build only Russian
    python tools/build_storage.py ru en fr  # build multiple languages

Prerequisites:
    Copy spiffsgen.py from ESP-IDF into tools/:
        cp /home/zen/projects/esp32/esp-idf/components/spiffs/spiffsgen.py tools/

Output:
    firmware/robot/s3/{lang}/storage.bin
    firmware/control/s3/{lang}/storage.bin
"""

import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SOURCE_DIR = REPO_ROOT / "source"
SPIFFSGEN   = Path(__file__).parent / "spiffsgen.py"

# Must match firmware partition table and menuconfig
PARTITION_SIZE = "0x800000"
SPIFFS_FLAGS = [
    "--page-size=256",
    "--obj-name-len=32",
    "--meta-len=4",
    "--use-magic",
    "--use-magic-len",
]

# Same storage.bin goes to both devices (MP3 files are shared)
TARGETS = [
    "firmware/robot/s3",
    "firmware/control/s3",
]


def build_lang(lang: str) -> bool:
    src = SOURCE_DIR / lang
    if not src.is_dir():
        print(f"[ERROR] source/{lang}/ not found")
        return False

    ok = True
    for target in TARGETS:
        out_dir = REPO_ROOT / target / lang
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "storage.bin"

        cmd = [sys.executable, str(SPIFFSGEN), PARTITION_SIZE, str(src), str(out_file), *SPIFFS_FLAGS]
        print(f"  {lang} → {out_file.relative_to(REPO_ROOT)}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f"[ERROR] spiffsgen failed for {lang} → {target}")
            ok = False

    return ok


def main():
    if not SPIFFSGEN.exists():
        print("[ERROR] tools/spiffsgen.py not found.")
        print("Copy it from your ESP-IDF installation:")
        print("  cp /home/zen/projects/esp32/esp-idf/components/spiffs/spiffsgen.py tools/")
        sys.exit(1)

    langs = sys.argv[1:] if len(sys.argv) > 1 else sorted(d.name for d in SOURCE_DIR.iterdir() if d.is_dir())

    if not langs:
        print(f"[ERROR] No language folders found in source/")
        sys.exit(1)

    print(f"Building {len(langs)} language(s): {', '.join(langs)}")
    success = all(build_lang(lang) for lang in langs)
    print("Done." if success else "Finished with errors.")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
