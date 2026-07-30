#!/usr/bin/env python3
"""
Generate the shared SPIFFS storage.bin images for PrimaSTEM firmware from
language source folders.

The S3 audio partition is identical for robot and control, stable and dev, so
there is a single shared output tree: firmware/s3/audio/{lang}/storage.bin.
All four manifests point at it; index.html swaps the locale per user choice.

ESP32-S3 partition map (14.5 MB as of 2026-05-11):
    storage partition: offset 0x110000, size 0x00E80000 (14.5 MB)

Usage:
    python tools/build_storage.py                 # build ALL langs found in source/
    python tools/build_storage.py ru              # build only Russian
    python tools/build_storage.py ru en fr        # build multiple languages

Prerequisites:
    Copy spiffsgen.py from ESP-IDF into tools/:
        cp $IDF_PATH/components/spiffs/spiffsgen.py tools/

Output:
    firmware/s3/audio/{lang}/storage.bin

Hardening:
    - Fails loudly if spiffsgen returns non-zero (prints stderr).
    - Verifies output file size matches the partition size after each build.
    - Never leaves a zero-byte storage.bin behind silently.
"""

import sys
import subprocess
from pathlib import Path

REPO_ROOT  = Path(__file__).parent.parent
SOURCE_DIR = REPO_ROOT / "source"
SPIFFSGEN  = Path(__file__).parent / "spiffsgen.py"

# ESP32-S3 storage partition size, 14.5 MB
S3_PARTITION_SIZE = 0x00E80000

# Must match firmware partition table and menuconfig
SPIFFS_FLAGS = [
    "--page-size=256",
    "--obj-name-len=32",
    "--meta-len=4",
    "--use-magic",
    "--use-magic-len",
]

# Single shared S3 audio tree (robot and control, stable and dev, read from here)
AUDIO_TARGET = "firmware/s3/audio"


def run_spiffsgen(size, src_dir, out_file):
    """Run spiffsgen and verify the result. Raises RuntimeError on problems."""
    out_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(SPIFFSGEN), hex(size), str(src_dir), str(out_file), *SPIFFS_FLAGS]
    rel = out_file.relative_to(REPO_ROOT)
    print("  [{}] -> {}  ({} MB)".format(src_dir.name, rel, size // 1024 // 1024))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[FAIL] spiffsgen returned {} for {}".format(result.returncode, rel))
        if result.stdout:
            print("[stdout]")
            print(result.stdout)
        if result.stderr:
            print("[stderr]")
            print(result.stderr)
        raise RuntimeError("spiffsgen failed for {}".format(rel))
    actual = out_file.stat().st_size
    if actual != size:
        raise RuntimeError(
            "Size mismatch for {}: expected {} bytes, got {} bytes".format(rel, size, actual)
        )


def build_lang(lang):
    src = SOURCE_DIR / lang
    if not src.is_dir():
        raise FileNotFoundError("source/{}/ not found".format(lang))
    out_file = REPO_ROOT / AUDIO_TARGET / lang / "storage.bin"
    run_spiffsgen(S3_PARTITION_SIZE, src, out_file)


def main():
    if not SPIFFSGEN.exists():
        print("[ERROR] tools/spiffsgen.py not found.")
        print("Copy it from your ESP-IDF installation:")
        print("  cp $IDF_PATH/components/spiffs/spiffsgen.py tools/")
        sys.exit(1)

    langs = sys.argv[1:] or sorted(d.name for d in SOURCE_DIR.iterdir() if d.is_dir())
    if not langs:
        print("[ERROR] No language folders found in source/")
        sys.exit(1)

    print("Building S3 audio (14.5 MB) into firmware/s3/audio/")
    print("Languages: " + ", ".join(langs))
    print("")
    try:
        for lang in langs:
            print("== {} ==".format(lang))
            build_lang(lang)
        print("")
        print("Done - all output files verified.")
    except Exception as e:
        print("")
        print("[FATAL] " + str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
