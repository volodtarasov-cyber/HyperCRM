---
тип: отчёт о миграции
проект: Обновление системы
дата: 2026-08-11
статус: завершено, с хвостами
---

# Миграция волта macOS → Windows

> Источник: архив старого волта `HyperCRM (3)` из папки Downloads (полный слепок `/Users/vladimirtarasov/Yandex.Disk.localized/HyperCRM`).
> Приёмник: `D:\SecondBrain\HyperCRM`.

## 1. Что было до переноса

Волт на Windows существовал как **каркас из пустых папок**. Реальных файлов — 545, и те частичные: скилы, one-product-flow и knowledge лежали отдельно в корне `D:\SecondBrain` с двойной вложенностью, а в самом волте под них были пустые каталоги-заглушки. Методбаза `agency-os`, на которую ссылаются все скилы, отсутствовала целиком — 12 путей вида `agency-os/methods/...` не резолвились.

## 2. Что перенесено

Стало **1020 файлов**, из них 950 под git.

| Раздел | Файлов | Что приехало |
|---|---:|---|
| `projects/agency-os/` | 154 | методбаза: methods, modules, templates, course-notes, visual-maps, sources |
| `projects/detailing-samara/` | 1005 | marketing/funnels, analytics, sales, reports, meetings |
| `projects/traffic-freelance/` | 32 | клиенты, гипотезы |
| `projects/ai-infobiz/` | 28 | content-pipeline, product/community-roadmap |
| `.tools/` | 113 | universal (web, pdf, telegram-vault, yougile, wordstat) + проектные скрипты |
| `system/` | 19 | changelog, 11 analyze-скриптов, шаблоны, secrets |
| `life/`, `team/`, `daily/`, `outputs/` | 107 | decisions, финпланы, ten-report, агентство |
| корень | 6 | CLAUDE.md, AGENTS.md, README, tasks.md, inbox.md |

**Намеренно не переносил:** macOS-venv (127 МБ, posix-разметка — на Windows не запускается), `node_modules` прототипа (24 335 файлов, ставится `pnpm install`), пустой `.git`, mac-версию `settings.local.json` (затёрла бы рабочую).

**Сохранено то, чего в архиве не было:** скил `razvedka-nishi`, проекты `seo-sites` и `unisec-nsk` — они появились уже на Windows.

## 3. Что было сломано и как починено

### venv и тулсы
Приехало macOS-окружение (`bin/`, `lib/python3.9`), а CLAUDE.md и `.tools/README.md` велели звать тулсы через `.tools/venv/bin/python`. На Windows путь другой.

**Решение:** venv пересобран на Python 3.14 — pandas, numpy, openpyxl, markdown, playwright + chromium, google-api-client. Пути переписаны на `venv/Scripts/python.exe` в CLAUDE.md, AGENTS.md, `.tools/README.md` и черновике ютуб-обложек.

**Проверено вживую:** `snapshot.py` снял desktop+mobile; `film-avg-check.py` посчитал LTV по реальной базе (124 404 ₽ за первый год).

### Юникод в консоли Windows
Скрипты падали на финальном `print("✓")` — консоль в cp1251. Тулса при этом отрабатывала (PNG создавались), но возвращала ошибку, что маскировало реальные сбои.

**Решение:** `PYTHONUTF8=1` и `PYTHONIOENCODING=utf-8` в `.claude/settings.json`.

### MCP google-sheets
`.mcp.json` и `.codex/config.toml` были целиком в mac-путях: `uvx` из `~/.local/bin`, ключ из `~/.config/google-credentials/`. `uvx` на машине нет.

**Решение:** оба конфига зовут venv-питон напрямую, без uv; ключ привязан к `system/secrets/gsheets-key.json` внутри волта. Засада: `mcp-google-sheets 0.6.1` тянет `mcp 2.0`, где `fastmcp` переехал — закреплён `mcp<2.0`. Self-test лаунчера проходит. **Требуется рестарт Claude Code.**

### Mac-пути в скриптах
В `analyze-detailing-base.py` были захардкожены абсолютные `ROOT` и путь к ключу — скрипт не запустился бы вообще.

**Решение:** `ROOT` считается от расположения файла, ключ — через `os.path.join`. Docstring-примеры запуска в четырёх `analyze-*.py` переведены с `uv run --with ...` на venv-питон.

Осталось 12 файлов с mac-путями: 5 в telegram-vault и yougile (эти тулсы всё равно не мигрированы), 7 — упоминания в тексте старых заметок, на работу не влияют.

### Дубли от повторной загрузки
13 файлов вида `«... (2).md»`. Проверил каждую пару: у всех `(2)` старые относительные пути (`../../hypotheses.md` вместо актуального `../../../`) — то есть они с эпохи до перестройки папок.

**Решение:** 11 удалено, `landing-tz (2).md` переименован (оригинала не было). По `life/finance/_index.md` вышло наоборот — оригинал был пустым скелетом, `(2)` содержательнее, но оба устарели; файл пересобран на актуальный `finance-plan-h2-2026-v2.md` (29.06).

### Git
`.git` приехал пустым — истории нет. Мешал сломанный вложенный репозиторий `ppf-kp-prototype`: его коммит-объект отсутствует, `git fsck` даёт invalid sha1, история невосстановима.

**Решение:** битый `.git` отодвинут в `tmp/broken-git-backup/` (не удалён — вдруг объекты найдутся на старой машине), исходники прототипа вошли в общий коммит. В `.gitignore` добавлены venv, node_modules, `__pycache__`, `tmp/`. Первый коммит — `b9dbcd7`, 950 файлов.

## 4. Что не приехало

- **`memory/`** — карточки памяти системы (`MEMORY.md`, `project_target_model`, `reference_claude_seo`). Жили в `~/.claude` на маке, а не в волте, поэтому в слепок не попали. CLAUDE.md и AGENTS.md на них ссылаются.
- **6 тулсов**, заявленных в `.tools/README.md`: `build-screening-xlsx.py`, `result-card.py`, `dashboard-telegram.py` и три `transcribe-*.ps1`. Их каталоги приехали пустыми.
- **claude-seo** — 25 SEO-скилов, плагин не установлен.
- **telegram-vault** — нужен `pywhispercpp` и whisper-модель, путь ведёт в mac-приложение Handy.
- **yougile-sync** — `com.hypercrm.yougile-sync.plist` это mac launchd; под Windows нужен Task Scheduler.

## 5. Ссылки

Полная проверка дала **142 битые ссылки**: 97 в живых файлах, 45 в замороженных (`daily/`, `_archive/`, `reviews/` — CLAUDE.md запрещает их трогать).

Починены приоритетные — навигационный каркас (`_index.md`, `README.md`): переведены на существующие csv/html там, где данные остались, и честно помечено утерянное.

Оставшиеся 97 делятся так: **26 механических** (файл переехал или сменил расширение — правится скриптом, но есть ложные совпадения по общим именам вроде `README.md`) и **71 отсутствует физически** — каждая требует решения. Разбор → [system-audit-2026-08-11.md](system-audit-2026-08-11.md).
