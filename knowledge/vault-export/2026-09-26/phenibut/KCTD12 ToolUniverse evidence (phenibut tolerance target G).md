---
title: KCTD12 ToolUniverse evidence (phenibut tolerance target G)
type: note
permalink: main/phenibut/kctd12-tool-universe-evidence-phenibut-tolerance-target-g
tags:
- phenibut
- KCTD12
- GABA-B
- tolerance
- tooluniverse
- druggability
---

# KCTD12 ToolUniverse evidence (phenibut tolerance target G)

Pulled via ToolUniverse 2026-06-22. Extends program question G (GABA-B tolerance machinery; KCTD12/16 Gbetagamma scavenging).

## Identity
- UniProt Q96CX2 (KCD12_HUMAN), 325 aa; Ensembl ENSG00000178695; Entrez 115207; HGNC:14678; chr13q.
- Aliases C13orf2, PFET1, PFETIN, KIAA1778. Pharos TDL = **Tchem** (has chemical probes), novelty 0.039, 30 pubs.
- Domains: BTB/POZ T1 (IPR003131), H1 (IPR049905 H1_KCTD12); Pfam PF02214 (BTB_2), PF23110 (H1_KCTD8_12_16).

## Mechanism (OpenTargets + PubMed primary sources)
- GABA-B auxiliary subunit; binds GABAB2 C-tail via **T1**, accelerates onset + promotes **fast desensitization** of GIRK/Kir3 currents.
- Zheng/Kruse 2019 Nature (PMID 30814734): KCTD12 forms ASYMMETRIC PENTAMERIC ring on GABA-B C-tail; **H1 domain symmetrically engages 5x Gbetagamma**, cooperatively STRIPS Gbetagamma off GIRK -> desensitization. This is the literal Gbetagamma-scavenging machinery.
- Turecek 2014 Neuron (24836506): dual G-protein binding (constitutive stabilize + dynamic uncouple Gbetagamma).
- Adelfinger 2014 (25065880): GABAB2 **Ser892 PKA phosphorylation** cross-regulates / slows KCTD12 desensitization -> ties KCTD12 to the phospho-tolerance axis.
- Seddik 2012 (23035119): H1 T/NFLEQ motif confers desensitization; KCTD8/16 H2 domain suppresses it.
- Li 2017 (28713569): human KCTD12 KO mouse -> reduced seizure susceptibility AND reduced high-conc ethanol consumption (behavioral handle relevant to GABA-B drug tolerance/withdrawal).

## Structure
- PDB 6QZL (1.98A, X-ray) H1 domain of human KCTD12.
- PDB 6M8S (3.71A) KCTD12 H1 domain in complex with **Gbeta1gamma2** — experimental confirmation of scavenging interface. (Both supersede AlphaFold Q96CX2 for the folded domains.)

## Druggability — REAL measured affinities (ChEMBL CHEMBL4523424, doc CHEMBL4321811)
- 141 activities; campaign targets recombinant human KCTD12 **T1 domain res 27-131**.
- SPOT peptide microarray EC50 (assay CHEMBL4322698): best **160 nM (pChEMBL 6.80)**, 180/210/210/250/300 nM next; range 160 nM–20.5 uM.
- FP displacement of TAMRA-peptide (CHEMBL4322699) Ki: best **1.34 uM** (1.86, 13.6 uM others).
- Orthogonal assays in same doc: ITC Kd (CHEMBL4322700), SEC-MALS oligomer, Thermofluor, and **HEK293 co-IP disrupting KCTD12-GABAB1b/2 interaction** (CHEMBL4322705). NOTE these T1 binders target the oligomerization/GABAB2 interface, NOT directly the H1-Gbetagamma scavenging site — do not conflate.

## Expression (GTEx v8 median TPM)
- Brain-enriched: Cerebellum 38.0, Substantia nigra 29.6, Hippocampus 19.6, Amygdala 17.5, Cortex 10.9; Whole blood 12.7; **Liver 1.78** (low).
- Substantia-nigra expression is relevant to the VTA/DA-disinhibition arm (question B). HPA "Mitochondria" subcellular call CONFLICTS with GO/membrane/synapse consensus — treat as HPA data error, do not propagate.

## Interactions (STRING >=400 / IntAct)
- Top STRING: GNB1 0.903, GNG2 0.839 (Gbetagamma), then KCTD11/GABBR1 0.634/KCTD16 0.49/GABBR2 0.506/CUL3 0.569.
- IntAct: KCTD12 homo-oligomerization confirmed (self, 3 expts) — consistent with pentameric T1 ring.

## NEW ANGLE
A T1-domain KCTD12 inhibitor (existing chemotype, EC50 ~160 nM, disrupts KCTD12-GABAB2 co-IP) is a concrete **tolerance-reversal lever**: blocking KCTD12 assembly slows GABA-B fast desensitization -> could blunt R-phenibut/baclofen tolerance. Tractable, brain-expressed, Tchem. Caveat: T1 binders act on receptor assembly, distinct from the H1/Gbetagamma scavenging step (Zheng 2019).

## Tool note
WikiPathways returned 0 KCTD12 pathways. ChEMBL activity tools are ToolUniverse-internal (execute_tool), not ToolSearch-deferred.