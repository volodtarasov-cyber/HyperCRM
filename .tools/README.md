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
| Vault | `universal/vault/quality-check.py` | Единая проверка живого слоя: ссылки, checkpoints и результаты гипотез, доказательства модулей, owner/status, полнота словаря и коллизии aliases, плавающие термины, противоречия канону, приватность экспорта. **Срок годности (WARN):** область — файлы, на которые ссылаются активные индексы (один хоп: то, что реально открывают). Порог по типу — решения 90 дн., клиентские материалы 45, планы 30; поле `годен-до:` во frontmatter сильнее типа; метод Marketing OS и неклассифицированные артефакты по календарю не проверяются, у них нет срока годности по дате. Файл нужного типа вовсе без отметки `**Проверено:**` — только в `--strict`, иначе обычный прогон захлебнётся долгом разметки |
| Детейлинг | `projects/detailing-samara/analytics/levsha-dashboard-update.py` | Обработчик локальной аналитики Левши: выгрузки Б24 (сделки и лиды), 1С и рекламных кабинетов из `inbox/` → SQLite → `dashboard/data.js`. Запуск: `--project projects/detailing-samara/analytics/levsha-dashboard`; `--no-inbox` только пересобирает дашборд из базы. Проще — `Обновить аналитику.bat` в папке дашборда. Правила расчёта и формат выгрузок → README дашборда |
| Vault | `universal/vault/board.py` | Визуальная доска направления → `.tools/board.html`: деньги, блокеры, чекпоинты со сроками, реестр проектов и клиентов, регулярные ритмы, задачи. Задача = незакрытый чекбокс в индексе проекта или в материалах `practice`. Сводные блоки читаются из секций `practice/_index.md` («Деньги сейчас», «Что стоит и чего ждёт», «Реестр проектов») и `practice/plan.md` («Чекпоинты») — доска рендерит, но не хранит; `--open` открывает в браузере |
| Vault | `universal/vault/board_server.py` | **Рабочая доска**: локальный сервер на 127.0.0.1, собирает страницу заново на каждый запрос; клик по задаче переключает чекбокс прямо в markdown. `--port`, `--no-open` |
| Vault | `universal/vault/weekly-digest.py` | Понедельничный дайджест в Telegram: открытые задачи, ошибки и протухшее из `quality-check`, блок «Что снаружи», требующее внимания, ближние чекпоинты. **Снимок прогона не трогает** — читает состояние напрямую из `board.py`, поэтому живой `review.py` по-прежнему показывает полную разницу с прошлого раза. `--print` — текст без отправки, `--log` — режим Планировщика с отметкой времени и исходом |
| Vault | `universal/vault/telegram-setup.py` | Установка дайджеста: скрытый ввод токена → определение `chat_id` через getUpdates → задача в Планировщике Windows (пн 09:00, с догоном пропуска). Токен в волте не хранится — `%LOCALAPPDATA%\HyperCRM\telegram.json`. `--task-only` переставляет задачу, `--send-test` шлёт пробное. Задача запускает обёртку `run-digest.cmd` рядом с конфигом: она задаёт рабочую папку (у задачи Планировщика её нет) и пишет весь вывод в `digest.log` — иначе при сбое остаётся только код возврата без текста |
| Vault | `universal/vault/review.py` | **Вход для разбора**: что закрыто и с каким следом, что появилось, что висит, что протухло, чекпоинты на горизонте. Сравнивает со снимком прошлого прогона (`.tools/review-state.json`), не с git. **Блок «Что снаружи»** — обратный ход: печатает факты, чьё состояние живёт вне волта, с датой последней сверки. Метка в любом файле `projects/` или `life/`: `- [вне] что сверяем ⟳ 2026-08-25`, где `⟳ —` значит «ни разу». Метка живёт рядом со своим фактом, а не в отдельном реестре — реестр протух бы первым |
| Vault | `universal/vault/repair-links.py` | Консервативный ремонт ссылок: dry-run по умолчанию, `--apply` перевязывает однозначные перемещения с приоритетом живого слоя и снимает разметку с утраченных целей |
| Vault | `universal/vault/check-links.py` | Узкая legacy-проверка Markdown-ссылок; для полной гигиены использовать `quality-check.py` |

## Проектные

| Проект | Категория | Скрипты |
|---|---|---|
| `detailing-samara` | Analytics | `film-avg-check.py`, `film-check-distribution.py`, `film-order-distribution-all-history.py`, `film-orders-distribution.py`, `film-orders-repeat-analysis.py`, `new-vs-returning.py` |
| `detailing-samara` | Exports | `build-a-handoff.py`, `build-screening-pilot-levsha.py` |
| `detailing-samara` | Web | `hero-shot.py`, `section-shot.py` |
| `bingo-samara` | Analytics | `zayavki-analysis.py` — разбор выгрузки заявок формы ВК (cp1251, `;`): база, удержание по когортам с нормализацией окна, ритм возврата, спящие, ядро, LTV, размер компании, атрибуция, динамика по месяцам и играм |
| `ai-infobiz` | Content | `carousel.py` |
| `ananas-marketing` | Content | `result-card.py` |
| `ananas-marketing` | Documents | `md-to-pdf.py`, `md-to-pdf-simple.py` |
| `ananas-marketing` | Web | `ananasm-detail.py`, `extract-logo.py` |

Проектные инструменты лежат в `.tools/projects/<project>/<category>/`. Пустые каталоги Marketing OS не считаются доступными инструментами и не документируются как команды.

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
.tools/venv/Scripts/python.exe .tools/universal/vault/quality-check.py --strict
.tools/venv/Scripts/python.exe .tools/universal/vault/board_server.py
.tools/venv/Scripts/python.exe .tools/universal/vault/board.py --open
.tools/venv/Scripts/python.exe .tools/universal/vault/repair-links.py
.tools/venv/Scripts/python.exe .tools/universal/vault/repair-links.py --apply
.tools/venv/Scripts/python.exe .tools/universal/reporting/dashboard-telegram.py --send
.tools/venv/Scripts/python.exe .tools/universal/telegram-vault/bot.py --self-test
.tools/venv/Scripts/python.exe .tools/universal/telegram-vault/setup.py
.tools/venv/Scripts/python.exe .tools/projects/ai-infobiz/content/carousel.py <input.md>
py .tools/projects/ananas-marketing/content/result-card.py <cards.json>   # Windows: рендер через headless Chrome, venv не нужен
.tools/venv/Scripts/python.exe .tools/projects/detailing-samara/analytics/film-avg-check.py
```
