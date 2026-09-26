---
title: Picamilon ToolUniverse data (N-nicotinoyl-GABA)
type: note
permalink: main/phenibut/analogs/picamilon-tool-universe-data-n-nicotinoyl-gaba
tags:
- phenibut
- picamilon
- GABA-analog
- ADMET
- prodrug
- tooluniverse
---

# Picamilon (N-nicotinoyl-GABA) — ToolUniverse pull 2026-06-22

GABA + nicotinic acid amide conjugate. Soviet/Russian nootropic (NIIK/All-Union Vitamin Research Inst). US: NOT FDA-approved; banned as supplement adulterant (FDA 2015).

## Identity
- Free acid: PubChem CID 60608; UNII 0S5N9SEK4N; CAS 34562-97-5; ChEMBL CHEMBL4303255; DTXSID40188098; InChIKey NAJVRARAUNYNDX-UHFFFAOYSA-N
- Sodium salt (marketed form): CID 23663986; UNII S4L664E11D; CAS 62936-56-5; InChIKey DGWZSECHAXUHPD-UHFFFAOYSA-M
- SMILES (acid): C1=CC(=CN=C1)C(=O)NCCCC(=O)O ; Formula C10H12N2O3 ; MW 208.21
- IUPAC: 4-(pyridine-3-carbonylamino)butanoic acid (= 4-nicotinamidobutyric acid)

## Descriptors (PubChem/RDKit/ChEMBL)
XLogP -0.4 ; consensus LogP 0.27 (SwissADME) ; alogp 0.68 (ChEMBL) ; TPSA 79.3 ; HBD 2 ; HBA 4 ; RotB 5 ; QED 0.70 ; Ro5 violations 0 ; very water soluble (~33 mg/mL).

## ADMET
- SwissADME: GI absorption HIGH; **BBB permeant = No** (BOILED-Egg); logKp -7.84; Pgp substrate No; all CYP1A2/2C9/2C19/2D6/3A4 inhibition = n/d (no flags); 0 PAINS/Brenk; bioavailability 0.56.
- ADMET-AI: BBB_Martins 0.636 (43rd pctile) — DISAGREES with SwissADME hard "No". Reconciliation: zwitterionic free acid (GABA COO- + pyridine N) crosses BBB poorly intact → consistent with transport-prodrug behavior, CNS effect after hydrolysis to GABA + niacin.
- ADMET-AI tox: AMES 0.021 (clean), hERG 0.014 (clean, 8th pctile), DILI 0.62, LD50_Zhu 1.90, carcinogen 0.32. Low cardiotox/mutagenic flag.

## Affinity / targets — DECISIVE
- **Santillo & Sprando 2023 (Basic Clin Pharmacol Toxicol; PMID 36668678, doi 10.1111/bcpt.13836): picamilon screened vs 50 safety targets (receptors/ion channels/enzymes/transporters), INACTIVE in silico AND in vitro at 10 uM ("weak or no binding").** Empirical confirmation picamilon is a prodrug, not a direct binder — its target profile differs from other GABA analogues.
- ChEMBL CHEMBL4303255 activities (n=11): only SARS-CoV-2 antiviral screens (~0% inhibition, IC50 >20 uM) + HDAC6 (~28% / negative) — all inactive screening junk, no real target.
- GtoPdb/BindingDB/DrugCentral: no curated affinity. ChEMBL therapeutic_flag false, prodrug -1.

## Safety (openFDA FAERS, last_updated 2026-04-28)
Tiny signal (single-digit counts): NAUSEA 3, ASTHENIA 2, HANGOVER 2, IRRITABILITY 2, MUSCLE SPASMS 2, SUBSTANCE ABUSE/INTENTIONAL MISUSE 2 each. Low volume = consistent with unregulated nootropic supplement, no approved-drug surveillance.

## Relevance to phenibut program (Q-F / analog SAR)
- Reinforces the program thesis that GABA-conjugate "prodrugs" act via RELEASED GABA, not the intact molecule — directly parallels phenibut/baclofen being direct GABA-B binders WHILE picamilon (amide-locked GABA) is inert at 50 targets.
- Picamilon = niacin transport vector for GABA (vasodilation via niacin + GABAergic after amide hydrolysis); contrasts with phenibut (beta-phenyl-GABA, lipophilic, direct GABA-B-active). The amide bond (not present in phenibut) is what kills direct binding.
- DDI typing (mechanism only): no CYP inhibition flags, not a Pgp substrate → low pharmacokinetic-DDI liability for intact picamilon; PD-additivity plausible only via released GABA + niacin (vasodilation/flush) components.
