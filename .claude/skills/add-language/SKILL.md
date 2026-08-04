---
name: add-language
description: >-
  Добавить новый язык озвучки на update.primastem.com (веб-флэшер прошивок PrimaSTEM).
  Используй ВСЕГДА, когда пользователь просит добавить/подключить/собрать новый язык,
  локаль или озвучку для этого репозитория — например «добавь финский», «собери
  раздел с языком X», «возьми готовый язык из TTS-проекта и подключи», даже если
  слово «скилл» или «storage.bin» не произнесено. Покрывает весь путь: копирование
  исходников из TTS-пайплайна → сборка storage.bin → регистрация в index.html →
  проверка → коммит → деплой на боевой.
---

# Добавление нового языка

Языки озвучки — это SPIFFS-образы `storage.bin` (14.5 МБ) в разделе `firmware/s3/audio/{lang}/`.
Один образ общий для robot/control/stable/dev; `index.html` подставляет выбранную локаль в манифест.
Добавить язык = собрать его `storage.bin` из MP3 + зарегистрировать код в `index.html`.

Весь процесс идёт из корня репозитория. Работай на ветке (если на `main` — сначала
`git checkout -b add-lang-{lang}`), потому что финальный push деплоит на боевой.

## Шаг 1 — найти исходники и проверить комплектность

MP3-исходники живут в TTS-пайплайне (отдельный репозиторий), нормализованные — в
`output_norm/{lang}/`:

```
C:/Users/andrei/Documents/Claude/Projects/tts-localization/output_norm/{lang}
```

Прежде чем копировать — **сверь комплект с эталоном** `source/en`. Прошивка обращается
к конкретным именам файлов; если в новом языке не хватает файлов, что есть в английском,
эти звуки на устройстве промолчат. Лишние файлы в новом языке — не проблема.

```bash
SRC="C:/Users/andrei/Documents/Claude/Projects/tts-localization/output_norm/{lang}"
echo "только в en, НЕТ в {lang} (это плохо, если непусто):"
comm -23 <(cd source/en && ls | sort) <(cd "$SRC" && ls | sort) | tr '\n' ' '; echo
echo "только в {lang}, нет в en (это норм):"
comm -13 <(cd source/en && ls | sort) <(cd "$SRC" && ls | sort) | tr '\n' ' '; echo
```

Если «только в en» непусто — покажи список пользователю и спроси, осознанный ли это
пропуск, прежде чем продолжать. Не решай молча.

## Шаг 2 — скопировать в source/ и собрать раздел

`source/` в `.gitignore` (в git не попадёт — это ожидаемо, коммитится только `storage.bin`).

```bash
cp -r "$SRC" source/{lang}
python tools/build_storage.py {lang}
```

Скрипт пишет `firmware/s3/audio/{lang}/storage.bin`, сам проверяет размер (ровно
15 204 352 байт = 14.5 МБ) и падает при ошибке. Если `spiffsgen.py` не найден —
он не в git, копируется из ESP-IDF (см. README).

## Шаг 3 — зарегистрировать язык в index.html

Без этой правки сайт язык не покажет (он пробит HEAD-запросом, но кнопки не будет).
Добавь запись в массив `ALL_LANGS` — **код + родное самоназвание** (endonym), не
английское имя:

```js
{ code: '{lang}', name: '{Endonym}' },
```

Примеры уже в файле: `fi` → `Suomi`, `de` → `Deutsch`, `pt-BR` → `Português (Brasil)`,
`ar` → `العربية`, `he` → `עברית`. RTL-языки (арабский, иврит) указывают код только в
аудио-пути — UI просто рисует самоназвание, ничего дополнительно настраивать не надо.
Двухбуквенные коды и формы вида `pt-BR` regex подмены локали обрабатывает штатно.

## Шаг 4 — проверить

```bash
python tools/verify_manifests.py
```

Ждём `[OK] 4 манифестов, N языков — все пути существуют` (N вырастет на 1). Верификатор
подтверждает, что у каждого языка из `index.html` есть свой `storage.bin`.

## Шаг 5 — коммит

Коммитятся только `storage.bin` и `index.html` (исходники в `source/` игнорируются):

```bash
git add firmware/s3/audio/{lang}/storage.bin index.html
git commit -m "Add {Language} ({lang}) audio + language option"
```

## Шаг 6 — деплой (спроси разрешение)

Push в `main` мгновенно деплоит на боевой `update.primastem.com` (GitHub Pages).
Это outward-facing — **не пуши без явного «да» от пользователя**. Если работал в ветке,
сначала влей в main (`git checkout main && git merge --ff-only add-lang-{lang}`), потом:

```bash
git push origin main
```

Замечание: на большом объёме push может показать таймаут команды, хотя данные заливаются.
Проверяй фактом — сравни локальный HEAD с origin:

```bash
git rev-parse HEAD && git ls-remote origin main | head -1
```

## Шаг 7 — проверить, что деплой докатился

GitHub Pages деплоит через CDN за ~1 минуту. Проверяй не заголовком, а **сравнением
содержимого** (md5) с обходом кэша — так видно, что боевой отдаёт именно новый образ:

```bash
local=$(md5sum firmware/s3/audio/{lang}/storage.bin | cut -d' ' -f1)
for i in $(seq 1 8); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -I "https://update.primastem.com/firmware/s3/audio/{lang}/storage.bin?cb=$RANDOM")
  if [ "$code" = "200" ]; then
    remote=$(curl -s "https://update.primastem.com/firmware/s3/audio/{lang}/storage.bin?cb=$RANDOM" | md5sum | cut -d' ' -f1)
    [ "$remote" = "$local" ] && { echo "docat: md5 совпал"; break; } || echo "$i: 200, md5 ещё старый"
  else echo "$i: ещё $code"; fi
  sleep 25
done
```

## После — обнови память

Если у языка была особенность (например неполный комплект `xNNN`-файлов, как у арабского),
запиши это. Проверить звучание на реальном железе может только пользователь — структура
и веб-часть проверяются здесь, но воспроизведение на устройстве нет; напомни об этом,
если комплект расходился с эталоном.
