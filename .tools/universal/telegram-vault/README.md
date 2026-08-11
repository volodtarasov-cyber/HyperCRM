# Telegram ↔ HyperCRM

Один приватный бот для двух режимов:

1. `/report` и автоматический будничный отчёт — короткий срез из живых
   `projects/**/_dashboard.md`.
2. Обычный текст — запрос локальному Codex в контексте HyperCRM: поиск,
   чтение, фиксация решений и гипотез, создание и обновление проектных файлов.
3. Голосовые — временно скачиваются, локально расшифровываются Whisper и
   передаются в тот же контекст Codex. Скачанная копия удаляется сразу после
   расшифровки, до запуска Codex.

## Безопасность

- Бот принимает действия только от одного `owner_user_id`, полученного при
  установке из реального сообщения `/start`.
- Codex работает с sandbox `workspace-write` и корнем HyperCRM.
- В шлюз встроен запрет выдавать в Telegram токены, пароли и содержимое
  `access.md`.
- Токен бота хранится в macOS Keychain. Telegram ID, состояние диалогов и логи
  лежат локально в `~/Library/Application Support/HyperCRM Telegram Bot/`, вне
  Yandex Disk.
- Текст переписки отдельно не журналируется. Контекст хранится как ID локальной
  сессии Codex.
- Голосовые ограничены 20 минутами и 25 МБ. Оригинал остаётся в Telegram;
  локальная копия живёт только во временной папке и удаляется даже при ошибке.

## Установка

1. Создать бота через `@BotFather` и получить токен.
2. Запустить в Терминале:

```bash
cd "/Users/vladimirtarasov/Yandex.Disk.localized/HyperCRM"
.tools/venv/Scripts/python.exe .tools/universal/telegram-vault/setup.py
```

3. Вставить токен в невидимый prompt, отправить боту `/start` и подтвердить
   найденный Telegram user ID.

Без ручной работы с Терминалом: скопировать токен `@BotFather` в буфер обмена,
отправить новому боту `/start` и попросить Codex завершить установку. Токен будет
прочитан из буфера напрямую и не появится в чате или выводе команд.

Установщик проверит бота, сохранит секрет локально, создаст launchd-агент
`com.hypercrm.telegram-vault` и запустит его. По умолчанию отчёт приходит по
будням в 08:30 по Самаре.

## Команды

- `/report` — сводка из всех живых дашбордов.
- `/new` — новый контекст разговора с Codex.
- `/status` — состояние связки.
- `/reporthere` — направить автоотчёты в текущий чат/группу.
- `/time 08:30` — изменить время будничного отчёта.
- `/help` — справка.

В группе бот реагирует только на команды, ответ на его сообщение или
`@упоминание`; и только если отправитель совпадает с `owner_user_id`.

## Диагностика и остановка

```bash
.tools/venv/Scripts/python.exe .tools/universal/telegram-vault/bot.py --self-test
launchctl print gui/$(id -u)/com.hypercrm.telegram-vault
tail -n 50 "$HOME/Library/Application Support/HyperCRM Telegram Bot/bot.err.log"
launchctl bootout gui/$(id -u) "$HOME/Library/LaunchAgents/com.hypercrm.telegram-vault.plist"
```
