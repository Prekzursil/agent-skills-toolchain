---
title: Genetics SUD re-run 2026-07-13 - only KCTD16 has a GW-sig dependence hit (alcohol
  use disorder)
type: report
permalink: main/projects/phenibut/genetics-sud-re-run-2026-07-13-only-kctd16-has-a-gw-sig-dependence-hit-alcohol-use-disorder
tags:
- phenibut
- genetics
- SUD
- KCTD16
- mendelian-randomization
- dependence
---

# Genetics SUD re-run (2026-07-13): only KCTD16 has a GW-sig dependence hit (alcohol use disorder)

Re-ran the target-gene × **dependence-trait** scan (DR V17/G27) that the earlier cis-MR (`BIOMNI_CAUSAL_MR.md`, essentially null) missed — it tested "substance" with **smoking/drinks-per-week (Liu 2019 GSCAN)**, not OUD/AUD/CUD. Done via **OpenTargets Genetics (credible-set/L2G/coloc) + GWAS Catalog** through ToolUniverse (transparent).

**FINDING:** Among the 6 target genes (GABBR1/2, CACNA2D1/2, KCTD12/16), **ONLY KCTD16** carries a genome-wide-significant dependence association — **alcohol use disorder** (Kranzler 2019 MVP, GCST008258, rs185177474, **p=2e-8**). KCTD16→opioid is **sub-GW** (Gaddis GCST90244557, rs358664, 4e-6 — confirms the earlier temper). GABBR1/2, CACNA2D1/2, KCTD12 = **NO** SUD association (their hits are SCZ/MDD/pain/anthropometric/intelligence).

**CAVEAT — pleiotropy:** the KCTD16 locus (chr5:144.4–144.5 Mb) is highly pleiotropic — insomnia (6e-11) + AUD (2e-8) + opioid (sub-GW) + migraine + educational attainment all cluster there. Mechanistically coherent for phenibut (sleep + dependence both map here, on the GABA-B desensitization subunit) BUT demands coloc + pleiotropy-robust MR before any causal claim.

**CAUSAL LAYER:** the well-powered OUD GWAS (Gaddis GCST90244554, N=320,890) has **0 fine-mapped credible sets** in OpenTargets; OUD top loci map to non-target genes (TRIM28, DENND1A, FTO, DAO). **No L2G/coloc support for any target gene → dependence.** The earlier causal null HOLDS at the dependence-specific layer too.

**ONE rigorous next step:** KCTD16 → AUD (Kranzler) + OUD (Gaddis) **pleiotropy-robust cis-MR + coloc using brain pQTL/sQTL instruments** (Wingo 2025, DR R49), MR-Egger/HEIDI — not the sparse single brain cis-eQTL the earlier run had (1 SNP, underpowered). Dispatchable to Biomni; deferred pending go-ahead.

**Data:** `compute/phenibut_fetch/genetics/GENETICS_SUD_RERUN.md`. Extends the earlier `BIOMNI_CAUSAL_MR.md` (which the DR V17/G27 flagged as panel-limited).