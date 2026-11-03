# Гигиена системы и шаблон для передачи @system

> Перенесено из `CLAUDE.md` 2026-11-03 без изменений смысла. Месячный чек-лист и состав шаблона системы. `CLAUDE.md` держит короткую версию и ссылку сюда; правило меняется здесь.

## System hygiene (monthly)

On phrases «давай прибрёмся / ревью системы / гигиена» — go through the checklist:
1. Run `.tools/venv/Scripts/python.exe .tools/universal/vault/quality-check.py --strict`; finish with zero errors and warnings or explicitly name the missing fact that blocks closure. `NO_CHECK_MARK` is marking debt, not rot: stamp `**Проверено:**` only on files you actually confirmed — a date you did not verify is worse than a missing one. The check also validates glossary cards, alias collisions, and floating English terms in working Marketing OS modules.
2. For broken navigation, use `repair-links.py` first in dry-run mode and then with `--apply`: unique moved targets are relinked; absent targets lose false clickable markup without creating empty placeholders.
3. Collapse stale state: replace outdated focus in `_index.md`, close overdue hypotheses with result/conclusion, and move superseded versions to `_archive/` after extracting reusable conclusions.
4. Analytics: for dated versions with the same prefix, keep one current file; move prior versions to `_archive/` and point the current file to evidence only when needed.
5. `.tools/`: check scripts are documented. Do not create a maintenance report inside the vault; stdout and the concise changelog entry are enough.

## System template (for handover / agency replication)

- Folder structure (empty)
- `CLAUDE.md`, `README.md`, `system/rules/`
- Templates from `system/templates/` (without frozen ones)
- Frameworks from `knowledge/`
- Sanitized Marketing OS core: `core/`, `engines/`, `routes/`, `playbooks/`, `templates/`, `maps/`, `product/`, `systems/`
- Empty evidence structure / redacted bank of method evidence only
- WITHOUT data, daily, notes, client information; `clients/` ships as the empty registry and the card template only
- WITHOUT Marketing OS `evidence/applications/`, populated evidence bank, `sources/`, or archives
