# Инструменты

Скрипты разделены по области применения.

## Обработка курса «Флагман VII»

Локальный возобновляемый разбор: [инструкция и команды](projects/flagman-vii/README.md), [план и требования к артефактам](../knowledge/frameworks/flagman-vii-2025/_index.md). `course.py` инвентаризирует видео с SHA-256 и длительностями, извлекает раздатку и транскрибирует уникальные записи через установленную large-v3 на GPU. Сырьё и результаты обработки — в игнорируемой `.tools/local/flagman-vii/`; исходный курс не меняется. Смысловой разбор и проверка актуальности — отдельные этапы.

## Контент карточек компаний

- `universal/seo/wordstat-snapshot.py --factory <папка-завода> --region <ID> --region-name <название> --date YYYY-MM-DD --phrase <запрос> --out <JSON>` — quoted-замер через XMLRiver модуль завода по HTTPS; не меняет конфиг и очередь сайта, ключи не выводит. Создаёт JSON/CSV рядом с инструментом.
- `universal/content/validate-geo-pack.py <pack-manifest.json> --as-of YYYY-MM-DD --out <JSON> [--require-publish-ready]` — проверка комплекта и отдельный допуск публикации по точкам; ничего не отправляет. Ручная проверка правдивости, кабинетов, контактов и видимости остаётся обязательной. Правила и гейты → [плейбук](../marketing-os/playbooks/geo-news-production.md).

При подготовке кейса `/agency-carousel` делает версии для Instagram, Threads и Telegram, если пользователь не ограничил площадки. Самостоятельный Telegram-пост хранится в исходном Markdown в разделе `Telegram — пост для канала`; `carousel-export.py` сохраняет его в `telegram-post.txt` и общий ZIP. Это подготовка текста; панель ниже публикует в Instagram и Threads.

## Публикация Instagram и Threads с ПК

Рабочий контент-завод: [инструкция очереди, дашборда, расписания и замеров](projects/ananas-marketing/content/FACTORY.md). Запуск — `open-content-factory.ps1` в том же каталоге. Главная страница на `127.0.0.1:8766` теперь открывает завод; прежняя панель публикатора — `/publisher`. База, версии, календарь, попытки, ручные замеры и обращения сохраняются локально. Instagram/Threads используют существующий браузер; Telegram @lazyhim пока имеет ручной выпуск. Фоновая ИИ-генерация, плановый сбор статистики и автозапуск Windows не включены. [Проект архитектуры](projects/ananas-marketing/content/factory-design.md) отделяет будущие расширения от реализации.

`projects/ananas-marketing/content/social-publisher.py` управляет отдельным видимым Chromium через Playwright. Аккаунты авторизуются вручную в этом браузере; сессия сохраняется на ПК. API Meta и подписка на сервис публикации не нужны.

Запуск из корня волта:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .tools/projects/ananas-marketing/content/open-social-publisher.ps1
```

Панель — `http://127.0.0.1:8766/`. По умолчанию открыт комплект автосвета. Другой комплект:

```powershell
& .tools/venv/Scripts/python.exe .tools/projects/ananas-marketing/content/social-publisher.py --pack .tools/carousel-out/<case>
```

В комплекте нужны последовательно пронумерованные `slide-01.png`… и подписи `instagram-caption.txt`, `threads-post.txt`. Текущая версия принимает 2–10 PNG одинакового размера; это ограничение инструмента. `--check` проверяет комплект без запуска браузера.

В панели: ник аккаунта → «Открыть / войти» → ручной вход → «Подготовить» → проверка черновика в браузере → «Опубликовать». Проверка владельца использует кнопку редактирования выбранного профиля; перед отправкой проверяется повторно. Для Instagram выбирается 4:5, если исходник 4:5, иначе исходный формат. При неоднозначном элементе интерфейса инструмент останавливается, а не угадывает кнопку. После ручного изменения черновика нужна повторная подготовка.

Локальное состояние — `.tools/local/social-publisher/` (игнорируется git): профиль Chromium, ники, квитанции отправки и скриншоты черновиков. Пароли в панель и чат не вводятся. После неопределённого результата отправки комплект блокируется от повтора: сначала вручную проверяем профиль; квитанцию не сбрасываем автоматически. Закрытие инструмента — отдельная кнопка в панели.

