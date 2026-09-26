---
title: qdx-rush MCP v2 hardened (deep-research audit)
type: report
permalink: main/projects/phenibut/qdx-rush-mcp-v2-hardened-deep-research-audit
tags:
- qdx-rush
- mcp
- exess
- phenibut
- hardening
---

# qdx-rush MCP v2 hardened (deep-research audit)

`D:\Research\_infra\qdx_mcp\qdx_mcp_server.py` was hardened from v1→v2 via a 7-agent deep-research + audit workflow (2026-07-03). **20 tools** now (added `save_run`).

## What changed (13 fixes, all applied)
- **F1 CRITICAL:** `run_collect` now parses real energies — `exess.ResultRef.from_raw_output(raw).fetch().calc.qmmbe` → `total_kcal_per_mol`, `is_interaction_energy`. v1 returned only object-store pointers (repr of `{path,size,format}`).
- F2/F3: `save_run(run_id,out_path)` + `prepare_protein_ligand` now BLOCKS and saves the merged complex (`run.collect().fetch()` → `list[PyTRC]` → `rush.save_structure`).
- F4: `_with_retry` on transient 5xx/429/timeouts (backoff); terminal-state envelopes `{status: done|failed|still_running|error}`.
- F5: Optional hints `T | None` + `from __future__ import annotations` (null args no longer error).
- F6: fail-fast — RI needs `aux_basis`; KSDFT geometry-opt rejected; unrestricted-KSDFT/RI-MP2 rejected. (KSDFT WITHOUT functional is ALLOWED — EXESS default B3LYP sentinel.)
- F7: `structure_info` reads the `topology` sub-dict + reports `n_fragments`/`fragment_atom_counts`.
- F12: `qdx_whoami` reports real `importlib.metadata.version('rush-py')` + `rush.session.GRAPHQL_ENDPOINT`.

## Gotchas discovered (durable)
- PyO3 hides `Result.calc` / `Calculation.qmmbe` from `dir()`/`vars()` — confirm fields via `inspect.signature(cls)` (constructor sig), not dir().
- `ManyBodyExpansion.reference_fragment` is a `FragmentRef` OBJECT (not int) → non-JSON-serializable → `_fields()` coerces unknown types to `str` or the whole parse silently falls back.
- `nnxtb.energy` takes NO charge arg — net charge lives in the input structure's formal charges.
- rush-py = `talo/rush-py` (Apache-2.0, Python ≥3.12; 3.14 can't build libqdx). No public forum; support = docs + hello@qdx.co + Google form. EXESS from Barca's group (J Chem Phys 159 044112 2023).

## Validated statically; ONE gap
Import OK · 20 tools register · parser JSON-safe (smoke test) · ruff clean · all submit kwargs verified vs real signatures. **NOT yet live-tested end-to-end** because (a) the running MCP is still v1 until a Claude/MCP restart, and (b) QDX API returned 503 this session + real EXESS jobs cost credits. Next: after restart, run one small `exess_interaction_energy` when the QDX backend is up and confirm `run_collect` returns a parsed number.

Docs synced to 20 tools: SKILL.md, README.md, QDX_REFERENCE.md, [[QDX_RUSH_MCP.md]], EN+RO paper Appendix A (PDFs rebuilt + copied to AIs Conversations). Relates to [[phenibut computational program]].
