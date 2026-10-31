---
title: corpus
type: note
permalink: dqverify-repo-20261013/agent-self/skills/hacktricks/references/corpus
---

# HackTricks local corpus

- **Location:** `D:\knowledge\hacktricks\` (override with env `HACKTRICKS_CORPUS`)
  - `hacktricks\src\` — main book: pentest, web, AD, mobile, crypto, forensics, network, OS internals, general dev tricks.
  - `hacktricks-cloud\src\` — cloud book: AWS, GCP, Azure, Kubernetes, CI/CD.
- **Size:** about 1,600 Markdown pages total (Markdown-focused, not literally Markdown-only). The
  reproducible 2026-07-24 receipt was 995 main + 593 cloud = 1,588 Markdown files, about 38 MiB
  including Git metadata. Counts drift upstream; do not treat any single number as permanent.
- **Index:** each book's `src\SUMMARY.md` is the full page tree.
- **Sparse:** `--no-cone`, set `/src/**` + `!/src/images/**`. This excludes `src/images/**` but
  RETAINS `src/files`, `src/pdfs`, and occasional nested images — it is not a Markdown-only checkout.
- **Refresh:** `pwsh scripts/htk_update.ps1` (never on lookup, SessionStart, or CI).
- **Search substrate:** host/PowerShell ripgrep (fast). `htk_search.ps1` file order is ripgrep
  TRAVERSAL order, not match-count ranking, and it shows at most three matches per file — do not
  present it as a relevance rank. The corpus on `D:` is also reachable from WSL at
  `/mnt/d/knowledge/hacktricks` if needed (slower over 9p).
- **AI wiki:** `ai.hacktricks.wiki` is NOT a separate open repo — its AI layer is served by the
  authenticated REST API (see the `hacktricks-api` skill).
- **License:** original HackTricks text is CC BY-NC 4.0 — personal reference only; attribute
  HackTricks if reused and preserve the noncommercial restriction. Third-party excerpts retain their
  own terms. The skill/wrapper code itself is MIT.