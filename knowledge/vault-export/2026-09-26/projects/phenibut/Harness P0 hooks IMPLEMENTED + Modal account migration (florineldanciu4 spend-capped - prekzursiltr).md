---
title: Harness P0 hooks IMPLEMENTED + Modal account migration (florineldanciu4 spend-capped
  -> prekzursiltr)
type: report
permalink: main/projects/phenibut/harness-p0-hooks-implemented-modal-account-migration-florineldanciu4-spend-capped-prekzursiltr
tags:
- harness
- hooks
- claude-code
- modal
- migration
- phenibut
---

# Harness P0 hooks IMPLEMENTED + Modal account migration

## SOTA harness research -> P0 implemented (2026-06-20)
Ran a deep-research + adversarial-grill workflow (`SOTA-HARNESS-RECOMMENDATIONS.md` in `~/.claude/`); the grill KILLED 9 candidates as hype/dup (Graphiti/Mem0 2nd-memory, Langfuse+Docker, no-fabricated-path guard, Consensus/Perplexity dups, etc.). User said "implement all except 1 (safety is okay)". DONE + wired in `settings.json` + validated (JSON valid, both hooks compile + behavior-tested):
- **#2 fresh-context verify TRIGGER** — `~/.claude/hooks/fresh-verify/trigger.py` (PostToolUse, matcher `mcp__ida-pro-mcp__.*|mcp__cheatengine__.*|mcp__ghidra-mcp__.*`). Counts hex-address reuse; at >=8 reuses of a value with no independent check, injects a directive to invoke the `fresh-context-verify` skill (separate clean-context model JUDGES). The F2 wrong-but-consistent-anchor residual; complements anti-degen `fingerprint.py` (mechanical spin). RE-scoped so interactive sessions are never touched. Fail-open.
- **#3 citation/temporal-memory convention** (zero-install) — added provenance-graph routing (`mcp__scholarly-access__paper_citation_graph` / PubTator3) to `TU-MODULE-INDEX.md`; added `superseded_by`/`valid_as_of` front-matter convention to `CLAUDE.md` memory section (temporal-memory invalidation, no graph DB, mirrors `note.py --supersedes`).
- **#4 compchem pre-flight probe** — `~/.claude/hooks/compchem-preflight/probe.py` (PreToolUse, matcher `mcp__schrodinger__glide_dock|mcp__schrodinger__prime_mmgbsa`). Once per session, injects simplest-probe-first reminder: verify ligand MW/formula/charge/stereo (RDKit/`molecule_properties`) BEFORE burning GPU — motivated by the real β-phenyl-β-alanine 165-vs-179 Da SMILES slip. Fail-open.
- **SKIPPED #1** (PowerShell `permissions.deny` safety backstop) per user. Hooks activate next session (load at startup).

## Modal migration — florineldanciu4 SPEND-CAPPED
Root cause of the "rate limit / hang": **`florineldanciu4` workspace hit its billing-cycle SPEND LIMIT** -> "App creation failed" -> it can NOT run ANY jobs (FEP hung, pack failed). Volume DATA reads still work. User chose to **switch to `prekzursiltr`** (fresh budget) rather than top up.
- Approach = **A (copy the INSTALLED suite, NOT re-install — user: "avoid further reconfig")**. The tarball/pack path is DEAD (can't run a function on a spend-capped account). Re-install path (B) rejected by user.
- `modal volume get` mangles the suite's symlinks ("`jaguar.../macro_pka already exists`") — fix = pre-create the dest dir (recursion) + **`--force`** (overwrites the duplicate symlink paths).
- Done: results+inputs mirrored to `D:/Research/projects/phenibut/_modal_mirror/`; license is local (`D:/Research/_assets/schrodinger-licenses/26-2.lic`); `schrodinger` volume created on prekzursiltr. IN PROGRESS: `modal volume get schrodinger /suites2026-2 ... --force` (~15GB). NEXT: upload suite+lic_support+fep_inputs to prekzursiltr -> resume FEP (re-run α2δ + connected-map SAR) on the fresh account.
- Use `MODAL_PROFILE=<profile>` env var per-command to target a profile without changing the global active one.

See [[FEP per-edge parallelization has a QUALITY COST — use connected map for validation-grade ddG]] and [[Corpus-mine COMPLETE — adversarial verification REFUTES phenibut-PEA-DA-release; B reframed]].
