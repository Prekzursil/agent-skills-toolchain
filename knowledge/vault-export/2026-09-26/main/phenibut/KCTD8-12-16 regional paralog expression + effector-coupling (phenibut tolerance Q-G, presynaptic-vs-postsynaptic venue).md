---
title: KCTD8/12/16 regional paralog expression + effector-coupling (phenibut tolerance
  Q-G, presynaptic-vs-postsynaptic venue)
type: note
permalink: main/phenibut/kctd8-12-16-regional-paralog-expression-effector-coupling-phenibut-tolerance-q-g-presynaptic-vs-postsynaptic-venue
---

# KCTD8/12/16 regional paralog expression + effector coupling

Pulled via ToolUniverse (GTEx v8, STRING, UniProt) + scholarly-access/tavily 2026-06-25. Extends Q-G (GABA-B tolerance) and the "presynaptic-vs-postsynaptic KCTD12/16 pools + regional expression" venue. EXTENDS the KCTD12-only note (main/phenibut/kctd12-tool-universe-evidence-phenibut-tolerance-target-g).

## CORRECTION to prior framing (advisor-caught)
Bulk GTEx is compartment-BLIND. The KCTD12/16 TPM ratio does NOT directly measure subcellular pre/post pools. What it DOES resolve: regional complement of FAST-desensitizing (KCTD12) vs SLOW-desensitizing (KCTD8/KCTD16) auxiliary subunits. Pre/post localization is region- AND cell-type-specific (primary lit), not paralog-intrinsic. Do not propagate "KCTD12/16 ratio = pre/post proxy".

## Identity
- KCTD16 = UniProt Q68DU8 (KCD16_HUMAN), 428 aa, ENSG00000183775. "Auxiliary subunit... accelerates onset and promotes desensitization."
- KCTD12 = Q96CX2, 325 aa, ENSG00000178695 (fast desensitizer, Gbg-scavenger).
- KCTD8 = ENSG00000183783, slow desensitizer (H2 domain suppresses desensitization, like KCTD16).

## Regional GTEx v8 median TPM (data]
Region | KCTD12 | KCTD8 | KCTD16 | GABBR1 | GABBR2
Cerebellum | 38.0 | 28.6 | 0.32 | 277 | 62.5
Cerebellar Hemi | 36.4 | 32.8 | 0.29 | 327 | 62.7
Substantia nigra | 29.6 | 3.57 | 0.42 | 77.1 | 8.26
Nucleus accumbens | 27.6 | 9.94 | 2.20 | 230 | 5.27
Hippocampus | 19.6 | 3.46 | 2.31 | 99.8 | 18.5
Amygdala | 17.5 | 3.70 | 2.10 | 131 | 17.7
Caudate | 17.9 | 6.91 | 2.29 | 161 | 4.50
Cortex | 10.9 | 6.09 | 4.93 | 169 | 64.2
Frontal cortex BA9 | 15.3 | 10.9 | 7.24 | 211 | 84.0
Putamen | 12.5 | 4.77 | 1.47 | 136 | 3.03
Liver | 1.78 | 0.0 | 0.008 | 4.17 | 0.010

## KEY regional signals [data]
- CEREBELLUM: slow-desensitizing role carried by KCTD8 (28.6), NOT KCTD16 (0.32). KCTD12 fast (38). KCTD8>>KCTD16 here — the 12/16-only frame mis-calls cerebellum.
- SUBSTANTIA NIGRA (VTA-arm, Q-B): KCTD12-dominant (29.6), KCTD8/16 both low (3.6/0.42). Fast-desensitizing-skewed regional complement.
- CORTEX/BA9: most KCTD16-enriched (4.9-7.2), lowest KCTD12:KCTD16 ratio (~2x). Slow-desensitizing-skewed.
- KCTD12:KCTD16 ratio spans ~120x (cerebellum ~120, SN ~70) to ~2x (BA9) — large regional dynamic range = computable axis.

## Effector-coupling fingerprint (STRING >=200) [data] — the DERIVED pre/post handle
- KCTD12: GNB1 0.903, GNG2 0.839 (Gbg-scavenging), CUL3 0.569. NO direct KCNJ(GIRK) or CACNA1(Cav) edge. -> couples to Gbg-stripping machinery.
- KCTD16: **CACNA1B (Cav2.2, presynaptic N-type) 0.525** — UNIQUE among the three. GABBR2 0.961, GABBR1 0.516. -> presynaptic Ca-channel-coupled context.
- KCTD8: RIMS4 0.432 (presynaptic active-zone), SSTR3 0.460 (presynaptic GPCR). -> presynaptic-leaning context.
This is data-DERIVED (not an imported label): KCTD16/KCTD8 carry presynaptic-effector edges; KCTD12 carries the Gbg-scavenger edge.

## Primary-lit compartment mapping (corrects/qualifies labels)
- Schwenk 2010 Nature (PMID 20400944): KCTD8/12/12b/16 "distinct expression profiles", subtype-specific desensitization. Foundational.
- KCTD16 anchors GBR-HCN channel complexes in VTA DA neurons (biorxiv 2021.09.27.461912, Bettler lab) — DIRECT Q-B relevance (HCN/Ih in DA neurons).
- KCTD8+KCTD12 facilitate AXONAL (presynaptic) GBR expression in habenula cholinergic neurons (JNeurosci 2022, 42:1648).
- eLife 68274: KCTD12 immunoparticles mostly POSTsynaptic at asymmetric synapses; KCTD8/12b peri-/active-zone presynaptic in MHb. => compartment is circuit-specific, not paralog-fixed. "KCTD16 expressed most brain areas but NOT MHb."
- Structural basis PMC6405316: KCTD12 vs KCTD16 BTB(T1)/H1 domains; H1 binds Gbeta.

## NEW ANGLES
1. Effector-coupling fingerprint (STRING) cleanly separates KCTD16 (CACNA1B presynaptic) from KCTD12 (Gbg-scavenger) WITHOUT assuming compartment — strongest computable pre/post discriminator. Next: regionally co-correlate each KCTD's TPM vs GIRK-set {KCNJ3/6/9} vs Cav-set {CACNA1A/1B} across the 10 brain regions (cor matrix in RDKit/pandas — pull KCNJ/CACNA1 GTEx and compute Pearson).
2. SN paradox for Q-B: GABA-B is DENSE in SN (GABBR1=77) but the SLOW/presynaptic KCTD16 is nearly absent (0.42) while FAST KCTD12 dominates (29.6). If VTA mirrors SN, DA-neuron GABA-B there is fast-desensitizing — could shape the tonic-disinhibition timecourse (phenibut acute vs tolerance). KCTD16-HCN coupling (biorxiv) is the slow/Ih arm — low KCTD16 in SN means HCN-coupling is region-limited.
3. KCTD8 is the cerebellar slow-desensitizing subunit (not 16). Any "12/16 pool" model must be a "12 vs (8+16)" fast-vs-slow model, regionally weighted.
4. snRNA-seq (gtex_snrnaseq_pilot) would give cell-type (not subcellular) resolution of KCTD12:KCTD16:KCTD8 per neuron class — closer to circuit.

## Tool notes
- GTEx_get_median_gene_expression: multi-gene array works; v8 dataset (v10 empty).
- STRING_get_interaction_partners: required_score in 0-1000 (200=low). KCTD16-CACNA1B only surfaces at >=400.
- KCTD16 UniProt: search needs gene:KCTD16 AND organism_id:9606 AND reviewed:true (Q68DU8). Q6PDC7 is a WRONG accession (404).
