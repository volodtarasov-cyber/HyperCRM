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
| Media | `universal/media/transcribe-calls.py` | Локальная транскрибация звонков (whisper.cpp). **Записи не уходят в облако** — это правило коробки «анализ разговоров», а не деталь. Только macOS: декодирование через `afconvert`, модель ggml из Handy |
| Vault | `universal/vault/board.py` | **Legacy, не источник задач.** Был собран под очередь Markdown-чекбоксов и старую структуру `projects/practice`; после решения 2026-09-01 задачи живут только в YouGile. Использовать лишь для диагностики старого слоя до отдельной пересборки визуальной панели |
| Vault | `universal/vault/board_server.py` | **Legacy.** Не переключать через него чекбоксы: это снова превращает волт в задачник |
| Vault | `universal/vault/weekly-digest.py` | **Legacy.** Формат основан на Markdown-задачах и старой доске; не использовать как отчёт агентства до пересборки на P&L, мощности и внешние данные |
| Vault | `universal/vault/telegram-setup.py` | Установка дайджеста: скрытый ввод токена → определение `chat_id` через getUpdates → задача в Планировщике Windows (пн 09:00, с догоном пропуска). Токен в волте не хранится — `%LOCALAPPDATA%\HyperCRM\telegram.json`. `--task-only` переставляет задачу, `--send-test` шлёт пробное. Задача запускает обёртку `run-digest.cmd` рядом с конфигом: она задаёт рабочую папку (у задачи Планировщика её нет) и пишет весь вывод в `digest.log` — иначе при сбое остаётся только код возврата без текста |
| Vault | `universal/vault/review.py` | **Legacy для task-diff.** Блок `[вне]` остаётся полезным, но сравнение Markdown-задач больше не является входом для агентского разбора; задачи и их статусы читаются только в YouGile |
| Vault | `universal/vault/repair-links.py` | Консервативный ремонт ссылок: dry-run по умолчанию, `--apply` перевязывает однозначные перемещения с приоритетом живого слоя и снимает разметку с утраченных целей |
| Vault | `universal/vault/check-links.py` | Узкая legacy-проверка Markdown-ссылок; для полной гигиены использовать `quality-check.py` |

## Проектные

| Проект | Категория | Скрипты |
|---|---|---|
| `ananas-marketing` | Analytics | `portfolio-margin.py` — маржа клиентского портфеля по методу ёмкости контура: себестоимость единицы = оклад / ёмкость, простой отдельной строкой. Срез месяца задан в самом скрипте, метод → `agency/finmodel.md` |
| `bingo-samara` | Analytics | `zayavki-analysis.py` — разбор выгрузки заявок формы ВК (cp1251, `;`): база, удержание по когортам с нормализацией окна, ритм возврата, спящие, ядро, LTV, размер компании, атрибуция, динамика по месяцам и играм |
| `ai-infobiz` | Content | `carousel.py` |
| `ananas-marketing` | Content | `result-card.py` |
| `ananas-marketing` | Documents | `md-to-pdf.py`, `md-to-pdf-simple.py`, `html-to-pdf.py` — пересборка полосового A4-документа из HTML в PDF с проверкой вёрстки: число страниц в PDF против числа блоков `.page`, перелив содержимого за нижний край, пересечение фирменного декора с текстом. Ненулевой код возврата, если вёрстка поехала |
| `ananas-marketing` | Web | `ananasm-detail.py`, `extract-logo.py` |
| `unisec-novosibirsk` | Yandex Maps | `build-images-from-sources.py` — пересобирает фото услуг 1080×1080 с метаданными из `assets/yandex-maps-services/source/` через `build-service-image.py`; `build-price-list.py` — прайс карточки из рабочего CSV услуг; `build-launch-clusters.py` — кластеры запуска из `semantics/clusters.csv` и проверки частотности; `build-tracking.py` — список ключей и шаблон журнала позиций из кластеров запуска. Данные и результат — в `clients/unisec-novosibirsk/` |

Проектные инструменты лежат в `.tools/projects/<project>/<category>/`. Пустые каталоги Marketing OS не считаются доступными инструментами и не документируются как команды.

## Служебные каталоги

- `venv/` — Python-окружение инструментов.
- `snapshots/` — общие результаты скриншотов и аналитические CSV. Не версионируются; снимок-доказательство добавляется явно через `git add -f`.
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
.tools/venv/Scripts/python.exe .tools/projects/ananas-marketing/documents/html-to-pdf.py <doc.html>
.tools/venv/Scripts/python.exe .tools/projects/ananas-marketing/documents/html-to-pdf.py <doc.html> --check
.tools/venv/Scripts/python.exe .tools/universal/reporting/dashboard-telegram.py --send
.tools/venv/Scripts/python.exe .tools/universal/telegram-vault/bot.py --self-test
.tools/venv/Scripts/python.exe .tools/universal/telegram-vault/setup.py
.tools/venv/Scripts/python.exe .tools/projects/ai-infobiz/content/carousel.py <input.md>
py .tools/projects/ananas-marketing/content/result-card.py <cards.json>   # Windows: рендер через headless Chrome, venv не нужен
.tools/venv/Scripts/python.exe .tools/projects/bingo-samara/analytics/zayavki-analysis.py <export.csv>
```
