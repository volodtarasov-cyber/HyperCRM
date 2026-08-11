# Инструменты

Скрипты разделены по области применения.

## Wordstat API

`.tools/wordstat.ps1` — клиент официального API Яндекс Вордстата. OAuth-токен не хранится в vault: команда `setup` шифрует его через Windows DPAPI в профиле текущего пользователя.

```powershell
# Сохранить или заменить токен — ввод скрыт
powershell -NoProfile -ExecutionPolicy Bypass -File .\.tools\wordstat.ps1 -Action setup

# Проверить доступ после одобрения Яндекса
powershell -NoProfile -ExecutionPolicy Bypass -File .\.tools\wordstat.ps1 -Action test

# Топ запросов за последние 30 дней
powershell -NoProfile -ExecutionPolicy Bypass -File .\.tools\wordstat.ps1 -Action top -Phrase "франшиза музыкального бинго"

# Динамика по месяцам
powershell -NoProfile -ExecutionPolicy Bypass -File .\.tools\wordstat.ps1 -Action dynamics -Phrase "франшиза квиза" -Period monthly -FromDate "2024-01-01"

# Распределение спроса по городам
powershell -NoProfile -ExecutionPolicy Bypass -File .\.tools\wordstat.ps1 -Action regions -Phrase "музыкальное бинго" -RegionType cities
```

Результат можно сохранить через `-OutFile`, но только внутри workspace.

## Универсальные

Универсальный инструмент не содержит путей, URL, брендинга или схемы данных
конкретного проекта.

| Категория | Скрипт | Назначение |
|---|---|---|
| Web | `universal/web/snapshot.py` | Скриншоты произвольной страницы на desktop и mobile |
| PDF | `universal/pdf/pdf-preview.py` | PNG-превью локального PDF |
| Reporting | `universal/reporting/dashboard-telegram.py` | Утренняя сводка из живых `projects/**/_dashboard.md`; опциональная отправка через Telegram-бота |
| Automation | `universal/telegram-vault/bot.py` + `setup.py` | Приватный Telegram-шлюз к локальному Codex и vault; `/report` + будничная автосводка |

## Проектные

| Проект | Категория | Скрипты |
|---|---|---|
| `detailing-samara` | Analytics | `film-avg-check.py`, `film-check-distribution.py`, `film-order-distribution-all-history.py`, `film-orders-distribution.py`, `film-orders-repeat-analysis.py`, `new-vs-returning.py` |
| `detailing-samara` | Exports | `build-a-handoff.py`, `build-screening-pilot-levsha.py` |
| `detailing-samara` | Web | `hero-shot.py`, `section-shot.py` |
| `agency-os` | Spreadsheets | `build-screening-xlsx.py` |
| `agency-os` | Transcription | `transcribe-psychomarketing.ps1`, `transcribe-direct-response-copywriting.ps1`, `transcribe-neuroshamanic-communications.ps1` |
| `ai-infobiz` | Content | `carousel.py` |
| `ananas-marketing` | Content | `result-card.py` |
| `ananas-marketing` | Documents | `md-to-pdf.py`, `md-to-pdf-simple.py` |
| `ananas-marketing` | Web | `ananasm-detail.py`, `extract-logo.py` |

Проектные инструменты лежат в `projects/<project>/<category>/`.

## Служебные каталоги

- `venv/` — Python-окружение инструментов.
- `snapshots/` — общие результаты скриншотов и аналитические CSV.
- `carousel-out/` — результаты генератора каруселей.
- `cards-out/` — результаты генератора карточек с результатами (Ананас Маркетинг).
- `skill-build/` — рабочие материалы сборки навыков, не исполняемые инструменты.

## Примеры запуска

```bash
.tools/venv/Scripts/python.exe .tools/universal/web/snapshot.py <url> <prefix>
.tools/venv/Scripts/python.exe .tools/universal/pdf/pdf-preview.py <file.pdf>
.tools/venv/Scripts/python.exe .tools/universal/reporting/dashboard-telegram.py
.tools/venv/Scripts/python.exe .tools/universal/reporting/dashboard-telegram.py --send
.tools/venv/Scripts/python.exe .tools/universal/telegram-vault/bot.py --self-test
.tools/venv/Scripts/python.exe .tools/universal/telegram-vault/setup.py
.tools/venv/Scripts/python.exe .tools/projects/ai-infobiz/content/carousel.py <input.md>
py .tools/projects/ananas-marketing/content/result-card.py <cards.json>   # Windows: рендер через headless Chrome, venv не нужен
.tools/venv/Scripts/python.exe .tools/projects/detailing-samara/analytics/film-avg-check.py
powershell -ExecutionPolicy Bypass -File .tools/projects/agency-os/transcription/transcribe-psychomarketing.ps1
powershell -ExecutionPolicy Bypass -File .tools/projects/agency-os/transcription/transcribe-direct-response-copywriting.ps1
powershell -ExecutionPolicy Bypass -File .tools/projects/agency-os/transcription/transcribe-neuroshamanic-communications.ps1
```
