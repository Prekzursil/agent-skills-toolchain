# Eight INCOMPATIBLE-FLAG resolutions — 28.08.2026

Primary bodies are dual-written to `skills/` and `.agents/skills/`.
Exact pre-resolution snapshots remain under this `reconcile-flags/` tree.
Nothing was dropped: every non-chosen side is either a line-superset (absorbed)
or an adjacent `*.alt` file.

| # | Artifact | Chosen primary | Other side | Why |
|---|---|---|---|---|
| 1 | `battlecats-event-unlock/EVENT-UNLOCK-PLAYBOOK.md` | **live** | absorbed | Live is the same paragraph plus tbcml canonical home (Codeberg; GitHub archived; PyPI 1.1.0 stale). Root==dot. |
| 2 | `bc-drive-plus/snapshot_ring.py` | **dot** | equivalent | Same `md5(..., usedforsecurity=False)` digest; dot adds comments that the flag does not change the digest and must match on-device `md5sum`. Root==live. |
| 3 | `devtu/modes/code-optimization/README.md` | **live** | absorbed | Six table rows; live only changes link prefix to `references/…` (correct relative path). Root==dot. |
| 4 | `gem-hunt/SKILL.md` | **live** | absorbed | Live expands the anti-pattern list (OpenRouter MCP / LiteLLM / Cursor BYOK / LangGraph / duplicate Sentry) and points T0/T1 at `openrouter-routing`. Root==dot. |
| 5 | `mechanistic-ddi-pipeline/SKILL.md` | **root=live (67 tools)** | **dot → `SKILL.alt.md`** | Genuine fact split: 67 vs 12. Canonical `schrodinger-maestro-driver` skill heading is "The 67 Tools". Dot's "12 tools" line kept as alt, not silently dropped. |
| 6 | `multi-ai-mingle/SKILL.md` | **live (port 8812)** | **root → `SKILL.alt.md`**; **dot → `SKILL.dot.alt.md`** | Live is the full estate port doctrine (8812 agent-mail; 8765 is basic-memory; supervisor task). Root still says 8765 (stale, would collide). Dot is a shorter 8812 note. All three kept. |
| 7 | `phenibut-compchem/SKILL.md` | **live** | absorbed | Same ADMET table row plus v1 vs v2 (Chemprop-v2) re-run/version-label warning. Root==dot. |
| 8 | `quality-zero-platform-control-plane/scripts/audit_quality_zero_platform.py` | **live** (already a 2026-07-18 merge of both fallbacks) | **root → `.root.alt.py`**; **dot → `.dot.alt.py`** | Live documents in-file: in-process PyYAML, then `find_python_with_yaml()`, then pwsh `ConvertFrom-Yaml` last. Root is import-only; dot is the interpreter-search fallback. All three kept. |

`SKILL.alt.md` files are not skill entrypoints (loaders look for `SKILL.md` only).

> **Row 5 application gap, closed 2026-09-01 (PR #290 reconcile), kept rather than deleted:**
> commit 745b2f77 dual-wrote the `SKILL.alt.md` files but rewrote the 67-tool primary only in
> `skills/`; `.agents/skills/mechanistic-ddi-pipeline/SKILL.md` still carried the 12-tool line
> and was byte-identical to its own `SKILL.alt.md`. The `.agents/skills/` primary is now blob
> `45bac312` in both dests -- the same blob as the live snapshot under this folder and as
> PR #290's copy of the file. The adjudication itself was right; only its second write was missing.
