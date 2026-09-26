---
title: GABBR1 ToolUniverse research dump (2026-06)
type: report
permalink: main/phenibut/gabbr1-tool-universe-research-dump-2026-06
tags:
- phenibut
- GABBR1
- GABA-B
- tooluniverse
- target
- tolerance
---

# GABBR1 (GABA-B1) ToolUniverse EXECUTE-MAXIMAL dump

UniProt Q9UBS5 (GABR1_HUMAN), 961 aa, gene GABBR1, ChEMBL CHEMBL2064, KEGG hsa:2550, ENSP00000366233, GtoPdb target 240, Pharos TDL=**Tclin** (approved-drug target), novelty 0.0009 (well-studied).

## Identity / structure
- Heterodimeric Class C GPCR: only **GABBR1 binds agonist**, GABBR2 couples G protein. Orthosteric pocket = Venus-flytrap; ligand-contact residues **S247/S270/H287/.../466** (PDB 4MS3 GABA, 4MS4 baclofen agonist, 4MRM/4MR7 phaclofen antagonist).
- Topology: ECD 20-591 (2 Sushi domains 30-159), 7TM 592-854, cytoplasmic C-tail 855-961 with coiled-coil 869-925 + **ATF4-interaction region 888-916** (matches STRING ATF5 hit).
- Structures: AlphaFold AF-Q9UBS5-F1 (pLDDT 84.19, full len); cryo-EM **7C7S** full receptor inactive +CGP54626 2.9A; X-ray ECD 4MS4.
- NEDLC disease variants (PMID 36103875): E368D, A397V, A535T, G673D — all decrease/abolish GPCR signaling.

## Affinity (TAG species+measure-type to avoid clashing with program Ki anchors)
- DrugCentral: **baclofen MoA = human GABA-B agonist**, pIC50 7.46 (GABBR1+GABBR2); off-targets GABA-A, ADORA3.
- GtoPdb (mostly RAT, functional pIC50): baclofen 4.4-4.6; GABA 4.5; antagonists CGP56999A 9.1-9.2, CGP54626 8.7-8.8, CGP62349 8.8-9.0; lesogaberan pEC50 8.1 (human); SCH50911 6.4; CGP35348 4.6-4.8.
- Pharos ligands: GS39783 (PAM) pEC50 7.1; lesogaberan 8.1; 3-APPA.
- BindingDB returned EMPTY for Q9UBS5 (consistent: phenibut absent; baclofen indexed elsewhere). ChEMBL search endpoint 500-down this session (recorded once, no retry).

## Pathway / network (mechanism B + G)
- Reactome: GABA-B activation R-HSA-977444; **Activation of GIRK channels R-HSA-1296041**; **Inhibition of voltage-gated Ca2+ via Gbeta/gamma R-HSA-997272**; Gi signaling.
- KEGG hsa:2550 pathways incl GABAergic synapse hsa04727 and **Morphine addiction hsa05032**.
- STRING heterodimer interactome: GABBR2 0.999, GNAI1/2/3 (Gai), KCNJ3/6/9/5/11 (GIRK/Kir3), GNB1/GNG2/GNB5 (Gbg) — molecular basis of tonic disinhibition.
- **KEY for question G (tolerance): STRING GABBR2-KCTD16 = 0.961 (escore 0.946, high experimental)** — KCTD16 auxiliary subunit network-confirmed. Also MPDZ (PDZ scaffold), JAKMIP1 (trafficking), ATF5.
- Perroy et al EMBO J 2003 (PMID 12881416): **GRK4 mediates phosphorylation-INDEPENDENT, kinase-domain-independent GABA-B desensitization, only in neurons (cerebellar granule) not HEK293** — primary mechanism for GRK-arm of tolerance.

## Expression (GTEx via Pharos, TPM)
Brain-dominant: cerebellar hemisphere 357, nucleus accumbens 242, frontal cortex BA9 224, ACC 215, cortex 172, caudate 179; **substantia nigra 83 / nucleus accumbens 242 = VTA-relevant for DA-disinhibition hypothesis**. Low periphery: liver 4.2, skeletal muscle 5.8.

## Clinical/safety (baclofen as GABA-B agonist proxy, mechanism-typed PD)
FAERS top signals = on-target CNS depression: fatigue, somnolence, gait disturbance, falls, dizziness, coma 1500, encephalopathy 1055, **DRUG WITHDRAWAL SYNDROME 2252**, seizure 1667/convulsion 792 — mirrors phenibut GABA-B-agonist withdrawal (question E).

## NEW angles
1. KCTD16 (not KCTD12) is the network-dominant auxiliary subunit for human GABBR2 — refine question-G tolerance model toward KCTD16.
2. GRK4 desensitization is phosphorylation- AND kinase-domain-INDEPENDENT (scaffolding) and neuron-specific — explains why HEK recombinant assays miss phenibut/baclofen tolerance.
3. ATF4/ATF5 binds the 888-916 C-tail coiled-coil region — transcriptional arm linking GABA-B to ATF (potential withdrawal/plasticity coupling).
4. baclofen ADORA3 off-target (pIC50 7.3) — possible adenosine-mediated PD overlap.
