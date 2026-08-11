# Firmware Structure Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Переехать на структуру `firmware/{chip}/{stable|development|audio}/{device}` и убрать дублирование S3-звука (robot↔control и dev), сведя 38 `storage.bin` к 18.

**Architecture:** Chip-first иерархия. Звук S3 общий на всё — один комплект в `firmware/s3/audio/{lang}/`, на который ссылаются все четыре манифеста; `index.html` подменяет язык через Blob URL. ESP32 — legacy-ветка `firmware/esp32/stable/` без dev и без audio. Архивы вынесены в `firmware/_archive/`.

**Tech Stack:** Статический сайт (GitHub Pages), esp-web-tools v10, Python 3 для сборки SPIFFS. Ни билд-процесса, ни тест-фреймворка — «тест» это `tools/verify_manifests.py`, проверяющий согласованность манифестов и файлов на диске.

## Global Constraints

- **Атомарный выкат.** GitHub Pages деплоит на каждый push в `main`. Все локальные коммиты допустимы, но **push — единожды, в самом конце** (Task 11), после зелёного верификатора. Полурабочего состояния на `update.primastem.com` быть не должно.
- **Offset'ы не меняются** — копируются дословно из текущих манифестов. Меняются только `path`.
- **App-бинарники везде `robot.bin` / `control.bin`** без суффикса чипа.
- **18 языков:** ar, ca, da, de, en, es, fr, he, it, ja, nb, nl, pl, pt-BR, ru, sv, tr, uk.
- **`audio/` не делится на robot/control** — сразу языки.
- Работать через `git mv` (сохраняет историю), не через delete+add.
- Спека: `docs/FIRMWARE_STRUCTURE_DESIGN.md`.

---

## Целевая структура (справка)

```
firmware/
├── s3/
│   ├── stable/{robot,control}/     bootloader.bin · partition-table.bin · {robot,control}.bin
│   ├── development/{robot,control}/ bootloader.bin · partition-table.bin · {robot,control}.bin
│   └── audio/{lang}/storage.bin     ← 18 языков
├── esp32/
│   └── stable/
│       ├── robot/    bootloader.bin · partition-table.bin · robot.bin · storage.bin
│       └── control/  bootloader.bin · partition-table.bin · control.bin
└── _archive/
    ├── s3/{robot,control}/          ← из {robot,control}/s3/arhiv/
    └── development/{robot,control}/{arhiv,1705}/
```

---

### Task 1: Верификатор манифестов (наш «тест»)

**Files:**
- Create: `tools/verify_manifests.py`

**Interfaces:**
- Produces: скрипт-гейт. Запускается `python tools/verify_manifests.py`; exit 0 = все `part.path` во всех `manifest_*.json` существуют И для каждого языка из `index.html` `ALL_LANGS` существует `firmware/s3/audio/{lang}/storage.bin`; exit 1 = есть расхождения (печатает список).
- Инвариант используется как гейт после каждой следующей задачи.

- [ ] **Step 1: Написать верификатор**

```python
#!/usr/bin/env python3
"""Проверка согласованности манифестов и файлов на диске.

Exit 0 — все part.path существуют и все языки из index.html имеют audio.
Exit 1 — есть расхождения (печатает их).
"""
import json
import re
import sys
from pathlib import Path

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
```

- [ ] **Step 2: Запустить на текущей (ещё старой) структуре**

Run: `python tools/verify_manifests.py`
Expected: **FAIL** — текущие манифесты указывают на `firmware/s3/audio/…`? Нет, ещё на старые пути. На данном этапе манифесты старые, а `firmware/s3/audio/` не существует → верификатор упадёт на проверке языков (шаг 2) и, если запускать после правок, на путях. Это нормально: красный до Task 7+. Убедиться, что скрипт запускается и печатает список, а не падает с traceback.

- [ ] **Step 3: Commit**

```bash
git add tools/verify_manifests.py
git commit -m "Add manifest/disk consistency verifier"
```

