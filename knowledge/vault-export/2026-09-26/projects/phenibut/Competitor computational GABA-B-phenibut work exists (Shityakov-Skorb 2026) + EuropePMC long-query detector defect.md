---
title: Competitor computational GABA-B/phenibut work exists (Shityakov/Skorb 2026)
  + EuropePMC long-query detector defect
type: note
permalink: main/projects/phenibut/competitor-computational-gaba-b-phenibut-work-exists-shityakov-skorb-2026-europe-pmc-long-query-detector-defect
tags:
- phenibut
- literature
- competitor
- detector-failure
- paper-a
- paper-b
- verification
---

# Two findings from 2026-08-18 that change publication strategy

**valid_as_of: 2026-08-18.** Both surfaced while independently verifying a subagent claim, not from the planned search.

## 1. We are NOT first. A group is publishing computational GABA_B work on the phenibut scaffold.

The corpus predates these. **Read both in full before submitting Paper A.**

- **PMID 41832720** — *"Development of a Novel GABA_B Receptor Modulator as an Alternative to Phenibut: Insights from Molecular Modeling and In Vivo Studies."* Afolabi SO, Netesa MA, Kolobov AV, Ovchinnikov KL, Kravtsov V, Skorb EV, **Shityakov S**. 15,000-compound Tanimoto screen → docking + MD → lead **C1** = 3-[(2-oxo-2-phenylethyl)amino]benzoic acid, ΔG_bind **−8.5** vs phenibut **−8.0** kcal/mol. **Plus an in vivo arm** (elevated plus maze, n=20 male Wistar).
- **PMID 42462355** — *"Classical substructure search versus LLM-assisted keyword retrieval in SciFinder: A case study on GABA_B1 ligand discovery using a phenibut scaffold."* Afolabi, Feoktistova, Skorb, Shityakov. Candidate **s34** (CAS 97125-82-1), AutoDock Vina **−8.9** kcal/mol, MM/GBSA **−52.80**, 500 ns MD.

**Implication:** Paper A cannot be written as if this space were empty. The novelty claim must be scoped explicitly against the Shityakov/Skorb line, which already has an in vivo arm we do not. This does not invalidate our work — our α2δ/enantioselectivity and FEP framing differ — but "first computational treatment" is no longer available as a claim.

Other new 2026 records also absent from the corpus:
- **PMID 41692998** — first LC-MS/MS method for phenibut in **hair and nail** (keratinized specimens). Adjacent to gap G7; detects the PARENT, not metabolites, so G7 likely still SURVIVES.
- **PMID 42395253** — outpatient phenibut taper case (Cureus 2026). Cite existence only; program policy forbids reproducing schedules/doses.
- **PMID 42459031** — addiction-specialist knowledge survey; supports the clinical-awareness-gap framing.

## 2. ⚠ EuropePMC / OpenAlex silently dilute long multi-term queries — a whole class of absence claims is unsound

**CONFIRMED twice** (a subagent's control log, then my own re-run minutes later on the same endpoint):

| Query | Results | Phenibut-specific |
|---|---|---|
| `phenibut` | 5 | **5** |
| `phenibut LC-MS/MS quantification blood urine` | 5 | **0** |

**The failure is worse than "returns zero".** It returns *plausible, topically-adjacent records in which the target compound never appears* — Interpol forensic reviews, ACMT abstracts, a designer-benzodiazepine review. A zero invites suspicion; five results look like a search that ran fine and found nothing. That is how a measurement artifact becomes a published absence claim.

**Rule:** any absence claim in this program resting on a long multi-term EuropePMC or OpenAlex query is **UNSOUND — re-run with SHORT queries, then filter the returned records for the target term.** Treat both "zero results" and "results that never mention the compound" as artifacts of the same defect. Paper B's gap G2 cites exactly this kind of emptiness and needs re-checking.

Two further detector failures, correctly excluded rather than reported as absence:
- **HMDB** `hmdb.ca/unearth` → HTTP 403.
- **NeuroVault** API ignored its `search` parameter and returned `count = 17,751` — the entire index. *A search endpoint that returns everything looks exactly like one that works.*

Relates to [[root-cause-ato-m-replicas-go-permanently-silent-when-remdsteps-falls-out-of-phase-with-prnt-frequency]] — same lesson in a different medium: verify the instrument before trusting its silence.
