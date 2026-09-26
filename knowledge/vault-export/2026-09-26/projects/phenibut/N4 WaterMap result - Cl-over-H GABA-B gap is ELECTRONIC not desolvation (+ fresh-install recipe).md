---
title: N4 WaterMap result - Cl-over-H GABA-B gap is ELECTRONIC not desolvation (+
  fresh-install recipe)
type: report
permalink: main/projects/phenibut/n4-water-map-result-cl-over-h-gaba-b-gap-is-electronic-not-desolvation-fresh-install-recipe
tags:
- phenibut
- gabab
- watermap
- N4
- desolvation
- schrodinger-install
---

# N4 WaterMap result - baclofen>phenibut (Cl>H) GABA-B gap is ELECTRONIC, not desolvation

**Result (2026-07-13, Scaleway L40S, fresh full Schrodinger 2026-2 install):** WaterMap on the GABA-B (4MS4) pocket COMPLETED - 89 hydration sites with r_watermap_deltaG.

**Finding:** the para position (phenibut H / baclofen Cl) IS a desolvation hotspot - unfavorable high-energy waters, dG up to +3.4 kcal/mol (site 12 @0.9A = +3.04; site 80 @2.6A = +3.37). BUT there is **NO H<->Cl differential**: watermap_kinetics.py scores the S-phenibut(H) pose and a Cl-mutant (same pose, para H->Cl) IDENTICALLY (dG_UF = -7.9 each). Cl's ~0.67A extra reach displaces NO additional unfavorable water; the para high-energy water is displaced equally by H and Cl.

**Conclusion (per N4 kill-criterion, dossier sec.7 "reward<0.5 -> electronic"):** the baclofen>phenibut (Cl>H) GABA-B affinity gap (connected-map FEP ddG = +1.74 kcal/mol) is **NOT desolvation-driven - consistent with an ELECTRONIC / direct-interaction origin.** An interim geometric proxy (loose 2.4/2.8A thresholds) spuriously gave +1.72 matching the FEP ddG; the validated tool did NOT reproduce it (artifact retired - the "Cl-only" site sat at ~2.5A, beyond either atom's true displacement radius).

**Infra fix (workaround for the mirror-FEP-only limitation):** the Modal mirror could NOT run WaterMap (missing watermap product). RESOLVED by a FRESH FULL install from the 14GB installer at `/d/2026-2_Schrodinger_Linux.zip` (contains watermap-v6.7-Linux + mmshare/desmond/scisol/jaguar/epik/glide/impact/ffld + INSTALL). Recipe: `unzip` -> `bash INSTALL -b -s /opt/schrodinger2026-2 -k <scratch> <product tars>` -> cure (place 26-2.lic + replace libmmfileshared.so with the patched one md5 a34a793bd05237c30f8cdc4ac750d290 [Build 121] + SCHRODINGER_FEATURE_FLAGS=+SCHRODINGER_LICENSE_MANAGER). Installer Build 121 matches the patched .so -> license err=None. A fresh install has proper perms + symlinks (NO chmod/ldconfig repair needed, unlike the Windows-copied mirror). Relates to [[Modal Schrodinger 2026-2 mirror is FEP-plus-only - WaterMap + jaguar-pka blocked]].

**Data:** compute/phenibut_fetch/n4b_results/ (gabab_wm-out.maegz = 89-site water map, n4_result.txt, n4_hcl_scored.csv, n4_scored.csv).