---

### Task 2: Переезд ESP32 stable

**Files:**
- Move: `firmware/robot/esp32/*` → `firmware/esp32/stable/robot/*` (app переименовать)
- Move: `firmware/control/esp32/*` → `firmware/esp32/stable/control/*` (app переименовать)

**Interfaces:**
- Produces пути: `firmware/esp32/stable/robot/{bootloader.bin,partition-table.bin,robot.bin,storage.bin}`, `firmware/esp32/stable/control/{bootloader.bin,partition-table.bin,control.bin}`.

- [ ] **Step 1: Создать каталоги и перенести robot**

```bash
mkdir -p firmware/esp32/stable/robot firmware/esp32/stable/control
git mv firmware/robot/esp32/bootloader.bin        firmware/esp32/stable/robot/bootloader.bin
git mv firmware/robot/esp32/partition-table.bin   firmware/esp32/stable/robot/partition-table.bin
git mv firmware/robot/esp32/robot_prima_stem_esp32.bin firmware/esp32/stable/robot/robot.bin
git mv firmware/robot/esp32/storage.bin           firmware/esp32/stable/robot/storage.bin
```

- [ ] **Step 2: Перенести control**

```bash
git mv firmware/control/esp32/bootloader.bin      firmware/esp32/stable/control/bootloader.bin
git mv firmware/control/esp32/partition-table.bin firmware/esp32/stable/control/partition-table.bin
git mv firmware/control/esp32/control_prima_stem_esp32.bin firmware/esp32/stable/control/control.bin
```

- [ ] **Step 3: Проверить, что старые esp32-папки пусты и удалить**

Run: `ls -la firmware/robot/esp32 firmware/control/esp32 2>/dev/null`
Expected: пусто или каталогов нет. Если пусто — `rmdir firmware/robot/esp32 firmware/control/esp32`.
Проверить новые: `ls firmware/esp32/stable/robot firmware/esp32/stable/control` — 4 и 3 файла соответственно.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Move ESP32 firmware to firmware/esp32/stable/{device}, rename app to {device}.bin"
```

---

### Task 3: Переезд S3 stable (app/bootloader/partition)

**Files:**
- Move: `firmware/robot/s3/{bootloader,partition-table,robot}.bin` → `firmware/s3/stable/robot/`
- Move: `firmware/control/s3/{bootloader,partition-table,control}.bin` → `firmware/s3/stable/control/`

**Interfaces:**
- Produces: `firmware/s3/stable/robot/{bootloader.bin,partition-table.bin,robot.bin}`, `firmware/s3/stable/control/{bootloader.bin,partition-table.bin,control.bin}`.
- Языковые папки `{robot,control}/s3/{lang}/` и `arhiv/` этой задачей НЕ трогаются — уедут в Task 4 и Task 6.

- [ ] **Step 1: Создать каталоги и перенести**

```bash
mkdir -p firmware/s3/stable/robot firmware/s3/stable/control
git mv firmware/robot/s3/bootloader.bin       firmware/s3/stable/robot/bootloader.bin
git mv firmware/robot/s3/partition-table.bin  firmware/s3/stable/robot/partition-table.bin
git mv firmware/robot/s3/robot.bin            firmware/s3/stable/robot/robot.bin
git mv firmware/control/s3/bootloader.bin      firmware/s3/stable/control/bootloader.bin
git mv firmware/control/s3/partition-table.bin firmware/s3/stable/control/partition-table.bin
git mv firmware/control/s3/control.bin         firmware/s3/stable/control/control.bin
```

- [ ] **Step 2: Проверить**

Run: `ls firmware/s3/stable/robot firmware/s3/stable/control`
Expected: по 3 файла в каждом. `firmware/robot/s3/` и `firmware/control/s3/` ещё содержат языковые папки и `arhiv/` — это ожидаемо.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "Move S3 stable app/bootloader to firmware/s3/stable/{device}"
```

---

