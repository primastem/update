#!/usr/bin/env python3
"""
Generate SPIFFS storage.bin for PrimaSTEM firmware from language source folders.

Usage:
    python tools/build_storage.py                 # build ALL langs for prod
    python tools/build_storage.py ru              # build only Russian for prod
    python tools/build_storage.py ru en fr        # build multiple langs for prod
    python tools/build_storage.py en --dev        # build prod EN + dev EN (10 MB)
    python tools/build_storage.py en --dev-only   # build only dev EN (10 MB)

Prerequisites:
    Copy spiffsgen.py from ESP-IDF into tools/:
        cp $IDF_PATH/components/spiffs/spiffsgen.py tools/

Output:
    Prod (8 MB partition, S3):
        firmware/robot/s3/{lang}/storage.bin
        firmware/control/s3/{lang}/storage.bin
    Dev (10 MB partition, S3) - single file, no per-lang folder:
        firmware/development/robot/storage.bin
        firmware/development/control/storage.bin

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

# S3 production partition table: storage size = 0x00800000 (8 MB)
PROD_PARTITION_SIZE = 0x00800000
# S3 development partition table: storage size = 0x00A00000 (10 MB)
DEV_PARTITION_SIZE  = 0x00A00000

# Must match firmware partition table and menuconfig
SPIFFS_FLAGS = [
    "--page-size=256",
    "--obj-name-len=32",
    "--meta-len=4",
    "--use-magic",
    "--use-magic-len",
]

PROD_TARGETS = [
    "firmware/robot/s3",
    "firmware/control/s3",
]
DEV_TARGETS = [
    "firmware/development/robot",
    "firmware/development/control",
]


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


def build_lang_prod(lang):
    src = SOURCE_DIR / lang
    if not src.is_dir():
        raise FileNotFoundError("source/{}/ not found".format(lang))
    for target in PROD_TARGETS:
        out_file = REPO_ROOT / target / lang / "storage.bin"
        run_spiffsgen(PROD_PARTITION_SIZE, src, out_file)


def build_dev(lang):
    """Build the dev storage image (10 MB) from one language source.
    Dev firmware uses a single storage.bin (no per-language folder)."""
    src = SOURCE_DIR / lang
    if not src.is_dir():
        raise FileNotFoundError("source/{}/ not found".format(lang))
    for target in DEV_TARGETS:
        out_file = REPO_ROOT / target / "storage.bin"
        run_spiffsgen(DEV_PARTITION_SIZE, src, out_file)


def main():
    if not SPIFFSGEN.exists():
        print("[ERROR] tools/spiffsgen.py not found.")
        print("Copy it from your ESP-IDF installation:")
        print("  cp $IDF_PATH/components/spiffs/spiffsgen.py tools/")
        sys.exit(1)

    args = list(sys.argv[1:])
    dev_mode = False
    dev_only = False
    if "--dev-only" in args:
        dev_only = True
        dev_mode = True
        args.remove("--dev-only")
    if "--dev" in args:
        dev_mode = True
        args.remove("--dev")

    langs = args if args else sorted(d.name for d in SOURCE_DIR.iterdir() if d.is_dir())
    if not langs:
        print("[ERROR] No language folders found in source/")
        sys.exit(1)

    if dev_only:
        mode_label = "dev only (10 MB)"
    elif dev_mode:
        mode_label = "prod (8 MB) + dev (10 MB)"
    else:
        mode_label = "prod (8 MB)"
    print("Mode: " + mode_label)
    print("Languages: " + ", ".join(langs))
    print("")

    try:
        if not dev_only:
            for lang in langs:
                print("== Building PROD: {} ==".format(lang))
                build_lang_prod(lang)
        if dev_mode:
            dev_lang = langs[-1]
            if len(langs) > 1:
                print("[NOTE] dev has no per-language folder; bundling '{}' only.".format(dev_lang))
            print("== Building DEV: {} ==".format(dev_lang))
            build_dev(dev_lang)
        print("")
        print("Done - all output files verified.")
    except Exception as e:
        print("")
        print("[FATAL] " + str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
