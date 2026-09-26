---
title: PrimariRo v0.1.0-alpha live + grill critical findings
type: project
permalink: main/projects/primari-ro-v0.1.0-alpha-live-grill-critical-findings
tags:
- primariro
- romania
- mayors
- journalism
- gdpr
- provenance
---

# PrimariRo v0.1.0-alpha live + grill critical findings (2026-07-17)

**valid_as_of: 2026-07-17.** Built end-to-end this session at `Documents/GitHub/PrimariRo` (private repo).

## State
- **LIVE** on GitHub Pages: https://prekzursil.github.io/PrimariRo/ (map + table; SvelteKit adapter-static, base `/PrimariRo`; Pro plan → private-repo Pages, site is PUBLIC). Release **v0.1.0-alpha** (pre-release).
- 10 build units (Codex fan-out + a finish Workflow): SIRUTA 3187 UATs, BEC-30 AUR-2024 golden (30, official AEP provenance), 2020/2024 sample terms, party registry (36), app scaffold+views, enforcement spine (schemas+models+gates), CI + GDPR pack. CI green EXCEPT the hang below.
- **Privacy policy CHANGED (owner directive):** all confidence levels published with visible badges (Confirmed/Probable/Unverified); institutional office contacts public (Art.85); output allowlist relaxed to **deployment-secret + national-ID (CNP) only**. I held the CNP free-text line; conceded Unverified-affiliation-with-label + secrets-only-gate on the elected-officials + prominent-label + newspaper-labeling arguments (a §7 concession-to-new-argument).

## GRILL critical findings (5-lens DIVERGE) — must address
1. **Integrity gates are THEATER:** `pipeline/verify/provenance_gate.py` + `dual_source.py` have NO `__main__` → their `python -m` CI steps are no-ops; `data/snapshots/` doesn't exist despite cells citing `snapshot_hash`. The core content-validated-provenance promise is **not enforced** (only `output_allowlist` got a real `main()` this session). Keystone fix: wire real `main()`s + a content-addressed snapshot store. See [[CI gate gotchas]].
2. **Legal red-team (strongest):** publishing "Unverified: [party]" about a named living official = uncapped defamation × Art.9 special-category; the label is damages-mitigation, NOT a shield → **publish the GAP not the guess** (render 0-source as "no confirmed affiliation on record", never "Unverified: X"). Also: the GDPR pack (privacy-notice / DPIA / RoPA / data-subject channel) is an empty placeholder while the site is LIVE = standalone breach. Verify the personal-contact firewall survived the allowlist relaxation.
3. **CI hang** = bec30's live-refetch test (`verify_remote_provenance` fetches 30 sources ×2) stalling to the 20-min timeout — mark live + separate job.
4. **QZP verdict: DON'T onboard** to strict-zero (catalogue-tax on a DATA repo; Sonar/Codacy/DeepScan/qlty overlap, Sentry monitors nothing, coverage-100 on scrapers is theater, half-wiring required-checks blocks main). Keep the domain data-gates; add only CodeQL + Semgrep + Dependabot + secret-push-protection. **Recommend making the repo PUBLIC** (unlimited free Actions minutes + free security tooling + transparency) AFTER a git-history scrub (BFG/gitleaks) of the deprecated git-crypt `data/private`.

## Top next-phase directions (grill, pre-decision-queue)
Per-locality **permalink pages** (highest-leverage — SEO + share + embed substrate), find-my-mayor typeahead, timeline-as-hero with party-handover arrows, trustworthy badge popovers (surface the provenance), party-switch "traseism politic" story engine (reframes AUR as one lens, defusing "why single out AUR"), static JSON API + Zenodo DOI, embeddable newsroom widget + OG cards, change-feed (RSS/Telegram), generated `coverage.json`, person-reconciliation layer, decouple data from the JS bundle (inlined `import.meta.glob` won't scale to ~28k terms).