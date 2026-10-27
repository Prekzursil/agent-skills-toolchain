---
name: hacktricks
description: Search the local offline HackTricks knowledge base (~1,570 pages) for any technique or reference — pentest, cloud, web, network, Active Directory, mobile, crypto, forensics, AI security, plus general OS internals, protocols, and dev tricks. Unlimited, no network, no quota. Use this FIRST for any HackTricks or security/dev lookup; escalate to hacktricks-api only when local search is insufficient.
license: Skill MIT. Indexed content is HackTricks (CC BY-NC-SA 4.0) — personal reference only.
---

# HackTricks — local knowledge base (offline)

A sparse local clone of the HackTricks + HackTricks-Cloud books lives at:

- `D:\knowledge\hacktricks\hacktricks\src\**\*.md` (main book — pentest/web/AD/mobile/crypto/forensics/general)
- `D:\knowledge\hacktricks\hacktricks-cloud\src\**\*.md` (cloud — AWS/GCP/Azure/k8s)

This is a GENERAL reference, not just for RE/security: networking, protocols, OS internals, encoding,
file formats, and dev tricks are all here. Reach for it for any relevant lookup.

## How to search (fastest first)

1. **Grep tool** (preferred): ripgrep over the corpus.
   - path: `D:\knowledge\hacktricks`, glob: `**/*.md`, `-i`, output_mode `content`, `-C 2`.
   - Read the top 1-3 matching files in full for the actual procedure.
2. **CLI helper** (Codex/non-Grep contexts): `pwsh scripts/htk_search.ps1 -Query "<term>" -Context 3`.
3. The page tree / index is `…\src\SUMMARY.md` in each book — skim it to find the right section name.

## Refresh

`pwsh scripts/htk_update.ps1` — `git fetch` + hard reset + re-assert sparse (keeps it small, images excluded).

## When to escalate

If local search misses (new technique, or you want a synthesized answer across pages), use the
**hacktricks-api** skill (`/rag`), which is cached and rate-limited — prefer local search to conserve quota.
