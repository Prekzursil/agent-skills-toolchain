---
title: deadends
type: note
permalink: dqverify-repo-20261013/cyberstrike/memory/deadends
---

# Dead-end registry — REFUTED approaches (S4)

Per contract S4 (AGENTS.md:66-71): consult this registry when a task says retry / re-run /
approach-X. When declining a re-walk, cite the row id + its falsifiable precondition — never a
vague refusal. Supersede rows (`superseded_by`), never delete. No auto-load at session start
(RAM budget). Seeded 2026-09-22 by the cs-sota experiments lane from the bolt-campaign REFUTED
ledger + the plugin-shape lessons; capped — retire stale rows by supersede, not growth.

| id | refuted approach | falsifiable precondition (re-walk ONLY if this changed) | evidence anchor | date |
|---|---|---|---|---|
| DE-001 | Plugin array entry as a **bare path string** (`"plugin": ["~/.config/cyberstrike/plugin/manifest-writer.ts"]`) | Loader still bun-installs non-file://, non-npm array entries as package specs (any v1.1.16-class loader). file:// URL form is the proven-loading shape instead | TUI log `~/.local/share/cyberstrike/log/2026-09-20T230623.log` (bun add manifest-writer.ts@latest → MissingPackageJSON → BunInstallFailedError → server shutdown); commit `04aff13`; counter-proof live load via file://: log `2026-09-22T143008.log:31-32` | 2026-09-22 |
| DE-002 | Registering **session.\* as top-level plugin hook keys** (`"session.created"/"session.idle"/"session.compacted"` in the Hooks return) | Host dispatch surface gains those keys (they are absent from `@cyberstrike-io/plugin` dist/index.d.ts:108-230; session events arrive only via the generic `event` hook as `{event:{type,properties}}`). Fix shipped in `plugins/manifest-writer.ts` v2 | Zero shards + missing `manifest/` dir with plugin loaded (log 2026-09-22T143008.log:31); typings `node_modules/@cyberstrike-io/plugin/dist/index.d.ts:108-230`, `sdk/dist/gen/types.gen.d.ts:406-503,465` | 2026-09-22 |
| DE-003 | Plugin-side denial via **`permission.ask`** hook | Host starts dispatching `permission.ask` (declared in typings but exact-string count 0 in the v1.1.16 binary = never dispatched). Until then, denial goes through `throw` in `tool.execute.before` | `plugin/hook-experiment.ts:10-11` (static finding, binary v1.1.16 2026-09-20) | 2026-09-20 |
| DE-004 | **mutmut** as an on-box MCP/quality front (Windows) | mutmut ships a WSL-native Windows path (`To run mutmut on Windows, please use the WSL`); no MCP mode exists. Re-walk only if a maintained MCP entry point appears AND runs native/WSL-clean | `wiring_plan.json` `adopted_tools_probe_results` (probe 2026-09-22, impl-venv) | 2026-09-22 |
| DE-005 | **deepteam 1.0.9** as a CLI/MCP capability | `ModuleNotFoundError: sentry_sdk` at import AND no MCP entry point in dist-info. Re-walk only after `pip install sentry_sdk` into the venv AND an MCP/console entry point is verified present | `wiring_plan.json` `adopted_tools_probe_results` (probe 2026-09-22) | 2026-09-22 |
| DE-006 | **paper-qa 2026.8.12** as a CLI/MCP capability | Library only: no console_scripts entry, no `__main__`. Re-walk only if a maintained wrapper/entry point ships | `wiring_plan.json` `adopted_tools_probe_results` (probe 2026-09-22) | 2026-09-22 |
| DE-007 | **AI-Infra-Guard** adoption | Absent from impl-venv pip list, npm globals, and `D:/Research/tools`. Re-walk only after it is actually installed somewhere enumerable | `wiring_plan.json` `adopted_tools_probe_results` (probe 2026-09-22) | 2026-09-22 |

## Maintenance

- Add a row only for an approach with a DISK-ANCHORED refutation (log path, commit, probe
  receipt) — not for vibes. One row per distinct mechanism.
- Supersede: when a precondition genuinely changes, add the new row and mark the old
  `superseded_by: DE-xxx` inline; never delete history.
- Capped: if the table exceeds ~30 rows, supersede clusters into summary rows.