#!/usr/bin/env python3
"""Проверка согласованности манифестов и файлов на диске.

Exit 0 — все part.path существуют и все языки из index.html имеют audio.
Exit 1 — есть расхождения (печатает их).
"""
import json
import re
import sys
from pathlib import Path

# Windows-консоль по умолчанию не UTF-8 — иначе кириллица в кракозябры
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).parent.parent
MANIFESTS = sorted(REPO.glob("manifest_*.json"))
INDEX = REPO / "index.html"
AUDIO_DIR = REPO / "firmware" / "s3" / "audio"

problems = []

# 1. Каждый part.path в каждом манифесте существует
for m in MANIFESTS:
    try:
        data = json.loads(m.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        problems.append(f"{m.name}: невалидный JSON — {e}")
        continue
    for build in data.get("builds", []):
        chip = build.get("chipFamily", "?")
        for part in build.get("parts", []):
            p = REPO / part["path"]
            if not p.is_file():
                problems.append(f"{m.name} [{chip}]: нет файла {part['path']}")

# 2. Все языки из ALL_LANGS в index.html имеют audio/{lang}/storage.bin
text = INDEX.read_text(encoding="utf-8")
codes = re.findall(r"code:\s*'([^']+)'", text)
if not codes:
    problems.append("index.html: не удалось извлечь ALL_LANGS (code: '..')")
for code in codes:
    if not (AUDIO_DIR / code / "storage.bin").is_file():
        problems.append(f"index.html: язык {code} без firmware/s3/audio/{code}/storage.bin")

if problems:
    print("[FAIL] Расхождения:")
    for pr in problems:
        print("  - " + pr)
    sys.exit(1)
print(f"[OK] {len(MANIFESTS)} манифестов, {len(codes)} языков — все пути существуют.")
sys.exit(0)