### Task 4: Дедупликация и переезд S3-звука

**Files:**
- Move: `firmware/robot/s3/{lang}/storage.bin` (18 шт) → `firmware/s3/audio/{lang}/storage.bin`
- Delete: `firmware/control/s3/{lang}/storage.bin` (18 дублей)
- Delete: `firmware/development/robot/storage.bin`, `firmware/development/control/storage.bin`

**Interfaces:**
- Produces: `firmware/s3/audio/{lang}/storage.bin` для всех 18 языков. Единственный источник S3-звука для stable и dev, robot и control.
- Предусловие (проверить в Step 1): `robot/s3/{lang}/storage.bin` побайтно равны `control/s3/{lang}/storage.bin` — иначе дедуп неверен.

- [ ] **Step 1: Подтвердить идентичность перед удалением дублей**

```bash
for l in ar ca da de en es fr he it ja nb nl pl pt-BR ru sv tr uk; do
  a=$(md5sum firmware/robot/s3/$l/storage.bin | cut -d' ' -f1)
  b=$(md5sum firmware/control/s3/$l/storage.bin | cut -d' ' -f1)
  [ "$a" = "$b" ] || echo "MISMATCH: $l"
done; echo "проверка завершена"
```
Expected: ни одной строки `MISMATCH`. Если есть — СТОП, дедуп нельзя делать вслепую, разбираться отдельно.

