# Структура Клиентского Workspace

> Шаблон отдельного рабочего контура одного клиента. Репозиторий хранит
> конфигурацию, решения и знания, но не сырые персональные данные.

```text
client-slug/
├── README.md
├── .gitignore
├── 00-governance/
│   ├── passport.md
│   ├── data-boundary.md
│   ├── roles-raci.md
│   ├── access-register.md
│   └── retention-and-exit.md
├── 01-config/
│   ├── source-map.yml
│   ├── field-mapping.yml
│   ├── metric-definitions.yml
│   └── business-line.yml
├── 02-diagnostic/
│   ├── screening.md
│   ├── evidence-ledger.md
│   ├── customer-journey.md
│   └── current-constraint.md
├── 03-control-board/
│   ├── objective-90-days.md
│   ├── weekly-snapshot.md
│   └── data-quality.md
├── 04-initiatives/
│   ├── active/
│   └── archive/
├── 05-decisions/
│   ├── decision-log.md
│   └── weekly-reviews/
├── 06-outcomes/
│   ├── outcome-register.md
│   └── attribution-notes/
├── 07-sop-training/
│   ├── sop/
│   ├── battle-cards/
│   ├── training/
│   └── assessments/
└── 08-handover/
    ├── integration-map.md
    ├── backup-process.md
    ├── manual-fallback.md
    ├── export-manifest.md
    └── acceptance-checklist.md
```

## Вне Репозитория

В защищённом клиентском хранилище:

```text
raw/
├── crm/
├── erp/
├── advertising/
├── telephony/
└── finance/

normalized database
call recordings
document originals
backups
secrets manager
```

## Обязательные Правила

1. У клиента отдельный workspace и отдельные права доступа.
2. Секреты передаются через менеджер секретов, а не через файлы и чаты.
3. Raw-выгрузки не коммитятся.
4. В решении указывается ссылка на источник, а не копия чувствительных данных.
5. У каждой метрики есть определение, период и дата обновления.
6. У каждого доступа есть владелец и дата отзыва.
7. До старта определяются сроки хранения и порядок удаления.
8. При завершении работы клиент получает экспорт своего контура.

## Минимальные Файлы На Старте

Если полный шаблон пока избыточен, достаточно:

```text
README.md
00-governance/passport.md
00-governance/data-boundary.md
01-config/source-map.yml
01-config/metric-definitions.yml
02-diagnostic/current-constraint.md
03-control-board/objective-90-days.md
05-decisions/decision-log.md
06-outcomes/outcome-register.md
```

