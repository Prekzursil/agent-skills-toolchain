---
title: Comparator withdrawal-management mechanisms (baclofen/GHB/gabapentinoid) -
  compute angle
type: note
permalink: main/phenibut/comparator-withdrawal-management-mechanisms-baclofen-ghb-gabapentinoid-compute-angle
tags:
- phenibut
- comparators
- withdrawal
- GABA-B
- a2d
- compute
---

# Comparator withdrawal-management mechanisms - compute-grounded angle

Date 2026-06-25. Lens: ToolUniverse (ChEMBL/OpenTargets/FDA) + RDKit + local Schrodinger/OpenMM stack.

## Target anchoring (ChEMBL, verified this pass)
- Baclofen (CHEMBL701) and sodium oxybate/GHB (parent CHEMBL1342) BOTH = GABA-B receptor AGONIST, target CHEMBL2111463. GHB MoA comment: "not fully elucidated, proposed through GABAB".
- Gabapentin (CHEMBL940) and pregabalin (CHEMBL1059) BOTH = voltage-gated Ca-channel MODULATOR at alpha2delta-1, target CHEMBL2363032 (binding_site_comment explicitly "alpha2delta-1").
- This splits the comparators into exactly phenibut's two validated targets: GABA-B (baclofen, GHB) + a2d (gabapentinoids). Phenibut straddles both.

## RDKit Tanimoto vs phenibut (Morgan, this pass)
- phenibut vs baclofen = 0.70 (HIGH - only diff is para-Cl; matches validated GABA-B docking H->Cl anchor +6.09)
- phenibut vs pregabalin = 0.39
- phenibut vs gabapentin = 0.21
- phenibut vs GHB = 0.19
- baclofen vs pregabalin = 0.36
Phenibut is structurally a des-chloro baclofen; this is why GABA-B is its primary target and a2d secondary.

## RDKit descriptors (amw / tpsa / HBD / HBA / RotB / CrippenClogP / FractionCSP3)
- phenibut: 179.2 / 63.3 / 2 / 2 / 4 / 1.20 / 0.30
- baclofen: 213.7 / 63.3 / 2 / 2 / 4 / 1.86 / 0.30
- pregabalin: 159.2 / 63.3 / 2 / 2 / 5 / 1.08 / 0.875
- gabapentin: 171.2 / 63.3 / 2 / 2 / 3 / 1.37 / 0.889
- GHB: 104.1 / 57.5 / 2 / 2 / 3 / -0.16 / 0.75
ALL share TPSA 63.3, HBD2/HBA2 = GABA-mimetic zwitterion pharmacophore. Discriminator = aromatic ring (phenibut/baclofen FractionCSP3 0.30) vs aliphatic gabapentinoids (0.88).

## Withdrawal-mechanism anchors (FDA/OpenTargets, this pass)
- Baclofen carries US Black Box Warning: psychiatric + neuro + musculoskeletal toxicity (abrupt-withdrawal hyperexcitability). FDA label: CNS depressant, "sedation with tolerance", GABA-B stimulation.
- GHB/oxybate Black Box: neurotoxicity + respiratory + misuse. FDA label names GABA-B action at noradrenergic, dopaminergic AND thalamocortical neurons - directly ties to phenibut Q-B (VTA disinhibition) and TRN_THALAMOCORTICAL_ANGLE doc.
- Pregabalin FDA label: a2d high-affinity, explicitly does NOT bind GABA-A/B/benzo; upregulates GABA-transporter density on chronic dosing (a tolerance-adjacent adaptation).

## Corpus quantitative anchors (already in SAR_TABLE.md)
- Baclofen GABA-B Ki = 6 +/- 1 uM (Dambrova 2008, [3H]CGP54626 rat forebrain); R-phenibut ~15x weaker; baclofen ~10-12x clinically more potent.
- Clinical substitution ratio 8-10 mg baclofen per 1 g phenibut (DiFiore 2024, Bonnet 2024) - cross-tolerance confirms shared GABA-B mechanism.

## Why this matters
Withdrawal management = cross-tolerance substitution at the SHARED receptor. Baclofen works for phenibut withdrawal because Tanimoto 0.70 / same GABA-B target. Gabapentinoids are the a2d-only fallback (Tanimoto 0.2-0.4). The compute stack can quantify the substitution rationale structurally, not just clinically.
