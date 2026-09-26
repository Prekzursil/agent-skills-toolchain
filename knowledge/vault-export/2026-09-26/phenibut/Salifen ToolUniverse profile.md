---
title: Salifen ToolUniverse profile
type: note
permalink: main/phenibut/salifen-tool-universe-profile
---

# Salifen ToolUniverse profile (2026-06-22)

Salifen = phenibut salicylate salt (Volgograd/RGPU/Tyurenkov analog). ABSENT from PubChem-by-name, ChEMBL, BindingDB, EuropePMC, PubTator (Russian-only lit). Resolved as 1:1 salt of:
- Phenibut (active CNS component): CID 14113, C10H13NO2, MW 179.22, SMILES NCC(c1ccccc1)CC(=O)O
- Salicylic acid (counter-ion): CID 338, C7H6O3, MW 138.12
- Salt MW ~317.3

## Measured (ADMET-AI / SwissADME)
Phenibut: BBB_Martins 0.732 (51st pct); SwissADME BBB permeant=Yes, GI=High, Pgp substrate=No, no CYP inhibition (all n/d), 0 Lipinski viol, QED 0.73, TPSA 63.3, cLogP 0.56 consensus / 1.20 ADMET-AI. Tox: AMES 0.038 (neg), hERG 0.054 (low), DILI 0.126 (low), LD50 2.32. Clearance low, t1/2 short, VDss low — renal-leaning PK consistent with program PK split hypothesis.
Salicylate: BBB_Martins 0.547; DILI 0.449 (moderate), higher hepatocyte clearance.
Salt-as-mixture SMILES BBB collapses to 0.349 (artifact of concatenated-SMILES averaging; salts dissociate — judge by phenibut ion).

## DDI (mechanism-typed)
Both components are CYP-quiet (no inhibition predicted) -> CYP-mediated DDI unlikely. Salicylate moiety: PD-additive/displacement risks are salicylate-class (plasma protein binding displacement, GI/antiplatelet), NOT phenibut-driven. Phenibut PD-additivity = GABA-B/CNS-depressant additivity (mechanism only).

## New angle
Salt design rationale (RGPU): salicylate counter-ion may add an independent anti-inflammatory/analgesic PD arm on top of phenibut's GABA-B anxiolysis — a dual-pharmacophore co-crystal/salt, not a new receptor entity. BindingDB similarity scan on phenibut returns 0 measured affinities (re-confirms ChEMBL/BindingDB absence anchor).


## CORRECTION (corpus-verified 2026-06-22)
Identity + stoichiometry confirmed against local corpus (D:\Research\projects\phenibut\docs\SAR_TABLE.md L99/108/111/159/168), NOT name-inferred:
- Salifen = RGPU-189 = phenibut salicylate, **2:1 phenibut:salicylic acid** (not 1:1). Salt MW ~496.6 (2*179.22 + 138.12).
- Cation IS phenibut (4-amino-3-phenylbutanoic acid) — corpus-explicit; NOT glufimet/tolibut.
- Dose anchors (rat, preeclampsia-offspring): 7.5 mg/kg early / 15 mg/kg late; antihypoxic 2.16x survival (hypobaric) vs phenibut 1.61x.
ADMET battery unaffected (salt dissociates to phenibut + salicylate ions; both profiled).

## Additional ADMET-AI endpoints (phenibut)
Solubility_AqSolDB -1.04 (83rd pct, good); Lipophilicity_AstraZeneca -1.13; HydrationFreeEnergy -12.7.
Nuclear receptors ALL inactive (NR-AR/AhR/Aromatase/ER/PPARg all <0.05). Stress-response ALL low (SR-ARE/ATAD5/HSE/MMP/p53 <0.03). => phenibut is endocrine- and stress-pathway-quiet; off-target liability is GABA-B/a2d on-mechanism only.
