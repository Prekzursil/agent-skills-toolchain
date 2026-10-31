---
title: EVIDENCE-GRADING
type: note
permalink: dqverify-repo-20261013/skills/consensus-tooluniverse-research/references/evidence-grading
---

# Evidence Grading — canonical T1–T4 (single source of truth)

> Referenced by `AI-SCOPE.md`, `USER-SCOPE.md`, and the `consensus-tooluniverse-research` skill.
> Designed for a **clinical / dosing / overdose** domain, so it follows GRADE / CEBM: for any claim about
> what happens **in humans** (efficacy, dose-response, toxicity, interactions), **mechanistic and
> preclinical evidence is the WEAKEST, not the strongest.** Mechanism explains *why*; it never settles
> *whether* or *how much* in people.

## Two axes — grade by BOTH

**Axis 1 — Tier (strength of the design for a *human clinical* claim):**

| Tier | Design | Use |
|---|---|---|
| **T1** | Systematic review / meta-analysis of RCTs; large well-conducted RCT | Strongest; can anchor a clinical/dosing claim |
| **T2** | Individual RCT (smaller); prospective cohort; well-powered observational with controls | Good; supports with caveats |
| **T3** | Case-control, cross-sectional, case series, registry/poison-center signal | Hypothesis-generating; not sufficient alone for dosing |
| **T4** | Single case report, narrative review, expert opinion, **extrapolation/analogy** | Context only; never settles a clinical claim alone |

**Axis 2 — Evidence type (what system was studied):**
`human` · `animal` · `in-vitro` · `in-silico`. **Animal / in-vitro / in-silico evidence is graded for a
human clinical claim as T3 *at best*, usually T4**, regardless of how elegant the mechanism — even a clean
receptor-binding study is T4 for "what dose is safe in a person."

## How to cite
`GABA-B agonism is established for phenibut [T1-mechanistic, in-vitro/animal]; that it drives clinical
tolerance is extrapolated by analogy to baclofen [T4, human evidence sparse]`.
- **Mechanism-first ≠ mechanism-as-proof.** Lead with the biochemistry to *explain*, then state the
  human-evidence tier separately. A strong mechanism with only T4 human evidence is a *hypothesis*.
- **Never** let a T3/T4 (or any animal/in-vitro) source settle a **dose, safety threshold, or interaction**
  claim on its own. If that's all that exists, say so: "no human clinical evidence; mechanism only."

## Guidance for special source types
- **Clinical practice guideline** (WHO/NICE/ASAM…): authoritative for *practice*, but cite the underlying
  evidence tier; guidelines lag and vary by region.
- **Preprint** (bioRxiv/medRxiv): tier by design, **flag as not-peer-reviewed** — cap at T3 until published.
- **Predatory / retracted**: discard. A paper existing is not authority; quality-weight every source.

## Confidence label to carry forward
Tag each carried claim: `CONFIRMED` (≥2 independent concordant T1/T2 human, no T1/T2 contradiction) ·
`SUPPORTED` (some T2/T3) · `MECHANISTIC-ONLY` (animal/in-vitro/in-silico) · `UNVERIFIED — Consensus synthesis`
(taken from a Consensus `analysis` and not yet re-checked against a primary source). Dosing/toxicity/
interaction claims must reach at least `SUPPORTED` with a human source before being stated as fact.