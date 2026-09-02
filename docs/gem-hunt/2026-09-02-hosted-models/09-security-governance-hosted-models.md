# Gem-hunt 2026-09-02 / hosted models / lens 09: security and governance of hosted and local model integration

- Lens id: `09-security-governance-hosted-models`
- Kind: discovery (research + findings). No code changed. No PR.
- Branch: `gemhunt/hosted-models-09-security-governance-hosted-models` (cut from `origin/main` at `5fa34fda1`)
- Author: Cursor cloud agent, 2026-09-02
- Status: SKELETON - sections are filled in below in the order listed; each section is committed and pushed as it lands.

## How to read this file

Every claim carries a tag in square brackets:

- `[FACT A|B|C, corroborated|UNVERIFIED, YYYY-MM-DD]` - sourced fact. Tier A = primary source (vendor policy page, standard, source code in this repo); B = reputable secondary (vendor blog, major security-research writeup, well-known press); C = community/forum/single-party claim. `corroborated` = at least two independent sources agree; `UNVERIFIED` = one source or a page I could not fetch live. The date is the date of the source or the date I read it.
- `[INFERENCE]` - my reasoning from sourced facts.
- `[RECOMMENDATION]` - what I think this estate should do.
- `[ESTATE-LOCK]` - a hard constraint from the brief; cited as a constraint, never proposed against.

Sections:

1. Scope, dedup-set and estate locks (what already exists; what this lens must not re-propose)
2. Assets and trust boundaries (what a generic inference tool touches)
3. Threat model (STRIDE-ish, per path: HF providers, HF Spaces run by strangers, OpenRouter providers, local runtimes, Cursor bridge)
4. Provider data-retention and training-use policies (one row per provider, each cited)
5. Token scoping (HF fine-grained tokens, OpenRouter per-key limits, Azure/Modal/RunPod/Lightning)
6. Licensing (model weights, models.dev registry data, Space code)
7. OWASP LLM Top 10 (2025) mapped onto the generic inference tool
8. Minimal control set the registry and tool must enforce (allowlists, redaction, ledger, kill switch)
9. Finds - per-find rubric table
10. Ten-line summary

---
