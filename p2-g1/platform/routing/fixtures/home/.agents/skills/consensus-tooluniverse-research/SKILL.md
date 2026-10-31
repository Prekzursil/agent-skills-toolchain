---
name: consensus-tooluniverse-research
description: Use when downloading or systematically harvesting research from Consensus.app — extract each shared search browser-free from the page __NEXT_DATA__ payload, resolve every cited paper to a DOI and open-access PDF with ToolUniverse (Crossref, OpenAlex, Unpaywall, EuropePMC), organize by topic with a DOI-linked bibliography, capture the Consensus Meter graphs, and verify headline claims against primary sources. Bundles paste-ready AI-scope and user-scope instructions for mechanistic neuropharmacology and harm-reduction research.
---

# Consensus + ToolUniverse Research Harvest

Turn Consensus.app searches into an organized, DOI-linked, open-access paper library — deterministically
and without a browser — then verify the claims against primary literature with ToolUniverse.

**Why two tools:** Consensus gives the *human synthesis* (meter, claims-evidence tables) but keys papers by
an internal `hash_paper_id` with **no DOI**. ToolUniverse gives the *machine provenance* (DOI → OA full-text).
They compose; neither alone is enough. Full rationale: `references/BEST-METHOD.md`.

---

## When to use
- "Download / save these Consensus searches as text + the papers + the graph."
- "Build me a paper library on <topic> with PDFs and a bibliography."
- Any systematic literature harvest where you want primary-source PDFs + provenance, not just a summary.

## Prerequisites
- **ToolUniverse** installed (`import tooluniverse`; `tu.load_tools()` before any call). `pip install requests tooluniverse` (or run with the ToolUniverse venv).
- Consensus shared-search URLs (`https://consensus.app/search/<slug>/<thread_id>/`) — public, no login.
- **Config (no hardcoding — the scripts read these):** `CONSENSUS_WS` = workspace dir (or `--ws`, default cwd);
  `UNPAYWALL_EMAIL` = your contact email (or `--email`; **required** by Unpaywall/OpenAlex, fails fast if unset).

## Run
```bash
export CONSENSUS_WS=/path/to/workspace
export UNPAYWALL_EMAIL=you@example.com
python scripts/extract_consensus.py --urls searches.txt   # one Consensus URL per line, OR pass URLs as args

### Pipeline (3 stages — scripts in `scripts/`)
### Stage 1 — extract text + paper list  (`scripts/extract_consensus.py`)
### Stage 2 — resolve + download papers, OA-only  (`scripts/resolve_and_download.py`)
### Stage 3 — the graph (Consensus Meter)
### ToolUniverse tool reference (this pipeline)
### Verify — the Consensus `analysis` is an UNVERIFIED secondary claim
### Caveats (calibrated on real runs)
### Output layout
### Research conduct
