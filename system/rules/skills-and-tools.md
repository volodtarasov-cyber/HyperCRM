# Скилы и инструменты @system

> Перенесено из `CLAUDE.md` 2026-11-03 без изменений смысла. Какой скил по какому триггеру и как запускать инструменты. `CLAUDE.md` держит короткую версию и ссылку сюда; правило меняется здесь.

## Technical tools

- **Storage — everything on D:** (decision 2026-10-06). C: is the system disk and is nearly full; D: holds the work. Projects, tool environments, model and package caches, downloads, course material and generated data go to D:. Tools that write to the user profile by default are pointed at `D:\.cache\` through user environment variables before first use. If a program cannot live outside C:, say so instead of installing it there silently.
- **Tool layout:** reusable scripts live in `.tools/universal/`; scripts tied to data, URLs, or branding live in `.tools/projects/<project>/`. Full index: `.tools/README.md`.
- **Outside the vault:** SEO factories, `arcars-site`, `agency-site` — locations, git remotes, keys and which site each factory serves → single passport `.tools/README.md#вне-волта`.
- **Playwright** (`.tools/venv/Scripts/python.exe`, Python 3.14): `.tools/universal/web/snapshot.py <url> <prefix>` — desktop+mobile screenshots of any URL into `.tools/snapshots/*.png`, read via Read. For layout control after edits and competitor analysis.
- **Analytics:** new calculations — a separate py-script in `.tools/projects/<project>/analytics/` (not in Bash). Template — `.tools/projects/bingo-samara/analytics/zayavki-analysis.py` (parse → aggregate → conclusions). Call and video transcription stays local — client recordings never leave the machine; scripts in `.tools/universal/media/`.
- **Social publishing and content factory** (Instagram / Threads, only on explicit request) → `.tools/README.md`. Preparing a post and sending it are separate actions; a final click is never retried after an uncertain result. Factory material states do not replace tasks in YouGile.
- **YouGile API:** `.tools/universal/yougile/yougile.py` — `tree`, `tasks`, `create`, `push`; connect once with `Подключить YouGile.bat`. Creation only after explicit yes → «Tasks in YouGile». Limit 50 requests/min per company.
- **SEO dashboard:** `.tools/universal/seo-dashboard/` — all SEO factories on one page; sites listed in `sites.yml`. Reads state, holds no tasks.
- **MCP (unstable):** Google Drive (reading Sheets/Docs) + Google Calendar. Always keep a fallback to manual export.

# Which user skill to call when

| User trigger | Skill |
|---|---|
| «карточки с кейсом / комплект кейса для Instagram, Threads и Telegram / проверь превью в инсте» | `/agency-carousel` — `.claude/skills/agency-carousel/SKILL.md`; правило читаемости миниатюры → `team/brand-style.md` |
| «напиши пост / рассылку / лонгрид / лендинг / черновик» in first person (Volodya's or a client's voice) | `/copywriter`; mailing format and first-line hooks → its `references/` |
| «очеловечь / отредактируй / убери ИИ-шность / сделай живее» готовый текст | `/humanize-text` |
| **Without a trigger:** any model-written text (SEO factory article, page copy, `/copywriter` draft) before it goes to a client for approval or onto a site | `/humanize-text` — mandatory last pass, facts untouched |
| «собери VSL / сценарий видеопродавца / продающее видео» | `/vsl-script` (экспериментальный, не проверен) |
| «скрипт продаж / скрипт квалификации / разбери переписки, чаты, звонки / почему не покупают в чате / разбери нишу по диалогам» | `/sales-script` (pilot) — исполняет движок `marketing-os/engines/sales-script-design.md` |
| «собери воронку / стратегию привлечения / разложи на этапы» | `/aarrr-funnel` |
| «коробка шока / что отправить лиду / как прогреть» | `/shock-awe-box` |
| «на какой стадии бизнес / что ему сейчас нужно / почему не растёт / куда расти» | `/growth-stage` (draft) — 10 стадий роста и главное ограничение компании; первый шаг `/business-diagnostic` и контекст для `/screening` |
| «денежная модель / лестница предложений / что допродать / как поднять средний чек или LTV / клиент не окупает рекламу» | `/money-model` (draft) — валовая прибыль за 30 дней против CAC, сетка предложений |
| «собери оффер / упакуй или усиль предложение / гарантия, бонусы, название акции / лид-магнит» | `/offer` (draft) — исполняет движок `marketing-os/engines/offer-packaging-design.md` |
| «сделай объявления / креативы для VK, Директа, Авито / зацепки для роликов / реклама выгорела / план тестов креативов» | `/ad-creatives` (draft) — проверка «стоит ли реклама», банк зацепок 70-20-10, части объявления, бюджет на объявление и от мощности, журнал теста |
| «акция по базе / быстрые деньги / что продать своим клиентам / квартальная акция» | `/base-campaign` (draft) — проверка «стоит ли сейчас», сегменты и фильтр у каждого сообщения, премиум ×10 с лимитом от мощности, цепочка на 5–7 дней, не купившие, ритм 90 дней |
| «скрининг бизнеса / где узкое место» | `/screening` |
| «собери профайл компании / данные для анализа» | `/company-profile` |
| «JTBD-сегменты / карта сегментов / кому продаём» | `/jtbd-segments` |
| «кластеризуй семантику / разбей ключи по группам / структура РК для Директа или Google Ads / кросс-минусация» | `/ppc-keyword-clustering` |
| «карта пути клиента / CJM / где теряем по шагам / точки перелома» | `/cjm` |
| «полная диагностика бизнеса / прогон как у Ребдеу / под ключ» (оркестратор цепочки) | `/business-diagnostic` |
| «прогон дизайна / почему выглядит шаблонно / ИИ-шный дизайн / ревью сайта или лендинга» | `/impeccable critique` + `audit`; browser measurements → `/design-taste-frontend` (redesign → review) |
| «сделай / переделай лендинг, сайт, страницу круче» | `/design-taste-frontend` for pages; `/impeccable` for refinement passes (`bolder`, `quieter`, `typeset`, `layout`, `polish`). Agency documents follow `DESIGN.md` — the brand wins over the detectors |
| «проверь правки / убедись что работает» (after UI edits) | `/verify` |
| «запусти приложение / покажи как выглядит» | `/run` |
| «обзор кода / ревью PR» | `/code-review` or `/review` |
| Set up a schedule (routines, recurring tasks) | `/schedule` |
| Loop "do X every N minutes" | `/loop` |

**Rule:** if the user clearly matches a trigger — call the skill **before** generating the answer, not instead of it. Don't mention a skill without calling it.