Веб-интерфейсы соцсетей меняются: локальные проверки не подтверждают работу живого редактора. 20.10.2026 на живых Instagram и Threads проверена подготовка семи карточек с подписями в аккаунтах владельца, для Instagram — формат 4:5. Финальный клик отправки этим прогоном не проверялся. Адаптер учитывает меню Instagram без ролей, динамический выбор файлов, новое название обрезки, задержку появления окна Threads и сброс `input.files` после приёма изображений. Порядок проверяется по реальному событию выбора файлов до сброса поля. При `ERR_CONNECTION_RESET` / таймауте сначала проверяем доступ к соцсетям и VPN на ПК. Локальная панель при этом продолжает работать.

Браузер для ручного входа должен быть видим на обычном рабочем столе Windows. Запуск из изолированной среды помощника может оставить окно невидимым для пользователя; в таком случае закрыть инструмент и запустить тот же PowerShell-файл вне изолированной среды. Сохранённый профиль не удалять.

Если сайты открываются в обычном Chrome, а отдельный Chromium выдаёт сетевую ошибку, можно явно направить его через локальный прокси VPN. Сначала закрыть инструмент кнопкой панели, затем запустить с адресом реально работающего порта, например:

```powershell
& .tools/venv/Scripts/python.exe -X utf8 .tools/projects/ananas-marketing/content/social-publisher.py --proxy socks5://127.0.0.1:10808
```

Адрес сохраняется в игнорируемом `network.json` после успешного запуска браузера и используется обычным PowerShell-запуском. Панель показывает выбранный маршрут; VPN должен оставаться включённым. При смене порта повторить запуск с новым адресом; `--proxy direct` возвращает системный маршрут. Поддерживаются локальные HTTP и SOCKS5 без учётных данных. На этом ПК проверен SOCKS5 `127.0.0.1:10808`; HTTP-порт того же VPN давал сброс соединения в Chromium, хотя HTTP-клиент получал ответ. Успешный запрос скрипта не заменяет проверку в браузере.

Локальное действие API `inspect` сохраняет состав видимых элементов в `<площадка>-inspection.json` без значений полей и без навигации. Снимок страницы не делается при наличии поля пароля; диагностика и снимки остаются в игнорируемом каталоге состояния. Это используется для настройки адаптера после изменения интерфейса.

Проверки с локальными макетами, без запросов к соцсетям:

