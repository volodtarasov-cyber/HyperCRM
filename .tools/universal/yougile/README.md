# YouGile API-клиент

Заводит карточки в YouGile через REST API v2. **Запускать локально** —
из песочницы Claude Code сеть до YouGile закрыта (их хостинг режет облачный egress),
а твоя машина до YouGile доходит (раз десктоп-приложение работает).

---

## ⚡ Авто-режим: «сказал ассистенту → появилось в YouGile»

Ассистент дописывает задачи в `queue.jsonl`, фоновый launchd-агент на маке сам
их заливает (по изменению файла + раз в 5 мин). Идемпотентно — дубли не плодит.

**Настройка один раз:**
```bash
cd "/Users/vladimirtarasov/Yandex.Disk.localized/HyperCRM/.tools/universal/yougile"

# 1. получить ключ и id доски (см. раздел ниже «Разовая настройка» шаги 1-4)
python3 yougile.py companies --login ПОЧТА --password ПАРОЛЬ
python3 yougile.py make-key --login ПОЧТА --password ПАРОЛЬ --company-id <id>
export YOUGILE_API_KEY=<ключ>
python3 yougile.py boards          # покажет id всех досок

# 2. карта досок: вписать id в boards.json (по проектам)
nano boards.json                   # заменить ВСТАВЬ_ID_ДОСКИ у левша/инфобиз/трафик/default

# 3. вписать YOUGILE_API_KEY в plist (id доски тут уже не нужен — он в boards.json)
nano com.hypercrm.yougile-sync.plist     # заменить ВСТАВЬ_КЛЮЧ

# 4. установить агент
cp com.hypercrm.yougile-sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hypercrm.yougile-sync.plist
```
Готово. Дальше ассистент пишет в очередь — карточки появляются сами.

**Как выбирается доска:** ассистent в каждой задаче ставит `"project":"левша"` (или инфобиз/трафик),
`sync.py` берёт id из `boards.json`. Нет проекта или не в карте → доска `default`.
Можно жёстко задать `"board_id"` в задаче — тогда он в приоритете.
Проверка работы: `cat pushed.log`. Снять: `launchctl unload ~/Library/LaunchAgents/com.hypercrm.yougile-sync.plist`.

> Ключ лежит в plist в `~/Library/LaunchAgents/` (вне Yandex.Disk) — в облако не утекает.

---

## Ручной режим (разовая массовая заливка)

## Разовая настройка (5 минут)

```bash
cd "/Users/vladimirtarasov/Yandex.Disk.localized/HyperCRM/.tools/universal/yougile"

# 1. узнать companyId
python3 yougile.py companies --login ТВОЯ_ПОЧТА --password ПАРОЛЬ
#   → строка вида:  <id>  Ананас Маркетинг

# 2. создать API-ключ
python3 yougile.py make-key --login ТВОЯ_ПОЧТА --password ПАРОЛЬ --company-id <id>
#   → выведет ключ

# 3. сохранить ключ в текущей сессии терминала
export YOUGILE_API_KEY=<ключ>
```

## Узнать, в какую доску лить

```bash
python3 yougile.py boards                 # список досок с id
python3 yougile.py columns --board-id B   # колонки выбранной доски
```

## Залить задачи

```bash
python3 yougile.py push --file infobiz-tasks.json --board-id B --create-columns
```

`--create-columns` — создаст недостающие колонки из файла. Без флага задачи в
несуществующие колонки пропускаются (чтобы не плодить лишнее).

## Формат файла задач

```json
{
  "board": "Инфобиз",
  "columns": [
    {
      "title": "🔥 Сейчас",
      "tasks": [
        {"title": "Задача", "description": "пояснение", "checklist": ["шаг 1", "шаг 2"]}
      ]
    }
  ]
}
```

`description` и `checklist` — опциональны. Готовый набор по инфобизу →
[infobiz-tasks.json](infobiz-tasks.json). Новые наборы генерит ассистент по запросу.

## Безопасность

- **Ключ не храним в файлах этой папки** — она в Yandex.Disk (синхронизируется в облако).
  Держи ключ в `export YOUGILE_API_KEY=...` (на сессию) или в файле вне vault.
- Логин/пароль нужны только разово для `companies` / `make-key`. Дальше — только ключ.

## Ограничение

Ассистент (Claude Code) **не может запускать это сам** — его bash-окружение не
достучивается до YouGile. Генерит файлы задач, запускаешь ты.
