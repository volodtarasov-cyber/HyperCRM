# Формат артефактов

## `clusters.csv`

Одна строка на один уникальный нормализованный запрос.

Обязательные колонки:

```csv
keyword,normalized,cluster_id,platform,campaign,ad_group,intent,offer,landing_page,status,confidence,reason
```

- `platform`: `yandex`, `google`, `both` или `none`.
- `status`: `active`, `excluded`, `review`.
- `confidence`: `high`, `medium`, `low`.
- Для `excluded` поля кампании и группы могут быть пустыми.
- Для `review` в `reason` должен быть конкретный вопрос или недостающий факт.
- При `both` и разной платформенной структуре добавь четыре колонки: `campaign_yandex`, `ad_group_yandex`, `campaign_google`, `ad_group_google`. `cluster_id` остаётся общим.

Сохраняй доступные метрики из prepared-файла справа от обязательных колонок.

## `negative-keywords.csv`

```csv
negative,platform,level,scope,match_type,reason,evidence,confidence
```

- `level`: `account/shared`, `campaign`, `ad_group`.
- `scope`: точное имя кампании/группы либо `all`.
- `match_type`: платформенная рекомендация, не универсальная строка.
- `evidence`: исходный запрос, отчёт или логическое правило. Если доказательства нет — `candidate` в `reason`.

## `excluded.csv`

```csv
keyword,normalized,reason,conflict_with,confidence
```

Причины должны быть предметными: `not_offered`, `wrong_audience`, `wrong_geo`, `informational_out_of_scope`, `job_intent`, `competitor_out_of_scope`, `duplicate`. Не используй нерасшифрованное `irrelevant`.

## `review.csv`

```csv
keyword,normalized,possible_cluster,question,missing_evidence
```

## `cluster-summary.md`

Короткий документ:

1. Вход и ограничения данных.
2. Сводка в цифрах.
3. Канонические кластеры и их обещания.
4. Структура Яндекс Директа.
5. Структура Google Ads.
6. Кандидаты в минус-слова и риски блокировки.
7. Неоднозначные запросы.
8. Проверка качества и предупреждения валидатора.

Не превращай сводку в построчный пересказ CSV.

