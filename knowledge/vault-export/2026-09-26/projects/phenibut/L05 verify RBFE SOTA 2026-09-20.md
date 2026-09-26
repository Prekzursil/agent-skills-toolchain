---
title: L05 verify RBFE SOTA 2026-09-20
type: report
permalink: main/projects/phenibut/l05-verify-rbfe-sota-2026-09-20
tags:
- sota-lanes
- verification
- rbfe
- L05
- atm
- openfe
---

# L05 verification — adversarial check of [[L05_rbfe_sota]]

- [fact] All 13 sampled citations in L05_rbfe_sota resolved and matched on volume, issue, pages, year, author, title (16 fetches across 6 mechanically independent routes: PMC full text, Crossref REST, NCBI E-utilities REST, arXiv, LIVECoM redirect target, ReadTheDocs, Zenodo).
- [fact] Every load-bearing number of the OpenFE 2026 assessment (Baumann et al., JCIM 66(11):6429-6452, DOI 10.1021/acs.jcim.6c00089, PMC13555741) is verbatim in the PMC full text: edgewise MUE 1.05 [1.00, 1.10] kcal/mol on 1181 public edges; MBAR off-diagonal overlap > 0.03 convergence gate; analytical MBAR estimates "tend to be overoptimistic"; triplicate runs; public repeat consistency 83.5% -> 88.6% after the overlap filter.
- [fact] ATS 2025 (Gallicchio, JCIM 65(7):3706-3714, DOI 10.1021/acs.jcim.5c00207, PMID 40136079) confirmed twice independently (Crossref + NCBI E-utilities esummary, PMC12004517).
- [decision] Verdict: CONFIRMED. The artifact is substantive (~1400 words, 5 concrete recommendations, honest inline UNVERIFIED flags) and every sampled citation held.
- [fact] SAMPL9: only the host-guest challenge (Amezcua, Setiadi and Mobley, PCCP 2024, DOI 10.1039/d3cp05111k) is claimed and confirmed via Crossref; the GSK3beta protein-ligand item is marked UNVERIFIED in the artifact and claims nothing — honest posture verified.

## Claim-by-claim results

### ATM lineage
- Zariquiey 2023 validation, JCIM 63(8):2438-2444, DOI 10.1021/acs.jcim.3c00178 — CONFIRMED via Crossref (Validation of the Alchemical Transfer Method for the Estimation of Relative Binding Affinities of Molecular Series).
- Azimi and Gallicchio 2024, JPCB 128(44):10841-10852, DOI 10.1021/acs.jpcb.4c05732 — CONFIRMED via Crossref; title literally: Binding Selectivity Analysis from Alchemical Receptor Hopping and Swapping Free Energy Calculations (the receptor hopping/swapping characterization is in the title itself).
- Gallicchio 2025 ATS, JCIM 65(7):3706-3714, DOI 10.1021/acs.jcim.5c00207, PMID 40136079 — CONFIRMED twice, mechanically independent (Crossref + E-utilities). Direct pubmed.ncbi.nlm.nih.gov fetch hit a transient socket hang-up; recovered via E-utilities; not a dead URL.

### Benchmark norm (most load-bearing)
- Baumann et al. 2026 OpenFE assessment — all numbers verbatim in source, no inflation (see observations above). Also confirmed: Schindler et al. 2020, JCIM 60(11):5457-5474, DOI 10.1021/acs.jcim.0c00900 via Crossref.
- Note: Baumann print 2026-06-08, online 2026-05-21; the 66(11) issue assignment is real per Crossref.

### Analysis best practice
- Mey et al. 2020 LIVECoM 2(1):18378, DOI 10.33011/livecoms.2.1.18378 — CONFIRMED via the redirect target of the cited URL (301 to index.php/livecoms/article/view/v2i1e18378; same article, same DOI). Cited URL redirects; resolves correctly; not dead.
- pymbar 4 docs — CONFIRMED: MBAR estimation, automatic equilibration detection, correlated-timeseries subsampling documented at pymbar.readthedocs.io/en/master. Minor: landing page does not spell out "statistical inefficiency" though the feature it names is documented.
- BU-MBAR, arXiv:2609.03541, 3 Sep 2026, Muller/Alesiani/Christiansen, github.com/nec-research/BU-MBAR — CONFIRMED. Nuance: BU = binned-to-unbinned (hybrid binned WHAM / unbinned MBAR); the artifact paraphrase (WHAM-seeded Newton solve, GPU code) is compatible and makes no contrary claim.

### Additions 1 to 5 (recommendations real)
1. pymbar 4 stack + Chodera 2016 auto-equilibration JCTC 12(4):1799-1805, DOI 10.1021/acs.jctc.5b00784 — CONFIRMED via Crossref (A Simple Method for Automated Equilibration Detection in Molecular Simulations).
2. CAR: Yao et al. 2024 JCTC DOI 10.1021/acs.jctc.4c00939 — CONFIRMED via Crossref (Convergence-Adaptive Roundtrip Method Enables Rapid and Accurate FEP Calculations, 2024-09-05); ALCHEMD JCTC 22(1):750-762, DOI 10.1021/acs.jctc.5c01857 — CONFIRMED via Crossref (print 2026-01-13, online 2025-12-31; 2026 citation matches print).
3. OpenFE convergence gate + 83.5 -> 88.6 percent figures — CONFIRMED verbatim from PMC full text.
4. NNP correction: Zariquiey et al. 2024 JCIM 64(5):1481-1485, DOI 10.1021/acs.jcim.3c02031 — CONFIRMED via Crossref (Enhancing Protein-Ligand Binding Affinity Predictions Using Neural Network Potentials).
5. Zenodo concept DOI 10.5281/zenodo.22819600 EXISTS — program deposit, title: Data and code for two studies of the phenibut GABA-B axis, author Andrei Mihai Visalon, v3, concept DOI confirmed in record notes.

## Dead URLs
None. One 301 redirect (LIVECoM, resolves correctly); one transient PubMed socket hang-up (recovered via E-utilities); the artifact already discloses its pubs.acs.org / europepmc 403 blocks and sampl.sams.org certificate failure.

## Fabricated or contradicted claims
None found.

## Residual limits
- SAMPL9 GSK3beta item not independently verified, by design (artifact marks it UNVERIFIED and claims nothing).
- PMIDs 36994153 / 37042797 of the Zariquiey 2023 entry not individually re-resolved (paper itself Crossref-confirmed).
- FEP+ ranking-parity phrasing checked only indirectly (overlapping-edge MUE 0.99 vs 1.05), not against an explicit parity sentence.

## Transport caveat (verification-lane provenance)
The Bash tool on this box returned empty output for every call this session (including a trivial echo probe) and ENAMETOOLONG on any multi-KB payload, and the HexStrike MCP was Not Connected — so this report could not be written to D:/Research/projects/phenibut/docs/sota_lanes_2026-09-20/ as intended. It is stored here in the vault instead; the parent should copy it to the project folder if the exact path matters.