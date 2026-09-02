# Gem-hunt lens 07 - the generic inference MCP tool that replaces `glm53_chat`

- **Hunt:** `2026-09-02-hosted-models`
- **Lens id:** `07-generic-inference-mcp-tool`
- **Mode:** discovery, design + eval plan only. No code was changed by this lens.
- **Branch:** `gemhunt/hosted-models-07-generic-inference-mcp-tool` (cut from `origin/main` at `5fa34fda`)
- **Author:** Cursor cloud agent, 2026-09-02
- **Status:** IN PROGRESS - sections are pushed as they land; a section that is not listed as DONE
  in the checklist below was not finished when this run ended.

## Section checklist

| # | Section | Status |
|---|---------|--------|
| 0 | Frame, constraints, dedup-set, grading legend | pending |
| 1 | What `glm53_chat` does today and what a replacement must keep | pending |
| 2 | Survey: OSS MCP servers that expose OpenAI-compatible / HF endpoints as tools | pending |
| 3 | Alternative: the MCP sampling primitive (and why it is not enough alone) | pending |
| 4 | Hosting: how `tools/mcp/mcp-http-host` should host it once, not per session | pending |
| 5 | Tool surface specification | pending |
| 6 | Error taxonomy with truthful degradation | pending |
| 7 | Eval-harness spec (capability, regression, pass@k, fake endpoints for CI) | pending |
| 8 | Per-find rubric table | pending |
| 9 | Open questions and what this lens did NOT verify | pending |

## Grading legend (applies to every claim below)

- **Tier A** - primary source: the project's own repository, spec, or vendor documentation, read this run.
- **Tier B** - secondary but reputable: maintainer blog, package registry metadata, a widely cited write-up.
- **Tier C** - tertiary: aggregator, directory listing, forum post, or a single uncorroborated page.
- **corroborated** - two or more independent sources agree; **UNVERIFIED** - one source, or inferred from
  repository shape without running the code.
- Every claim is dated with the day it was read (all reads in this file: 2026-09-02 unless stated).
- Each statement is labelled **[FACT]** (sourced), **[INFERENCE]** (derived by this lens), or
  **[RECOMMENDATION]** (what this lens thinks the estate should do).
