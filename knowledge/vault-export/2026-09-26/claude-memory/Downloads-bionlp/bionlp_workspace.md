---
name: bionlp workspace + ToolUniverse usage
description: Dedicated bio-research workspace at C:\Users\Prekzursil\Downloads\bionlp
  — ToolUniverse 1.1.11 MCP global, 2216 tools, 108 Agent Skills installed
type: project
originSessionId: 7d868df4-f868-4a58-acac-c022173b11b4
permalink: main/claude-memory/downloads-bionlp/bionlp-workspace
---

**Workspace:** `C:\Users\Prekzursil\Downloads\bionlp\`
- `.venv\` — pinned Python 3.12 venv, tooluniverse==1.1.11 (frozen in `requirements.lock`)
- `.env` — API keys (gitignored): NCBI_API_KEY, SEMANTIC_SCHOLAR_API_KEY, FDA_OPENFDA_KEY, UMLS_API_KEY all set (UMLS approved by NIH on 2026-04-09)
- `scripts/bionlp.sh` — unified health/uninstall script (`bash bionlp.sh health`)
- `scripts/PROBE-RESULTS.md` — source of truth for install choices (CLI syntax, tool IDs, skill path)
- `notebooks/`, `scripts/`, `data/` — analysis artifacts
- `docs/plans/` — design and implementation plans (v1, v2, v3)

**MCP integration:** ToolUniverse registered globally in `~/.claude.json` as `tooluniverse`, command `uvx tooluniverse` (compact mode is the default in that entrypoint — no flag needed). Keys are LITERAL strings in the env block. Pre-install backup at `~/.claude.json.bak-pre-tooluniverse`.

**Stats:**
- **2216 tools** in the ToolUniverse catalog (2x what the README advertises)
- **108 Agent Skills** installed via `npx skills add mims-harvard/ToolUniverse -y -g` → `~/.agents/skills/tooluniverse-*` (symlinked to Claude Code)
- All skills appear in every Claude Code session globally

**Compact Mode tools (visible to Claude in every session):**
- `list_tools` — enumerate all tools
- `grep_tools` — keyword search over tool names/descriptions
- `find_tools` — semantic search (default on)
- `get_tool_info` — tool schema + description
- `execute_tool` — actually run a tool

**Verified working tool IDs (from smoke tests):**
- `EuropePMC_search_articles` — keyless, args `query=STRING limit=INT`
- `PubMed_search_articles` — uses NCBI_API_KEY, args `query=STRING limit=INT` (plus mindate/maxdate/include_abstract/sort)
- `OpenTargets_get_associated_targets_by_disease_efoId` — 64 OpenTargets tools total

**How to use:** Ask Claude for bio/medical/drug/gene/paper research. Claude auto-discovers via `find_tools`/`grep_tools` then `execute_tool`. For workflow skills (e.g. drug repurposing, rare disease diagnosis), invoke by name: `/tooluniverse-drug-repurposing`, `/tooluniverse-rare-disease-diagnosis`, `/tooluniverse-clinical-trial-matching`, etc.

**Windows Unicode fix:** `PYTHONIOENCODING=utf-8` is set in the MCP config env block and in `bionlp.sh`. For manual `tu` CLI calls, set it: `export PYTHONIOENCODING=utf-8` before running `tu`.

**Why:** User wants biomedical research capability from any Claude Code session without polluting the unrelated SWFOC editor game-modding repo.

**How to apply:**
- Any bio/medical query → use ToolUniverse MCP tools (automatic) or invoke a `tooluniverse-*` skill by name
- Workspace-specific work (notebooks, Python scripts) → route to `bionlp/` folder
- API keys live in `bionlp\.env` + literal in `~/.claude.json`. Never suggest moving them.
- Re-validate install: `bash /c/Users/Prekzursil/Downloads/bionlp/scripts/bionlp.sh health`
- Uninstall cleanly: `bash /c/Users/Prekzursil/Downloads/bionlp/scripts/bionlp.sh uninstall`