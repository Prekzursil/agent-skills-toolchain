---
title: KCTD16 ToolUniverse data dossier (phenibut Q-G)
type: report
permalink: main/phenibut/targets/kctd16-tool-universe-data-dossier-phenibut-q-g
tags:
- phenibut
- KCTD16
- GABA-B
- tolerance
- tooluniverse
---

# KCTD16 dossier (real ToolUniverse data, pulled 2026-06)

IDs: UniProt Q68DU8 (human, KCD16_HUMAN, 428 aa), Ensembl ENSG00000183775, Entrez 57528, HGNC:29244, locus 5q31.3, mouse Q5DTY9. ChEMBL targets CHEMBL4523340 (human)/CHEMBL4523323 (mouse) but NO small-molecule bioactivity records (PPI-only target). Pharos Tdl=Tbio, novelty 0.099, only 9 pubs (understudied).

## Function / role (answers phenibut Q-G: GABA-B tolerance machinery)
UniProt: "Auxiliary subunit of GABA-B receptors that determine pharmacology and kinetics; increases agonist potency and markedly alters G-protein signaling by accelerating onset and promoting desensitization." Member KCTD8/12/12b/16 family. Binds GABBR2 C-tail via T1/BTB domain (asymmetric pentameric ring); H1 domain binds Gbetagamma.
Subcellular: presynaptic + postsynaptic membrane.

## AFFINITY (hard numbers, Zheng et al. Nature 2019 PMC6405316 ITC full text)
Gbetagamma affinity hierarchy (KD): GTP-Gai undetectable; GIRK channels ~250 uM; **KCTD H1 domain ~185 nM**; GDP-Gai ~3 nM. KCTD binding to Gbetagamma is HIGHLY COOPERATIVE (5:5 complex, Gbeta-Gbeta contacts R42/R46). Model: KCTDs cooperatively STRIP Gbetagamma from GIRK -> rapid desensitization. This is the molecular basis of GABA-B desensitization kinetics — directly relevant to phenibut tolerance.
Sereikaite JMedChem 2019 (PMID 31509708): first peptide inhibitor of KCTD/GABBR2 PPI; induces KCTD16 hexamer.

## STRUCTURE (PDB, all real)
6OCP = GABBR2 peptide bound to KCTD16 T1 (2.35A); 6OCR/6OCT = KCTD16 T1 domain; 6I0Q = KCTD16 BTB hexamer (2.3A); 6QB7 = KCTD16 H1 domain (2.23A); also 5A15, 6M8R. AlphaFold AF-Q68DU8-F1 (avg pLDDT 69.1, monomer).

## EXPRESSION (OpenTargets HPA/GTEx consensus)
Strongly brain-enriched: prefrontal cortex RNA 3339 (z=5, highest), brain 2034, frontal lobe 1726, BA9 1117, temporal lobe 1113, cerebral cortex 743, BA24 721; also caudate/putamen/nucleus accumbens/amygdala/hippocampus. Cerebellum + cerebral cortex protein level 3 (reliable). Pancreas RNA 451. Low in immune/blood. nucleus accumbens 294 + substantia nigra/VTA expression supports VTA-DA relevance.

## INTERACTIONS
STRING (clean): GABBR2 0.961, CUL3 0.595, GABBR1 0.516, KCTD20 0.511, KCTD12 0.490 (hetero-oligomer), KCTD8 0.454, KCTD2 0.443. Enrichment: protein homo-oligomerization GO:0051260 (KCTD2/8/12/16, FDR 0.0023); neuron-glial signaling (GABBR1/2).
IntAct (Q68DU8) credible: GABBR1, GABBR2, NSF, RIMS1. (Note: APP/SORL1/NTRK1 cluster via EBI-302641 = isoform-mapping artifact, discard.)
Reactome enrichment EMPTY for KCTD16 (not pathway-annotated — Tbio understudied).

## NEW ANGLES for phenibut program
- Perez-Garci Neurobiol Dis 2025 (PMID 39914775): KCTD16 anchors HCN2/HCN3 channels to GABA-B in VTA dopamine neurons; KCTD16-KO -> prolonged GABA-B inhibition of DA-VTA firing + anxiety. DIRECT mechanistic tie to Q-B (VTA DA disinhibition) AND Q-A (anxiolysis). KCTD16 is the scaffold that tunes GABA-B output duration in exactly the VTA-DA circuit the dopamine-puzzle invokes.
- KCTD12/KCTD16 hetero-oligomers (PMID 28003345) give intermediate desensitization kinetics — tolerance could be hetero-oligomer-ratio-dependent, a testable axis.
- Vasconcelos Neurobiol Dis 2026 (41592618): KCTD16 sets baclofen analgesic efficacy (KO loses baclofen anti-allodynia) — relevant to R-phenibut/baclofen shared GABA-B pharmacology (Q-F).

DailyMed/FAERS/openFDA/DrugCentral N/A (non-drug gene). KEGG N/A (Reactome empty corroborates).
