---
name: secsearch
description: Unified offline search across ALL local security-knowledge corpora under D:\knowledge (HackTricks + PayloadsAllTheThings + OWASP WSTG + OWASP CheatSheets + Atomic Red Team, plus the GTFOBins/LOLBAS prose). One ripgrep query, per-source provenance tags so you know which corpus each hit came from. Unlimited, no network, no quota. Use this FIRST for any cross-source security/pentest/red-team/web-AppSec lookup; escalate to hacktricks-api only when local search is insufficient; use lolbin-lookup instead for structured GTFOBins/LOLBAS binary lookups.
license: Skill MIT. Indexed content keeps its upstream licenses (HackTricks CC BY-NC-SA, GTFOBins/LOLBAS GPL-3.0, OWASP CC-BY-SA, PayloadsAllTheThings/Atomic MIT) — personal local reference only, no redistribution. See D:\knowledge\CORPORA.md.
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

### Provenance
### When to use which skill
### Refresh
