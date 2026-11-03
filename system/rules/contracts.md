# Контракты волта @system

> Перенесено из `CLAUDE.md` 2026-11-03 без изменений смысла. Состояние, чекбоксы, данные, терминология. `CLAUDE.md` держит короткую версию и ссылку сюда; правило меняется здесь.

## State contract

Three rules with one purpose: the vault must describe **now**, not the day a file was written. Introduced 2026-08-25 after a project dashboard was found describing cancelled products for two and a half months without a single signal.

**1. One owner per fact.** A price, a channel, a client's state, a deadline — each lives in exactly one file; every other file links to it instead of restating it. This rule already holds for terminology (glossary is the only source → Terminology contract); it holds for state the same way. A fact written in N places rots N times faster, because updating costs N and forgetting costs nothing. When you find a copy, delete the copy and link. Owner files say so in their header — see `life/decisions.md`, `life/finance/finance-plan-h2-2026-v2.md`, `agency/finmodel.md`.

**2. Write conditions, not states.** «Не X, пока не Y» instead of «X не делаем». A state statement dies the moment the state changes and gives no signal that it died; a condition can be checked on any day and answers itself. Same for statuses: «черновик, ждёт публикации» rots, «публикуем, когда есть Y» does not. Applies to plans, gates, blockers and file statuses.

**3. Freshness is declared, never inferred.** `дата:` says when a file was written, which is not whether it is still true. Three marks carry that:

| Mark | Means | Who reads it |
|---|---|---|
| `**Проверено:** YYYY-MM-DD` | confirmed current on that date | `quality-check.py`: thresholds by type — decisions 90 дн., client materials 45, plans 30. Marketing OS method files and unclassified artifacts are not checked by calendar |
| `годен-до: YYYY-MM-DD` (frontmatter) | explicit expiry, stronger than type | `quality-check.py` |
| `- [вне] что сверяем ⟳ YYYY-MM-DD` | the fact's state lives **outside** the vault — a channel, a site, a payment, a campaign. `⟳ —` = never confirmed | `review.py` prints them as questions in every прогон |

The `[вне]` mark is the only thing that brings external events back in: tasks and file freshness both look inward, so a video that went live, a payment that landed or a certificate that expired changes nothing in the vault by itself.

**When state has moved on:** extract the reusable conclusion, then replace or delete. Never keep a superseded version in the active layer, and **never patch a stale file with a banner on top** — the banner leaves the wrong body underneath, and the body is what gets read.

# Checkbox contract

Introduced 2026-09-01, after ~600 checkboxes were found scattered across 50 files where none of them was a task.

A `- [ ]` in the vault means exactly one thing: **a step of a mechanic performed against an object** — a checklist run per client, per launch, per shift. Project actions, deadlines and assignees stay in YouGile, including agency-building work.

Nothing else carries a checkbox:

| What it actually is | How it is written |
|---|---|
| «сделать однажды» | YouGile. The vault never holds a task |
| Brief questions, meeting protocol, imported course notes | plain list items — a question has no state «выполнено» |
| A regulation with thresholds (a daily desk checklist) | plain items: it is run again every day, so no line is ever «done» — пороги, не галочки |

Why the discipline: one symbol carrying four meanings turns any material into a task list. The vault stores a reusable checklist as part of a mechanic; it does not store the current run of that checklist or its completion history.

# Data contract

The vault stores **conclusions and artifacts**, not raw data and not generated output.

- **Raw exports** (1С, Б24, ad accounts, Wordstat) live next to the tool that eats them — `.tools/` or the project's dashboard folder — and are not versioned.
- **Generated output** (`dashboard/data.js`, SQLite, screenshots a script re-creates) is not versioned; it is rebuilt by the script that made it.
- **What stays in git:** the script, its config, the conclusion in markdown, and the artifact someone actually reads — a chart, a client report, a competitor screenshot kept as dated evidence. A fresh clone therefore shows empty dashboards until their scripts are re-run.

## Terminology contract

- The only canonical source of Marketing OS definitions is `marketing-os/core/glossary.md`. Read the relevant card before using a specialized term.
- Use the Russian canonical name in working text; an English original or abbreviation may be shown at first mention and remains searchable as an alias.
- Do not redefine terms inside routes, engines, playbooks, or skills. Those files may describe application, not assign a second meaning.
- If a recurring or ambiguous term is absent, define it in the glossary before adding it to the method.
- Keep **доказательство для клиента** (`proof`, reduces a buyer's concrete doubt) separate from **доказательство метода** (`evidence`, validates an OS element through measured application).

**Before improvising a mechanic, open the catalog** — `marketing-os/_index.md` carries engines and playbooks with a status and a «Вызывать, когда» trigger. Reach for an existing one; if none fits, that is itself the signal that a new mechanic may be worth capturing.

Frameworks, with their real addresses (`knowledge/frameworks/` holds imported outside theory only — it is not a second home for the method):
- **JTBD** — `knowledge/frameworks/jtbd.md`; applied → engine `niche-icp-jtbd-research.md`, skill `/jtbd-segments`
- **Hormozi Value Equation** — `knowledge/frameworks/hormozi.md`
- **RDB** — glossary card `core/glossary.md#term-rdb`
- **Schwartz awareness levels** — `routes/one-product-flow/schwartz-entry-map-2026-07-06.md`, step `steps/s4-schwartz.md`
- **AARRR** — glossary card `core/glossary.md#term-aarrr`; assembly → skill `/aarrr-funnel`
