# Сценарии ассистента @system

> Перенесено из `CLAUDE.md` 2026-11-03 без изменений смысла. Полный порядок действий по триггерам. `CLAUDE.md` держит короткую версию и ссылку сюда; правило меняется здесь.

# Capture a decision
**Triggers:** «зафиксируй решение», «давай решим», «решено»

1. Store only a decision that changes future choices. A conversation event or intermediate opinion is not an artifact.
2. Determine the type: current personal strategy → update the relevant block in `life/decisions.md`; testable choice about the agency model → `agency/hypotheses.md`; about one client → `clients/<client>/hypotheses.md`; current client state → update that client's `_index.md` and its row in `clients/_index.md`.
3. If a new decision supersedes an old one, replace the active formulation. Preserve the old version only in `_archive/` when historical value is real.
4. Confirm in one line: what current state changed and where.

# Capture a hypothesis
**Triggers:** «гипотеза», «давай проверим», «предположение»

1. Open `agency/hypotheses.md` (agency model) or `clients/<client>/hypotheses.md` (one client).
2. Add it only if there is a metric and an exact `YYYY-MM-DD` checkpoint. Otherwise it is an idea, not a hypothesis, and is not stored by default.
3. An active hypothesis also needs `Ответственный` and `Задача` — the YouGile code of the task that brings each measurement to that person by date. Propose the task in the same reply (→ «Tasks in YouGile»); until it exists `quality-check.py` reports `HYP_NO_TASK`. A metric with a date but no owner is how HYP-TRF-002 lost its first month.
4. A closed hypothesis must contain `Результат` and `Вывод`. Superseded hypotheses leave the active layer after their reusable conclusion is extracted.

# Capture a mechanic
**Triggers:** «сработало», «зафиксируй механику», «мы так уже делали», «повтори как в прошлый раз», and the end of any route / engine / playbook run on a real object.

The vault is a toolkit, not a library: a method stays alive only while applications come back into it. The maturity ladder already exists and is already guarded — `draft` (never applied) → `pilot` → `working` (≥1 доказательство метода) → `playbook` (≥2) → `retired`; `check_module_evidence()` in `quality-check.py` refuses `working`/`playbook` without a «Доказательства» section carrying links. The missing move is the return one. Make it:

1. **Rule of three repetitions.** First time — just do the work, write nothing. Second time — write the sequence down as a playbook or engine in `marketing-os/`. Third time — turn it into a program: a skill in `.claude/skills/` or a script in `.tools/`. Below the second repetition it is a case, not a mechanic.
2. **After a completed run on a real object** — propose recording it in `marketing-os/evidence/applications/<object>-<YYYY-MM-DD>.md`: what was applied, the input, the action performed, the **measured** result, and the conclusion about limits of applicability. An artifact without a measured result is not доказательство метода and does not move the ladder. Sample shape → `evidence/applications/levsha-ppf-2026-06-03.md`.
3. **Then re-read the status** of the file that was applied and raise it if the ladder now allows, adding the link into its «Доказательства» section (the guard reads the section, not the header). Mirror the status in the catalog table of `marketing-os/_index.md`.
4. If the application refuted the mechanic — lower the status or mark it `retired`, extract the reusable conclusion, and get the refuted version out of the active layer.
5. Confirm in one line: which mechanic moved, to what status, on the strength of what.

**Where a mechanic lives is decided by who executes it, not by topic:**

| Executor | Home |
|---|---|
| Machine — script, generator, check | `.tools/` |
| Assistant — callable instruction with triggers | `.claude/skills/` |
| Human, by method — route, engine, playbook, template | `marketing-os/` |
| Nobody — imported outside theory | `knowledge/frameworks/` |

Do not open a fifth home for «инструкции»: four are enough, and a fifth only splits the search.

# Quickly write an idea into a named folder/file
**Triggers:** «запиши эту идею в папку...», «положи в ...», «закинь в ...», «сохрани в файл...»

