# Редизайн структуры firmware/ + дедупликация звука

Дата: 2026-07-30
Статус: утверждён, ждёт плана реализации

## Задача

Сейчас S3-звук (`storage.bin`) дублируется побайтно для робота и пульта: оба
собираются из одного `source/{lang}/`, но кладутся в две ветки —
`firmware/robot/s3/{lang}/` и `firmware/control/s3/{lang}/`. Плюс dev-сборки
держат ещё по своему `storage.bin`. Итого 38 файлов ≈ 578 МБ, половина —
мёртвый вес.

Заодно причёсываем всю иерархию `firmware/`: сейчас prod вложен как
`{device}/{chip}/`, dev — плоский `development/{device}/`, имена app-бинарников
разнобойные (esp32 длинные с суффиксом, s3 короткие). Единой логики нет.

## Целевая структура

Ось: `firmware/{chip}/{channel|audio}/{device}/…`

```
firmware/
├── s3/
│   ├── stable/
│   │   ├── robot/      bootloader.bin · partition-table.bin · robot.bin
│   │   └── control/    bootloader.bin · partition-table.bin · control.bin
│   ├── development/
│   │   ├── robot/      bootloader.bin · partition-table.bin · robot.bin
│   │   └── control/    bootloader.bin · partition-table.bin · control.bin
│   └── audio/
│       └── {lang}/storage.bin          ← 18 языков, ОДИН экземпляр на всё
└── esp32/                              ← legacy, через ~год удаляем ветку целиком
    └── stable/
        ├── robot/      bootloader.bin · partition-table.bin · robot.bin · storage.bin
        └── control/    bootloader.bin · partition-table.bin · control.bin
```

Правила:

- **chip первым уровнем.** Когда ESP32 умрёт, удаляется вся ветка `firmware/esp32/`
  одним движением — манифесты и страница ESP32 к тому времени тоже уберутся.
- **`stable/` и `development/` делятся на `robot/control`** — там бинарники разные
  (`robot.bin` ≠ `control.bin`).
- **`audio/` НЕ делится на robot/control** — звук у них идентичен. Внутри сразу
  языки: `audio/{lang}/storage.bin`. Это исключение из правила, ради него всё и
  затевается.
- **dev не имеет своего audio** — берёт звук из общего `s3/audio/{lang}/`, того же,
  что stable.
- **esp32 — только `stable/`**, без `development/` и без `audio/`. Звук у esp32
  только у робота, не локализован (один файл), делить не с кем — лежит прямо в
  `esp32/stable/robot/storage.bin`.
- **Имена app-бинарников** — везде `robot.bin` / `control.bin` без суффикса чипа
  (чип уже в пути). ESP32-имена `robot_prima_stem_esp32.bin` /
  `control_prima_stem_esp32.bin` переименовываются в `robot.bin` / `control.bin`.

## Языки (18)

ar, ca, da, de, en, es, fr, he, it, ja, nb, nl, pl, pt-BR, ru, sv, tr, uk

## Манифесты

Offset'ы сохраняются от текущих значений, меняются только пути. Все четыре
S3-манифеста ссылаются на один базовый `s3/audio/en/storage.bin`; `index.html`
подменяет `en` на выбранный язык через Blob URL.

| Манифест | Чип | Части (path @ offset) |
|---|---|---|
| `manifest_robot` | ESP32 | `esp32/stable/robot/bootloader.bin`@4096 · `partition-table.bin`@32768 · `robot.bin`@131072 · `storage.bin`@950272 |
| | S3 | `s3/stable/robot/bootloader.bin`@0 · `partition-table.bin`@32768 · `robot.bin`@65536 · `s3/audio/en/storage.bin`@1114112 |
| `manifest_control` | ESP32 | `esp32/stable/control/bootloader.bin`@4096 · `partition-table.bin`@32768 · `control.bin`@65536 |
| | S3 | `s3/stable/control/bootloader.bin`@0 · `partition-table.bin`@32768 · `control.bin`@65536 · `s3/audio/en/storage.bin`@1114112 |
| `manifest_devrobot` | S3 | `s3/development/robot/bootloader.bin`@0 · `partition-table.bin`@32768 · `robot.bin`@65536 · `s3/audio/en/storage.bin`@1114112 |
| `manifest_devcontrol` | S3 | `s3/development/control/bootloader.bin`@0 · `partition-table.bin`@32768 · `control.bin`@65536 · `s3/audio/en/storage.bin`@1114112 |

Robot ESP32 сохраняет несимметричный app-offset `131072` — он реальный, не трогаем.

## index.html

- **HEAD-probe** наличия языков (сейчас `./firmware/robot/s3/{code}/storage.bin`)
  переезжает на `./firmware/s3/audio/{code}/storage.bin`.
- **Ветка `isDev`, прячущая выбор языка, убирается.** Теперь все 4 устройства
  обрабатываются одинаково: язык выбирается и для stable, и для dev; манифест
  всегда патчится через Blob URL. Как следствие — при выборе
  «Robot/Control — development» на странице появляется выбор языка (раньше не было).
- **regex подмены локали** (`/\/[a-z]{2}(?:-[A-Z]{2,3})?\/storage\.bin/`) остаётся —
  путь `.../audio/en/storage.bin` он матчит и заменяет `en` на выбранный язык.
  Проверить, что в новых dev-путях regex не срабатывает на посторонних сегментах
  (bootloader/app storage.bin в пути не содержат — ложных срабатываний нет).
- Нумерация шагов в тексте («3. / 4. Hit button…») выравнивается под то, что язык
  теперь всегда показан.

## tools/build_storage.py

- `PROD_TARGETS` из двух путей (`firmware/robot/s3`, `firmware/control/s3`)
  становится одним: `firmware/s3/audio`. Выход — `firmware/s3/audio/{lang}/storage.bin`.
- `DEV_TARGETS`, функция `build_dev`, флаги `--dev` / `--dev-only` удаляются —
  dev больше не собирает свой storage, берёт из общего audio.
- Комментарий про «10 MB» на строке ~39 поправить: раздел 14.5 МБ (`0x00E80000`).
- ESP32-звук робота скрипт не собирает (и не собирал) — не трогаем.

## Прочее

- **`sync_and_build.bat`** (локальный, в `.gitignore`): robocopy в `source/` не
  меняется; вызов `python tools/build_storage.py` тот же. Обновить только
  комментарии про пути/число файлов.
- **Документация**: `README.md`, `CLAUDE.md`, `docs/PARTITIONS.md` — переописать
  структуру firmware и таблицу манифестов.
- **Перемещение `.bin`**: `git mv` существующих бинарников в новые пути; удалить
  один комплект дублей S3-звука (robot↔control) и оба dev `storage.bin`.

## Что даёт

- `storage.bin`: 38 файлов (~578 МБ) → 18 (~274 МБ). Минус ~304 МБ в рабочей копии.
- Каждая пересборка звука коммитит 18 файлов вместо 38.
- Единая предсказуемая иерархия; удаление legacy-ESP32 в будущем — удаление одной папки.

## Вне зоны

- ESP32 как платформа (доживает ~год, потом отдельной задачей выпиливается целиком).
- Изменение самого звукового контента (это TTS-пайплайн, отдельный репозиторий).
- Раздельные offset'ы / размеры разделов — сохраняются как есть.

## Порядок выката (важно)

Структуру, манифесты, `index.html` и `build_storage.py` менять **одним коммитом** —
пути должны совпасть одновременно, иначе страница обновления сломается между
пушами. GitHub Pages деплоит на каждый push; полурабочего состояния на
`update.primastem.com` быть не должно.
