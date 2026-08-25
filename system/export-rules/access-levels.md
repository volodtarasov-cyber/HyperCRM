# Правила экспорта данных

## Уровень 1 — Приватное (только я)

Файлы, которые НИКОГДА не покидают vault:
- `life/` — вся папка
- `daily/` — дневные файлы
- `reviews/` — обзоры
- `tasks.md` — замороженный архив старой task-модели
- `inbox.md`
- `team/` — команда, роли, внутренние договорённости
- `projects/*/_notes.md` — внутренние заметки
- `projects/*/client-intelligence.md` — клиентская база знаний
- `projects/*/competitors.md` — конкурентный анализ

## Уровень 2 — Для клиента / руководства

Данные, которые можно показать:
- `projects/*/reports/` — подготовленные отчёты
- Выгрузки в Google Sheets (отдельный лист)

Правила:
- Клиент видит ТОЛЬКО свой проект
- Без внутренних заметок, гипотез, конкурентного анализа
- Без личных данных, daily, обзоров

## Уровень 3 — Шаблон системы (для передачи / инфобиза)

Что входит в стартовый кит:
- `CLAUDE.md` (можно адаптировать имена проектов)
- `README.md`
- только актуальные шаблоны из `system/templates/`; `daily_template.md` и иные замороженные ритуалы исключаются
- `system/changelog.md` — пустой
- `knowledge/frameworks/` — фреймворки JTBD, Hormozi
- обезличенное ядро `projects/marketing-os/`: `core/`, `engines/`, `routes/`, `playbooks/`, `templates/`, `maps/`, `product/`, `systems/`
- `projects/marketing-os/evidence/` — только пустая структура и очищенный шаблон proof-bank без названий клиентов, ссылок на проекты и цифр
- Пустые `_index.md` проектов
- Пустые `hypotheses.md`
- `inbox.md` — пустой
- пустой `inbox.md` и актуальные шаблоны без задач, daily-ритуалов и проектной истории

Что НЕ входит:
- Заполненные файлы проектов
- `daily/`, `reviews/`
- `client-intelligence.md` с данными
- `competitors.md` с данными
- `content-pipeline.md` с данными
- `life/decisions.md` с данными
- `team/` с данными команды
- заполненный `projects/marketing-os/evidence/` и все `applications/`
- `projects/marketing-os/sources/` — сырьё курсов, транскрипты и сторонние материалы
- `projects/marketing-os/_archive/` и `projects/_archive/one-product-flow/`