1. If Volodya named a folder/file — use it directly.
2. If the folder is named colloquially («в папку карт», «в Левшу», «в маркетинг») — find the closest matching file via the project's `_index.md` and existing structure.
3. Do not write new ideas into a backlog file: backlogs are frozen, tasks live in YouGile. If it's a strategic idea — create/update project material, `hypotheses.md`, or `life/decisions.md`; if it's a task — propose it as a YouGile task (→ «Tasks in YouGile»).
4. If the idea isn't in the message yet — ask for the idea and the target folder/file in one short phrase.
5. After writing, reply in one line: where you put it and what exactly you captured.

# Client status
**Triggers:** «как дела с <клиент>», «статус...», «что по...»

1. Open `clients/_index.md` — the client's row: what is bought, who executes, price, priority.
2. Open `clients/<client>/_index.md` — context, decisions, measured result, `[вне]` marks.
3. Open `results/` for the latest measured artifacts.
4. **Don't go into YouGile** — Volodya knows task statuses himself.

# Onboard a client / update the registry
**Triggers:** «новый клиент», «завели <клиент>», «изменился чек», «поменялся исполнитель», «клиент отдал данные»

1. **Price, executor, direct cost and priority go into `clients/_index.md` and nowhere else.** If you catch yourself writing a price into a card, stop — that copy will rot.
2. A new client: copy `clients/_template/` to `clients/<slug>/`, fill the passport, add the registry row. Check the admission rules in the registry before agreeing to anything.
3. **Before the offer** set the path — niche product or service for a task (`agency/product/boxes.md`); service standard for all → `clients/_service-standard.md`. Without sales tied to source no revenue-based upside.
4. Nothing verified → write `?`, never a plausible number. A `?` row is honest; an invented row poisons the P&L.
5. When a client's whole marketing starts being built and their staff enter the system → the repository rule applies: their internals move to their own repo, the card stays.

# Periodic run-through of the agency
**Triggers:** «прогон», «разбор», «что изменилось», «давай посмотрим что сделано»

Done on request to assess the current business, not as a diary ritual.

1. Run `quality-check.py --strict` — freshness, broken links and contradictory owners are part of the input.
2. Open `agency/_index.md`, `clients/_index.md`, the client cards and `agency/hypotheses.md`. Task status comes from YouGile and is not reconstructed from Markdown.
3. Read measured outputs and applications. A result seen for the **second** time is a candidate mechanic — propose capturing it (→ «Capture a mechanic»).
4. Draw conclusions in dialogue: what moved, what did not and why, what this changes in the agency model, current project state or decisions. Tasks remain in YouGile.
5. **Do not create a review artifact.** The run-through updates only current state, reusable mechanics and decisions; it does not produce a diary file.

This is not the weekly ritual banned above: it reads traces and changes current state, it does not accumulate a log of activity.

# Weekly / monthly review (on request)
**Triggers:** «неделя», «ретро», «месяц», «обзор»

> Done **only when Volodya asks**. The vault doesn't accumulate daily logs, so the review is assembled from project materials and hypotheses, not from a diary.

1. Ask which project and horizon.
2. Per project: current state, changed metrics, hypothesis results, and decisions that affect the next period. Do not reconstruct a diary of file activity.
3. Patterns: where we're stuck, what recurs.
4. By default answer in dialogue. Do not create a review file unless Volodya explicitly asks for a saved artifact.

# "Десятка" report (on request)
**Triggers:** «отчёт в десятку», «отчёт Илюшину», «десятка»

Deadline **Sun 23:59** — Volodya remembers himself, the vault doesn't remind. Template: `life/ten-report/_template.md`. I help assemble a draft when asked.

# Client report (traffic)
**Triggers:** «отчёт для...»

1. Gather data from the client's folder in `clients/<client>/`.
2. Results only — no internal notes.
3. Save to `reports/` or export to a Google Sheet.

# Inbox
**Triggers:** «разбери inbox», «inbox»

1. Open `inbox.md`.
2. Distribute each entry into the right files (decisions / hypotheses / client-intelligence / update project materials).
3. Clear the inbox.
4. If unclear — ask, don't discard.