```powershell
& .tools/venv/Scripts/python.exe .tools/projects/ananas-marketing/content/test-social-publisher.py
```

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
| Reporting | `universal/seo-dashboard/build.py [--no-live] [--only <id>]` (или `Обновить дашборд.bat` рядом) | Дашборд всех SEO-заводов. Сайты — `sites.yml` (путь к заводу, карточка в волте, проверять ли живой сайт); домен, репозиторий и папку статей берёт из `site.config.yml` завода. Общая страница — «Внимание» (сломано / ждёт действия по всем сайтам) и сводка; страница сайта — журнал статей и тем со статусами, проверка опубликованного «как робот», техаудит, подключения (по именам ключей `.env`, значения не читаются), давно не сверенные `[вне]` из карточки. Задачи остаются в YouGile — дашборд их не хранит. Результат — `out/`, вне git |
| Tasks | `universal/yougile/yougile.py` (подключение — `Подключить YouGile.bat`) | Клиент YouGile API v2: `tree` (проект → доска → колонка), `users`, `tasks`, `create`, `push` списком с проверкой всех адресов до записи. Ключ — `.tools/local/yougile/key.env`, вне git; пароль вводится в окне и не сохраняется. Создаёт только после явного «да» Володи → CLAUDE.md «Tasks in YouGile». Подробности — README в папке |
| Reporting | `universal/reporting/dashboard-telegram.py` | Утренняя сводка из живых `projects/**/_dashboard.md`; опциональная отправка через Telegram-бота |
| Automation | `universal/telegram-vault/bot.py` + `setup.py` | Приватный Telegram-шлюз к локальному Codex и vault; `/report` + будничная автосводка |
| Vault | `universal/vault/quality-check.py` | Единая проверка живого слоя: ссылки, checkpoints и результаты гипотез, доказательства модулей, owner/status, полнота словаря и коллизии aliases, плавающие термины, противоречия канону, приватность экспорта. **Срок годности (WARN):** область — файлы, на которые ссылаются активные индексы (один хоп: то, что реально открывают). Порог по типу — решения 90 дн., клиентские материалы 45, планы 30; поле `годен-до:` во frontmatter сильнее типа; метод Marketing OS и неклассифицированные артефакты по календарю не проверяются, у них нет срока годности по дате. Файл нужного типа вовсе без отметки `**Проверено:**` — только в `--strict`, иначе обычный прогон захлебнётся долгом разметки |
| Media | `universal/media/transcribe-calls.py` | Локальная транскрибация звонков (whisper.cpp). **Записи не уходят в облако** — это правило коробки «анализ разговоров», а не деталь. Только macOS: декодирование через `afconvert`, модель ggml из Handy |
| Media | `universal/media/transcribe-video.py` | Локальная расшифровка видео и аудио на Windows: faster-whisper large-v3 на видеокарте (GTX 1070 Ti — `int8`, около ×6 к реальному времени), звук достаёт системный `ffmpeg`. Папку обходит рекурсивно, кладёт `.md` с таймкодами в `_transcripts\`, готовые пропускает — прогон можно прерывать. Своё окружение `.tools/venv-whisper` на Python 3.13 (у ctranslate2 нет колёс под 3.14); модели — в `D:\.cache\huggingface` |
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
| `ananas-marketing` | Analytics | `portfolio-snapshot.py <source.json> [--output result.json]` — read-only срез именованных чеков, среднего чека и заполненных оплат из выгрузки Sheets; исключает безымянные подытоги, не выдаёт чеки за выручку. Сырьё и результат — в игнорируемой `.tools/snapshots/`. `portfolio-margin.py` — маржа клиентского портфеля по методу ёмкости контура: себестоимость единицы = оклад / ёмкость, простой отдельной строкой. Срез месяца задан в самом скрипте, метод → `agency/finmodel.md`. `niche-demand-probe.py <seeds.txt> <out_dir>` — спрос владельцев бизнеса под нишевые страницы: частотность широкая и фразовая плюс топ-10 Яндекса через XMLRiver копии SEO-завода (0,025 ₽ за обращение, 3 на запрос); домены, повторяющиеся в топах, — конкуренты по выдаче. Сырьё — в `out_dir`, не версионируется |
| `arcars` | Telegram | `telegram/parse_channel.py [export_dir]` — разбор HTML-выгрузки канала t.me/ARCarsSamara (Telegram Desktop → «Экспорт истории», HTML, фото без видео) в `out/`: `posts.jsonl` (все посты с рубрикой по хештегам и ссылкой t.me), `offers.csv` (`#готовое_предложение`: модель, год, страна, мотор, пробег, цена и **город цены** — Самара или Владивосток; цена — расчёт на дату поста, не сделка), `gallery.html` (фото выдач, отзывов, процесса и людей с текстом поста; галочки → «Скопировать список»). Выгрузка кладётся в `telegram/export/<дата>/`; она и `out/` вне git. Выводы — в `clients/arcars/facts-from-client.md` с номером поста || `bingo-samara` | Analytics | `zayavki-analysis.py` — разбор выгрузки заявок формы ВК (cp1251, `;`): база, удержание по когортам с нормализацией окна, ритм возврата, спящие, ядро, LTV, размер компании, атрибуция, динамика по месяцам и играм |
| `ai-infobiz` | Content | `carousel.py` |
| `ananas-marketing` | Content | `result-card.py`; `carousel-export.py <source.html> <out_dir> [--copy publication.md]` — PNG из `.deck .slide`, автономный предпросмотр, макеты сетки профиля, проверка обрезки ключевых строк и размера текста на телефоне, ZIP. Ключи обложки отмечаются `data-grid-key`, основной текст — `data-body-copy`; правило → `team/brand-style.md`, сценарий → `/agency-carousel`. `social-publisher.py` — публикация готового комплекта через Playwright, [запуск ниже](#публикация-instagram-и-threads-с-пк) |
| `ananas-marketing` | Documents | `md-to-pdf.py`, `md-to-pdf-simple.py`, `html-to-pdf.py` — пересборка полосового A4-документа из HTML в PDF с проверкой вёрстки: число страниц в PDF против числа блоков `.page`, перелив содержимого за нижний край, пересечение фирменного декора с текстом. Ненулевой код возврата, если вёрстка поехала |
| `ananas-marketing` | Web | `ananasm-detail.py`, `extract-logo.py` |
| `samara-detailing` | SEO | `seo/semantics.py serp\|ws --factory <завод>` и `report` — топ-10 Яндекса (регион 51) и фразовая частотность Wordstat по `projects/seo-sites/samara-ppf-detailing/02-semantika/seeds.csv` через XMLRiver; повторный запуск добирает только пустые ответы; `report` делит домены на площадки, Левшу и исполнителей. Запускать интерпретатором завода (`<завод>/.venv`). Сырьё — в игнорируемой `seo/data/` |
| `unisec-novosibirsk` | Yandex Maps | `build-images-from-sources.py` — пересобирает фото услуг 1080×1080 с метаданными из `assets/yandex-maps-services/source/` через `build-service-image.py`; `build-price-list.py` — прайс карточки из рабочего CSV услуг; `build-launch-clusters.py` — кластеры запуска из `semantics/clusters.csv` и проверки частотности; `build-tracking.py` — список ключей и шаблон журнала позиций из кластеров запуска. Данные и результат — в `clients/unisec-novosibirsk/` |

Проектные инструменты лежат в `.tools/projects/<project>/<category>/`. Пустые каталоги Marketing OS не считаются доступными инструментами и не документируются как команды.

## Вне волта

Исполнители и сайты со своим git, ключами и генерируемыми данными. В волт не переносятся по контракту данных; этот раздел — единственный паспорт: где лежит, что это, под что настроено. Остальные файлы ссылаются сюда.

| Папка | Что | С чем связано |
|---|---|---|
| `D:\SecondBrain\seo-factory` | **SEO-завод** — внешний пакет, версия в его `VERSION`. Пишет статьи в блог сайта по подписке Claude/Codex, следит за техникой и позициями, шлёт отчёты. Git только локальный, без удалённого репозитория: отправку пакета на GitHub заблокировала защита Claude Code — платный пакет с лицензией. Бэкап — копия папки в облаке руками Володи, без `.venv`; ключи XMLRiver и Arsenkin — в его `.env`, волт о них знает только фактом подключения | **Одна установка — один сайт:** `site.config.yml` ведёт один сайт, путь к нему — `stack.repo_path`. Сейчас это Arcars |
| `D:\SecondBrain\seo-factory-volodtarasov` | **Вторая копия SEO-завода** — под volodtarasov.ru, та же версия, развёрнута 2026-10-13 из чистого архива курса (`D:\Курсы\ИИ SEO курс\ИИ SEO курс\seo-factory.zip`), без данных Arcars. Настроен на `agency-site` (статьи в `src/content/blog`, git не трогает), ключи XMLRiver и Arsenkin взяты у Arcars, порог платного шага — 150 ₽. Конкуренты вписаны руками по замеру выдачи: автоподбор пакета для B2B-ниши подобрал сайт для автовладельцев. Обновления пакета раскатываются в каждую копию отдельно; Wordstat и XMLRiver делят лимиты с Arcars — сборы разносить по времени | сайт — `agency-site` ниже; [условие запуска сайта](../agency/market.md#органический-канал) |
| `D:\SecondBrain\arcars-site` | Сайт клиента Arcars на Astro, свой git с копией в приватном `github.com/volodtarasov-cyber/arcars-site` — после выката коммит и push. Блог наполняет завод. Сайт полностью статичный, заявки принимает `public/api/lead.php`. Выкат на Timeweb — `deploy.py`: без флагов только сравнивает, `--apply` загружает новые файлы, `--overwrite` заменяет изменённые, на сервере ничего не удаляет | [карточка клиента](../clients/arcars/_index.md) |
| `D:\SecondBrain\agency-site` | Сайт агентства на Astro, свой git без удалённого репозитория, не выкачен. **Переезжает на ananasm.ru** с Тильды (решение 2026-10-13): план и карта 57 старых адресов — `docs/pereezd-ananasm.md`, `docs/redirects-ananasm.csv`; пока собирается под volodtarasov.ru, адрес меняется на этапе 2 плана. Оформление по [брендбуку](../team/brand-style.md) — Manrope, баклажанная шапка и обложки, светлая поверхность, фирменные кнопки и иконки, тёмная тема по выбору. Левое меню: поиск, разделы со счётчиками, фильтр по нише, каналу и датам, экосистема, действия, связь; состояние фильтра живёт в адресе. Страница материала: схема-обложка из данных, «Слушать статью» (файл озвучки или голос браузера), блок «Подготовил / Проверил». Бренд, меню и контакты — в `src/site.config.ts`. 12 нишевых страниц `/<ниша>/` в двух группах — авто (автосервис, шиномонтаж, автомойка, кузовной, детейлинг, автосвет) и чистота (клининг, химчистка одежды, мебели, обуви, прачечные, ковры); целевой запрос — по замеру в [рынке](../agency/market.md#органический-канал), кейсы — `/keysy/<ниша>/<кейс>/`; до готового текста ниша закрыта от индексации. 29 кейсов с ananasm.ru с флагом `needsRewrite`. Выкатываем, когда решение об органическом канале пересмотрено | [решение](../agency/market.md#органический-канал), [карточка сайта](../projects/ai-infobiz/product/site-lazyhim.md) |

- [вне] копия папки завода в облаке Володи — сделана и свежая? Ценное в ней — `engine\*\data`, `engine\*\queue`, `site.config.yml` ⟳ —

Завод на Windows:

```bat
D:\SecondBrain\seo-factory\Старт.bat                                    :: окно настройки, первый запуск собирает .venv
D:\SecondBrain\seo-factory\venv-python.bat engine\seo-agent\orchestrator.py doctor   :: что заполнено и что не отвечает
```

**Локальная правка движка у Arcars (2026-10-21):** `engine/content-factory/images.py` читает два своих ключа `images` — `cover_template` (обложка в стиле сайта, `site-assets/cover-arcars.html.tpl`, шрифты в `site-assets/fonts/`) и `kicker_labels` (русские названия рубрик). Обновление пакета перезапишет `images.py`, и обложки молча вернутся к шаблону движка — после обновления перенести обе правки и перерисовать: `cover_backfill.py --replace --no-grid`.

**Вторая локальная правка (2026-10-27):** `engine/seo-agent/llm_router.py`, вызов `claude -p` получает `--tools WebFetch WebSearch --allowedTools WebFetch WebSearch`. Без неё писатель сам тянется к WebFetch проверить источники для `claims`, в `-p` подтвердить доступ некому — и вместо статьи приходит вопрос «разрешить WebFetch?», прогон падает с «нет frontmatter вообще». После обновления пакета перенести. Рубрики — `content_factory.categories` вида `<страна>-<тема>`, названия на сайте — `arcars-site/src/data/blog-rubrics.ts`.

**Второй сайт — только второй копией пакета** (`D:\SecondBrain\seo-factory-<сайт>`): конфиг ищется от расположения движка, а список тем, очередь и ядро лежат внутри пакета — переключение `site.config.yml` перемешает данные двух сайтов. Общее на копии: окружение Claude, сервисный аккаунт Google, ключи, Telegram-релей; лимит Wordstat 100 запросов в час — сборы разносить по времени; в `.env` обеих копий — `OWN_SITES` со всеми своими доменами. Разбор → [knowledge/courses/seo-tseh-vasina](../knowledge/courses/seo-tseh-vasina/_index.md#ответ-как-вести-на-заводе-второй-сайт).

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
.tools/venv-whisper/Scripts/python.exe .tools/universal/media/transcribe-video.py "<папка или файл>" [--out <папка>]
```
