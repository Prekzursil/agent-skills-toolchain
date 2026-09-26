---
title: GRK4 ToolUniverse profile (phenibut tolerance hypothesis G)
type: note
permalink: main/phenibut/grk4-tool-universe-profile-phenibut-tolerance-hypothesis-g
---

# GRK4 — ToolUniverse EXECUTE-MAXIMAL profile

valid_as_of: 2026-06-22. Target of phenibut hypothesis G (GABA-B tolerance machinery).

## Identity
- HGNC:4543, symbol GRK4, "G protein-coupled receptor kinase 4", family GRK4 subfamily (GRK4/5/6).
- UniProt P32298 (GRK4_HUMAN, 578 aa); Ensembl ENSG00000125388; Entrez 2868; OMIM 137026; locus 4p16.3 (chr4:2,963,571-3,040,760, + strand).
- ChEMBL target CHEMBL5861; GtoPdb target 1468; Pharos TDL = Tchem (chemically tractable, NOT clinical).

## Affinity / chemistry (sparse — Tchem)
- Pharos: 3 ligands, 1 drug. ChEMBL CHEMBL5861 mostly %-inhibition screening, only 2 potent points:
  - Lestaurtinib (CHEMBL603469): Kd 12 nM (pKd 7.92) — pan-kinase, non-selective.
  - Balanol (CHEMBL60254): IC50 260 nM (pIC50 6.58).
  - Quinazoline-2,4-diamine CHEMBL4877302: IC50 ~22 nM (pIC50 7.66).
- BindingDB P32298: EMPTY (no records). No selective GRK4 chemical probe / approved drug.

## Function & mechanism (DIRECT hits on program)
- Phosphorylates activated GPCRs. GRK4-alpha phosphorylates rhodopsin (Ca/calmodulin-inhibited); GRK4-alpha & -gamma phosphorylate DRD3; phosphorylates ADRB2. (OpenTargets/UniProt)
- GABA-B desensitization: Kanaide 2007 (J Cell Physiol, PMID 17013811) — GRK4 (and GRK5) desensitize GABA-B by forming a protein COMPLEX with the GABA-B2 subunit at the plasma membrane; efficacy GRK4 > GRK5; GRK2/3/6 inactive.
- **Phosphorylation-INDEPENDENT**: Perroy 2003 (EMBO J, PMID 12881416) — GRK4 is necessary AND sufficient for agonist-promoted GABA-B desensitization in cerebellar granule cells; works via an ATYPICAL mechanism — kinase-dead GRK4 (kinase domain deleted) still desensitizes, no ligand-induced receptor phosphorylation. siRNA knockdown of GRK4 blocks desensitization.
- Sudo 2012 (PMID 22517292): GABA-B does NOT internalize / does not recruit beta-arrestin after baclofen even with GRK4 present — so GRK4 desensitization of GABA-B is arrestin/internalization-independent (contrasts with mu-opioid).

## Expression
- HPA: RNA tissue-specific = testis (nTPM 39.6); protein-level evidence; subcellular MAIN = plasma membrane + cytosol; additional = calyx.
- Pharos GTEx: highest testis 57.97 TPM; cerebellum ~15.4 / cerebellar hemisphere 16.69 (notable brain enrichment); pituitary 6.96; broad low-level brain (cortex 4.46, hypothalamus 4.43, hippocampus 3.94, substantia nigra 4.11, nucleus accumbens 3.54); kidney cortex 1.49 / medulla 2.42 (low but functionally important for hypertension); liver 0.89; whole blood 0.24.

## Network / pathway
- STRING top partners: GIT1 (0.998), GIT2 (0.961), ARRB1 (0.937), ARRB2 (0.926), OPRM1 (0.921), ARHGEF6 (0.807), RHO/rhodopsin (0.79), PXN (0.743) + chemokine receptors (CXCR4/2/3/6, CCR4/7). GIT1/GIT2/ARHGEF6/PXN = a focal-adhesion/ARF-GAP scaffolding cluster.
- Reactome (STRING RCTM): only Visual phototransduction / phototransduction cascade / Sensory Perception (rhodopsin role). NO GABA-B Reactome annotation — the GABA-B link is literature-only, not in curated pathway DBs.
- KEGG NETWORK: empty for GRK4 (not in disease networks). [no-data, not retried]

## Structure
- AlphaFold AF-P32298-F1 (v6), full-length 1-578, mean pLDDT 88.69, monomer, AB-INITIO.
- Only ONE experimental PDB mapped to P32298: 4YHJ (via UniProt ID mapping).

## Hypertension genetics (context)
- GRK4-gamma polymorphisms 65L/142V/486V cause salt-sensitive hypertension via impaired renal DRD1/sodium handling + renal oxidative stress (Diao 2017 PMID 28189851; Gastrorenal axis review PMID 27045027; cicletanine/HCTZ pharmacogenetic trial PMID 22278145).

## NEW ANGLES for phenibut program
1. GRK4->GABA-B desensitization is PHOSPHORYLATION-INDEPENDENT and ARRESTIN/INTERNALIZATION-INDEPENDENT — a scaffolding/complex-formation mechanism on GABA-B2. This reframes hypothesis-G "tolerance machinery": GRK4 contribution may NOT require its kinase activity, so a kinase-domain ATP-competitive inhibitor (lestaurtinib/balanol scaffolds) might NOT reverse GABA-B tolerance — the protein-protein interaction (GRK4:GABA-B2) is the druggable node, not the catalytic site.
2. GRK4 also phosphorylates DRD3 (and DRD1 functionally in kidney) — a direct dopamine-axis link relevant to the dopamine puzzle (hypothesis B): GABA-B-active R-phenibut chronically engaging GRK4 could cross-modulate dopamine receptor desensitization.
3. No selective GRK4 probe exists (Tchem, BindingDB empty) — modeling/FEP on the GRK4:GABA-B2 PPI interface (AlphaFold P32298 + GABA-B2) is the realistic in-silico route, not a ligand-affinity campaign.
