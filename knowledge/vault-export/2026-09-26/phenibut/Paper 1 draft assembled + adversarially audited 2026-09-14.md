---
title: Paper 1 draft assembled + adversarially audited 2026-09-14
type: note
permalink: main/phenibut/paper-1-draft-assembled-adversarially-audited-2026-09-14
tags:
- phenibut
- paper-1
- manuscript
- atm-rbfe
- honesty-floor
---

# Paper 1 draft assembled + adversarially audited (14.09, session 3fb11978)

Executed council step 1 (draft Paper 1) via an ultracode workflow (ground → draft → 3 adversarial audits → conditional revise), then a targeted second revision folding in the step-2 splice finding.

- [fact] Draft on disk: `docs/PAPER_1_DRAFT_2026-09-14.md` (~48.6 KB). Title (option 1, no QM clause): "Computational evidence that R-phenibut is the GABA-B eutomer: alchemical transfer free-energy validation and an honest failure report at α2δ-1".
- [fact] All five canonical ΔΔG rows verbatim from RESULTS.md; §3.3 explicit non-convergence paragraph present (zero round trips → error bars are lower bounds; 1.04 kcal seed spread; statistical-only error, FF ~1 kcal excluded); "clears the bound" stays retracted; SI "not for human use" box present.
- [decision] R→S is SIGN-ONLY; both seeds reported as co-equal rows with NO privileged magnitude — dropped the "canonical published number" label (seed 1 primary only by precedence, not correctness; seed 2 equally valid that the true value may be ~1 kcal lower). No averaging.
- [fact] Adversarial audit (3 lenses) = 1 CRITICAL + 4 MAJOR + minors. The CRITICAL (Afolabi citations flagged as possible fabrication) was a FALSE POSITIVE — the auditor grepped only RESULTS.md; I confirmed by grep that "Afolabi" + PMIDs 41832720/42462355 are real and filed in `docs/` (COMPETITOR_OVERLAP_2026-08-18.md, read in full). Citations kept.
- [fact] MAJORs fixed: (1) FEP+ +1.74±0.41 was wrongly cast as an unconverged α2δ failure — it is a CONVERGED GABA-B SAR cross-check recovering the ranking (README L29); removed from the α2δ stack, with a status flag that RESULTS.md still lists FEP+ as optional/blocked pending an SI CSV. (2) references preamble corrected (only Zvejniece in the compute SSOT; Afolabi grounded in COMPETITOR_OVERLAP; mood citations verification-pending). (3) seed de-privileging. (4) splice-mechanism rewrite — see [[ATM splice 10-11 falsifier — direct measurement REFUTES broken-splice autopsy 2026-09-14]].
- [decision] Open before submission (owner calls): QM-clause title decision; FEP+ +1.74 status reconciliation (README "converged" vs RESULTS.md "blocked/optional"); verify Fatemi/Cathomas/Zuo PMIDs; and — since the α2δ GPN failure mechanism is now UNRESOLVED (not splice) — decide how much of the ECC/site-model investigation belongs in Paper 1 vs the Paper-2 methods track.