- [ ] **Step 2: Перенести robot-комплект звука в общий audio/**

```bash
mkdir -p firmware/s3/audio
for l in ar ca da de en es fr he it ja nb nl pl pt-BR ru sv tr uk; do
  mkdir -p firmware/s3/audio/$l
  git mv firmware/robot/s3/$l/storage.bin firmware/s3/audio/$l/storage.bin
done
```

- [ ] **Step 3: Удалить дубли control и dev-storage**

```bash
for l in ar ca da de en es fr he it ja nb nl pl pt-BR ru sv tr uk; do
  git rm firmware/control/s3/$l/storage.bin
done
git rm firmware/development/robot/storage.bin firmware/development/control/storage.bin
```

- [ ] **Step 4: Проверить**

Run: `ls firmware/s3/audio | wc -l && find firmware/s3/audio -name storage.bin | wc -l`
Expected: `18` и `18`. Пустые языковые папки в `robot/s3` и `control/s3` подчистить: `find firmware/robot/s3 firmware/control/s3 -type d -empty -delete`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "Deduplicate S3 audio into firmware/s3/audio/{lang} (38 -> 18 storage.bin)"
```

---

### Task 5: Переезд S3 development

**Files:**
- Move: `firmware/development/robot/{bootloader,partition-table,robot}.bin` → `firmware/s3/development/robot/`
- Move: `firmware/development/control/{bootloader,partition-table,control}.bin` → `firmware/s3/development/control/`

**Interfaces:**
- Produces: `firmware/s3/development/robot/{bootloader.bin,partition-table.bin,robot.bin}`, `firmware/s3/development/control/{bootloader.bin,partition-table.bin,control.bin}`.
- `arhiv/` и `1705/` в `firmware/development/{device}/` НЕ трогаются — уедут в Task 6.

- [ ] **Step 1: Создать каталоги и перенести**

```bash
mkdir -p firmware/s3/development/robot firmware/s3/development/control
git mv firmware/development/robot/bootloader.bin       firmware/s3/development/robot/bootloader.bin
git mv firmware/development/robot/partition-table.bin  firmware/s3/development/robot/partition-table.bin
git mv firmware/development/robot/robot.bin            firmware/s3/development/robot/robot.bin
git mv firmware/development/control/bootloader.bin      firmware/s3/development/control/bootloader.bin
git mv firmware/development/control/partition-table.bin firmware/s3/development/control/partition-table.bin
git mv firmware/development/control/control.bin         firmware/s3/development/control/control.bin
```

- [ ] **Step 2: Проверить**

Run: `ls firmware/s3/development/robot firmware/s3/development/control`
Expected: по 3 файла. `firmware/development/{robot,control}/` ещё держат `arhiv/` и `1705/`.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "Move S3 dev firmware to firmware/s3/development/{device}"
```

---

### Task 6: Архивы в firmware/_archive/

**Files:**
- Move: `firmware/robot/s3/arhiv/` → `firmware/_archive/s3/robot/`
- Move: `firmware/control/s3/arhiv/` → `firmware/_archive/s3/control/`
- Move: `firmware/development/robot/{arhiv,1705}/` → `firmware/_archive/development/robot/{arhiv,1705}/`
- Move: `firmware/development/control/{arhiv,1705}/` → `firmware/_archive/development/control/{arhiv,1705}/`

**Interfaces:**
- Produces: все исторические бинарники под `firmware/_archive/`. После этой задачи старые корни `firmware/robot/`, `firmware/control/`, `firmware/development/` должны исчезнуть полностью.

- [ ] **Step 1: Перенести s3-архивы**

```bash
mkdir -p firmware/_archive/s3
git mv firmware/robot/s3/arhiv    firmware/_archive/s3/robot
git mv firmware/control/s3/arhiv  firmware/_archive/s3/control
```

- [ ] **Step 2: Перенести dev-архивы и снапшоты**

```bash
mkdir -p firmware/_archive/development/robot firmware/_archive/development/control
git mv firmware/development/robot/arhiv firmware/_archive/development/robot/arhiv
git mv firmware/development/robot/1705  firmware/_archive/development/robot/1705
git mv firmware/development/control/arhiv firmware/_archive/development/control/arhiv
git mv firmware/development/control/1705  firmware/_archive/development/control/1705
```

- [ ] **Step 3: Убедиться, что старые корни исчезли**

```bash
find firmware/robot firmware/control firmware/development -type f 2>/dev/null; echo "---"
find firmware -maxdepth 1 -type d
```
Expected: первый `find` пуст (файлов не осталось). Пустые каталоги удалить: `find firmware/robot firmware/control firmware/development -type d -empty -delete 2>/dev/null`. Второй `find` показывает только `firmware/s3`, `firmware/esp32`, `firmware/_archive`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Move archives and dated snapshots to firmware/_archive/"
```

---

### Task 7: Обновить манифесты

**Files:**
- Modify: `manifest_robot.json`, `manifest_control.json`, `manifest_devrobot.json`, `manifest_devcontrol.json`

**Interfaces:**
- Consumes: все новые пути из Task 2–6.
- Produces: манифесты, чьи `part.path` указывают на существующие файлы. После этой задачи верификатор (Task 1) должен стать ЗЕЛЁНЫМ.

- [ ] **Step 1: `manifest_robot.json` — заменить пути (offset'ы сохранить)**

ESP32 build parts:
```json
{ "path": "firmware/esp32/stable/robot/bootloader.bin", "offset": 4096 },
{ "path": "firmware/esp32/stable/robot/partition-table.bin", "offset": 32768 },
{ "path": "firmware/esp32/stable/robot/robot.bin", "offset": 131072 },
{ "path": "firmware/esp32/stable/robot/storage.bin", "offset": 950272 }
```
ESP32-S3 build parts:
```json
{ "path": "firmware/s3/stable/robot/bootloader.bin", "offset": 0 },
{ "path": "firmware/s3/stable/robot/partition-table.bin", "offset": 32768 },
{ "path": "firmware/s3/stable/robot/robot.bin", "offset": 65536 },
{ "path": "firmware/s3/audio/en/storage.bin", "offset": 1114112 }
```

- [ ] **Step 2: `manifest_control.json`**

ESP32 build parts:
```json
{ "path": "firmware/esp32/stable/control/bootloader.bin", "offset": 4096 },
{ "path": "firmware/esp32/stable/control/partition-table.bin", "offset": 32768 },
{ "path": "firmware/esp32/stable/control/control.bin", "offset": 65536 }
```
ESP32-S3 build parts:
```json
{ "path": "firmware/s3/stable/control/bootloader.bin", "offset": 0 },
{ "path": "firmware/s3/stable/control/partition-table.bin", "offset": 32768 },
{ "path": "firmware/s3/stable/control/control.bin", "offset": 65536 },
{ "path": "firmware/s3/audio/en/storage.bin", "offset": 1114112 }
```

- [ ] **Step 3: `manifest_devrobot.json` (только ESP32-S3 build)**

```json
{ "path": "firmware/s3/development/robot/bootloader.bin", "offset": 0 },
{ "path": "firmware/s3/development/robot/partition-table.bin", "offset": 32768 },
{ "path": "firmware/s3/development/robot/robot.bin", "offset": 65536 },
{ "path": "firmware/s3/audio/en/storage.bin", "offset": 1114112 }
```

- [ ] **Step 4: `manifest_devcontrol.json` (только ESP32-S3 build)**

```json
{ "path": "firmware/s3/development/control/bootloader.bin", "offset": 0 },
{ "path": "firmware/s3/development/control/partition-table.bin", "offset": 32768 },
{ "path": "firmware/s3/development/control/control.bin", "offset": 65536 },
{ "path": "firmware/s3/audio/en/storage.bin", "offset": 1114112 }
```

- [ ] **Step 5: Запустить верификатор — теперь должен пройти**

Run: `python tools/verify_manifests.py`
Expected: **[OK] 4 манифестов, 18 языков — все пути существуют.** Если FAIL — исправить путь, на который жалуется, до зелёного.

- [ ] **Step 6: Commit**

```bash
git add manifest_robot.json manifest_control.json manifest_devrobot.json manifest_devcontrol.json
git commit -m "Point all manifests at new firmware paths + shared s3/audio"
```

---

### Task 8: Обновить tools/build_storage.py

**Files:**
- Modify: `tools/build_storage.py`

**Interfaces:**
- Consumes: новый путь `firmware/s3/audio`.
- Produces: `build_storage.py`, пишущий в `firmware/s3/audio/{lang}/storage.bin`; dev-логика удалена.

- [ ] **Step 1: Заменить таргеты и выкинуть dev-ветку**

Заменить `PROD_TARGETS` / `DEV_TARGETS` и функции сборки. `build_lang_prod` пишет в единственный общий каталог:

```python
# Единственный общий каталог S3-звука (robot и control берут отсюда)
AUDIO_TARGET = "firmware/s3/audio"


def build_lang(lang):
    src = SOURCE_DIR / lang
    if not src.is_dir():
        raise FileNotFoundError("source/{}/ not found".format(lang))
    out_file = REPO_ROOT / AUDIO_TARGET / lang / "storage.bin"
    run_spiffsgen(S3_PARTITION_SIZE, src, out_file)
```

- [ ] **Step 2: Упростить `main()` — убрать `--dev` / `--dev-only`**

```python
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
```

- [ ] **Step 3: Поправить комментарий про размер раздела**

Строку `# ESP32-S3 storage partition size, identical for prod and dev (10 MB)` заменить на `# ESP32-S3 storage partition size, 14.5 MB`. Обновить docstring (убрать упоминания dev-таргетов и `--dev`).

- [ ] **Step 4: Тест — пересобрать один язык и проверить, что пишет в новый путь**

Run: `python tools/build_storage.py en && ls -la firmware/s3/audio/en/storage.bin`
Expected: `Done - all output files verified.` и файл 15204352 байт по новому пути. `git status` покажет `firmware/s3/audio/en/storage.bin` изменённым (пересобран) — это ок.

- [ ] **Step 5: Commit**

```bash
git add tools/build_storage.py firmware/s3/audio/en/storage.bin
git commit -m "build_storage.py: single shared s3/audio target, drop dev logic"
```

---

### Task 9: Обновить index.html

**Files:**
- Modify: `index.html` (script-блок)

**Interfaces:**
- Consumes: путь `firmware/s3/audio/{lang}/storage.bin`.
- Produces: страница показывает выбор языка для всех 4 устройств (включая dev); все манифесты патчатся через Blob URL единообразно.

- [ ] **Step 1: Переkey HEAD-probe на новый путь**

В `loadLanguages()` заменить строку пробы:
```javascript
const res = await fetch(`./firmware/s3/audio/${lang.code}/storage.bin`, { method: 'HEAD' });
```

- [ ] **Step 2: Убрать спец-ветку `isDev` для выбора языка**

В обработчике выбора устройства (`input[name="device"]`) сейчас dev прячет `lang-step`. Сделать выбор языка видимым всегда:
```javascript
document.querySelectorAll('input[name="device"]').forEach(radio =>
  radio.addEventListener('change', () => {
    selectedDevice = radio.value;
    document.getElementById('lang-step').classList.remove('hidden');
    document.getElementById('connect-label').textContent =
      '4. Hit button (Connect) BELOW and select the correct USB-COM port. (Requires Chrome or Edge.)';
    updateManifest();
  })
);
```

- [ ] **Step 3: Патчить манифест единообразно (dev тоже через Blob)**

В `updateManifest()` убрать раннюю ветку `if (isDev(...)) { button.manifest = ...; return }`. Требовать язык для всех: заменить гейт `if (!isDev(selectedDevice) && !selectedLang) return;` на `if (!selectedLang) return;`. Блок `fetch(manifest) → патч пути → Blob` применять ко всем устройствам. Функцию `isDev` можно удалить, если больше нигде не используется (проверить grep по файлу).

- [ ] **Step 4: Проверить regex подмены локали на dev-путях**

Regex `/\/[a-z]{2}(?:-[A-Z]{2,3})?\/storage\.bin/` применяется только к part с `chipFamily === 'ESP32-S3'`. В новых путях `/storage.bin` встречается лишь в audio-части (`firmware/s3/audio/en/storage.bin`), в bootloader/app-частях — нет. Значит regex тронет только звук. Убедиться визуально, что условие `if (build.chipFamily === 'ESP32-S3')` сохранено.

- [ ] **Step 5: Тест — прогнать страницу локально**

Run: `python -m http.server 8000` (в отдельном окне), затем открыть `http://localhost:8000` в браузере (или через browser-tool).
Проверить вручную:
- Выбор «Robot» → шаг 3 «Select language» виден, языки подгрузились (18).
- Выбор «Robot — development» → выбор языка тоже виден.
- В DevTools Network при клике языка — манифест это `blob:`; внутри `part.path` для storage указывает на выбранный язык.
Остановить сервер после проверки.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "index.html: probe new audio path, show language for all devices incl. dev"
```

---

### Task 10: Обновить документацию

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/PARTITIONS.md`, `sync_and_build.bat`

**Interfaces:**
- Produces: документация описывает новую структуру.

- [ ] **Step 1: `CLAUDE.md` — секция Architecture**

Обновить дерево `Firmware directory layout` и таблицу манифестов под новую структуру (chip-first, `s3/audio/`, `esp32/stable/`, `_archive/`). Убрать строку «production S3 manifests currently point to en/storage.bin» — заменить описанием общего `s3/audio/{lang}` + Blob-подмена. Обновить раздел «Switching localization» (путь теперь `firmware/s3/audio/{lang}`). Memory offsets — оставить (не менялись).

- [ ] **Step 2: `README.md`**

Привести любые пути/деревья к новой структуре (проверить `grep -n "firmware/" README.md`).

- [ ] **Step 3: `docs/PARTITIONS.md`**

Обновить пути в таблице разделов (в `.gitignore`, но на диске держим актуальным). `grep -n "firmware/" docs/PARTITIONS.md`.

- [ ] **Step 4: `sync_and_build.bat` (локальный, gitignore)**

robocopy в `source/` и вызов `python tools/build_storage.py` не меняются. Обновить только комментарий-шапку: «15 languages x 2 devices + dev» → «18 языков, единый s3/audio». Файл в `.gitignore` — в коммит не попадёт, правим ради актуальности на машине.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: describe chip-first firmware structure + shared audio"
```
(`docs/PARTITIONS.md` и `sync_and_build.bat` в .gitignore — в коммит не войдут, это ожидаемо.)

---

### Task 11: Полная верификация, пересборка звука и выкат

**Files:**
- Potentially rebuild: `firmware/s3/audio/{lang}/storage.bin` (все 18)

**Interfaces:**
- Consumes: всё из Task 1–10.
- Produces: согласованное состояние, готовое к единственному push.

- [ ] **Step 1: Полная пересборка всех языков в новый путь**

Run: `python tools/build_storage.py`
Expected: `Done - all output files verified.` 18 языков в `firmware/s3/audio/`.

- [ ] **Step 2: Верификатор — зелёный**

Run: `python tools/verify_manifests.py`
Expected: `[OK] 4 манифестов, 18 языков — все пути существуют.`

- [ ] **Step 3: JSON-валидность всех манифестов**

Run: `for f in manifest_*.json; do python -c "import json,sys; json.load(open('$f')); print('$f OK')"; done`
Expected: 4 строки `... OK`.

- [ ] **Step 4: Проверка, что живая структура чистая**

Run: `find firmware -maxdepth 2 -type d | sort`
Expected: только `firmware/s3/{stable,development,audio}`, `firmware/esp32/stable`, `firmware/_archive/{s3,development}`. Никаких `firmware/robot`, `firmware/control`, `firmware/development` в корне.

- [ ] **Step 5: Локальная проверка страницы (если не делалась в Task 9 Step 5)**

`python -m http.server 8000` → открыть, прощёлкать все 4 устройства + смену языка, убедиться что кнопка Install активируется и манифест-blob содержит верные пути. Остановить сервер.

- [ ] **Step 6: Финальный коммит пересборки (если звук изменился) и push**

```bash
git add -A
git status                      # обзор перед выкатом
git commit -m "Rebuild all 18 audio images into s3/audio" || echo "нечего коммитить"
git push
```
Expected: push проходит; GitHub Pages деплоит цельную новую структуру за один раз. После деплоя (~1 мин) проверить `https://update.primastem.com` — устройства и языки работают.

---

## Self-Review

**Spec coverage:**
- Целевая структура (chip-first, audio без robot/control, esp32 без dev/audio) → Task 2–6. ✓
- Дедуп 38→18 → Task 4. ✓
- Манифесты, offset'ы сохранены → Task 7. ✓
- index.html (HEAD-probe, isDev убран, regex, нумерация) → Task 9. ✓
- build_storage.py (один таргет, dev убран, комментарий 14.5 МБ) → Task 8. ✓
- Документация (README, CLAUDE.md, PARTITIONS.md, sync_and_build.bat) → Task 10. ✓
- Архивы в _archive/ → Task 6. ✓
- Атомарный выкат одним push → Global Constraints + Task 11. ✓
- ESP32-звук в esp32/stable/robot/ → Task 2. ✓
- Имена app без суффикса чипа → Task 2 (esp32 rename), остальные уже robot.bin/control.bin. ✓

**Placeholder scan:** плейсхолдеров нет; весь код и команды приведены дословно.

**Type consistency:** пути согласованы между задачами (Produces одной = Consumes следующей). Имя `build_lang` в build_storage.py вводится в Task 8 и там же используется. Верификатор `tools/verify_manifests.py` вводится в Task 1, используется в Task 7/11.

**Замечание по порядку:** верификатор красный между Task 2 и Task 7 (файлы переехали, манифесты ещё нет) — это ожидаемо и безопасно, потому что push только в Task 11. Локальные коммиты промежуточного состояния допустимы.
```
