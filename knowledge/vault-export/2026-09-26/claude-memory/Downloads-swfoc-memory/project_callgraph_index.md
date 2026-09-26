---
name: SWFOC callgraph + subsystem index
description: Queryable SQLite + Python CLI built on top of the IDA full corpus. Lets
  you find callers/callees, BFS-cluster a feature's neighborhood, list functions sharing
  RTTI class membership, and identify subsystems untouched by any verified ledger
  entry. Built 2026-04-26.
type: project
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/project-callgraph-index
---

The IDA full corpus has been indexed into a queryable callgraph at
`knowledge-base/callgraph_index.sqlite` and exposed via
`tools/callgraph_query.py`.

**Why:** The IDA corpus is 123 batch JSONs totaling ~165MB. Grep is too
slow for "what calls Make_Invulnerable" or "which unverified functions
sit between feature X and feature Y." The SQLite index turns every such
question into a sub-second query, and the BFS-based `feature` and
`untouched` subcommands surface the structural relationships between
verified features automatically.

**How to apply:** When wiring a new feature or fixing an existing one,
start with `python tools/callgraph_query.py feature <fact_id_substring>`
to see the verified module + the unverified functions in its
neighborhood. Use `callers` / `callees` for one-hop lookups,
`cluster` for N-hop neighborhoods, and `rtti <class_name>` to find the
class's full method set. Use `untouched --hops N` to find candidate
functions for new features (functions reachable from no verified
feature within N hops).

**Index stats (2026-04-26 build):**
- 22,728 unique functions (deduped from the 22,828 corpus entries)
- 152,032 code-edge xrefs (data-section refs are dropped — they don't
  resolve to a containing function)
- 3,737 RTTI vftable references across 1,401 distinct classes
- 282 verified-fact joins (the 30 ledger entries without an `rva` field
  — mostly struct definitions — are correctly skipped)
- ~1.2s rebuild time

**Schema:**
- `functions(addr, name, prototype, size, end_addr, source_batch)`
- `xrefs(src_func_addr, src_addr, dst_func_addr, edge_type)` — `edge_type`
  is `code` or `data`. The xref `src_addr` is the **call site** (an
  individual instruction inside `src_func_addr`).
- `rtti_refs(func_addr, class_name)`
- `verified_facts(rva, abs_addr, fact_id, category, confidence, claim)`
- `meta(key, value)` for build provenance

**Known limitations:**
- Data-section xrefs (table entries in `.rdata` referring to a function)
  are not resolved to a "src function" because they're not inside any
  function. ~55,960 such refs were dropped during build. To extend the
  index for "find the Lua binding table containing this wrapper",
  add a separate `data_xrefs(src_addr, dst_func_addr)` table that
  doesn't try to resolve src to a function.
- The RTTI extractor uses the regex `&([A-Za-z_][\w:<>,\s\*]*)::\\\`vftable'`
  which catches the standard MSVC mangled vftable references in IDA
  Hex-Rays output. It does not catch class methods that don't reference
  a vftable (e.g. plain non-virtual member functions).
- `untouched --hops 3` from 275 VERIFIED seeds only reaches 1,899
  functions (8.4% of the binary). Most of the corpus is genuinely
  outside the trainer's scope (renderer, audio, particle systems,
  STL container instantiations, MSVC runtime). When evaluating
  candidates for new features, filter `untouched_subsystems.md` by
  RTTI class to focus on actual game-logic subsystems.

**Reporter outputs (refresh with `python tools/callgraph_report.py`):**
- `knowledge-base/feature_modules.json` — for every VERIFIED feature,
  its 2-hop call module with verified vs unverified breakdown and the
  list of verified anchors at depth 1 (i.e., features that share
  immediate substructure)
- `knowledge-base/untouched_subsystems.md` — functions reachable from
  no VERIFIED ledger entry, clustered by RTTI class