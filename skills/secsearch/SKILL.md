---
name: secsearch
description: Unified offline search across ALL local security-knowledge corpora under
  D:\knowledge (HackTricks + PayloadsAllTheThings + OWASP WSTG + OWASP CheatSheets
  + Atomic Red Team, plus GTFOBins/LOLBAS prose). One ripgrep query, per-source provenance
  tags. Unlimited, no network, no quota. Use FIRST for any cross-source security/pentest/red-team
  lookup; use lolbin-lookup for structured binary lookups.
license: Skill MIT. Indexed content keeps its upstream licenses (HackTricks CC BY-NC-SA,
  GTFOBins/LOLBAS GPL-3.0, OWASP CC-BY-SA, PayloadsAllTheThings/Atomic MIT) — personal
  local reference only, no redistribution. See D:\knowledge\CORPORA.md.
permalink: dqverify-repo-20261013/skills/secsearch/skill
---

# secsearch — unified offline security-knowledge search

Search every local security corpus at once instead of remembering which book holds which technique.
The corpora live under `D:\knowledge\*` and are catalogued in `D:\knowledge\CORPORA.md`:

- `hacktricks` — pentest / web / AD / cloud / mobile / crypto / forensics (CC BY-NC-SA)
- `payloadsallthethings` — attack payloads & methodology per vuln class (MIT)
- `owasp-wstg` — Web Security Testing Guide, test cases WSTG-* (CC-BY-SA)
- `owasp-cheatsheets` — defensive AppSec cheat sheets (CC-BY-SA)
- `atomic-red-team` — ATT&CK technique docs `T####.md` + atomics (MIT)
- `gtfobins` / `lolbas` — present too, but structured (YAML); prefer the **lolbin-lookup** skill for those.

## How to search (the exact invocation)

Run ONE ripgrep query over the whole tree. Canonical parameters:

- **path:** `D:\knowledge`
- **glob:** `**/*.md`  (prose corpora; GTFOBins are extensionless and LOLBAS are `*.yml`, so use lolbin-lookup for those)
- flags: `-i` (case-insensitive), `-C 2` (context), output mode **content**.

1. **Grep tool** (preferred in-session):
   - path `D:\knowledge`, glob `**/*.md`, `-i`, `-C 2`, output_mode `content`.
   - The hit's path is its provenance: `D:\knowledge\<CORPUS>\...` — the first segment after `knowledge`
     names the source (e.g. `…\owasp-wstg\…` ⇒ OWASP WSTG).
   - Read the top 1-3 matching files in full for the actual procedure.

2. **CLI helper** (Codex / non-Grep contexts, adds explicit `[corpus]` provenance tags + ranking):

   ```
   pwsh skills/secsearch/scripts/secsearch.ps1 -Query "kerberoast" -Context 2
   ```

   It runs `rg -i --glob **/*.md` across `D:\knowledge`, ranks files by match count, and prints each
   block under a `[<corpus>] <path>` header so provenance is unambiguous. Override the corpus root with
   `-Root`, the glob with `-Glob` (e.g. `**/*.{md,yml}` to fold in LOLBAS), and result cap with `-MaxFiles`.

## Provenance

Every result carries its source. With the Grep tool the corpus is the `D:\knowledge\<CORPUS>\` path
prefix; with the helper it is the leading `[<corpus>]` tag. A single query for `kerberoast`, for
example, surfaces hits in `hacktricks`, `payloadsallthethings`, and `atomic-red-team` simultaneously —
that breadth is the point of this skill.

## When to use which skill

- **secsearch (this skill):** any prose lookup where you are not sure which book covers it, or you
  want corroboration across multiple sources (offense + OWASP defense + ATT&CK mapping in one pass).
- **hacktricks:** when you specifically want only the HackTricks book (narrower, faster).
- **lolbin-lookup:** structured "what can binary X do" / living-off-the-land queries against
  GTFOBins + LOLBAS (different query shape — name → technique → command, not prose).
- **hacktricks-api (`/rag`):** escalate ONLY when local search misses or you want a synthesized,
  cross-page answer. It is cached and rate-limited — prefer local search to conserve quota.

## Refresh

`pwsh D:\knowledge\sec-corpora-update.ps1` (or the **sec-corpora-update** skill) refreshes every
corpus except HackTricks (which uses its own `htk_update.ps1` sparse flow).