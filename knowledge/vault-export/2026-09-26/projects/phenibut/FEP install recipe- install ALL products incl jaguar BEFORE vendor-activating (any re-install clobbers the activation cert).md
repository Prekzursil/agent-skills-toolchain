---
title: 'FEP install recipe: install ALL products incl jaguar BEFORE vendor-activating
  (any re-install clobbers the activation cert)'
type: guide
permalink: main/projects/phenibut/fep-install-recipe-install-all-products-incl-jaguar-before-vendor-activating-any-re-install-clobbers-the-activation-cert
tags:
- schrodinger
- modal
- license
- jaguar
- fep
- install-order
- gotcha
- phenibut
---

# FEP install recipe: install ALL products (incl jaguar) BEFORE activating

**valid_as_of: 2026-06-21.** Two confirmed gotchas finishing the prekzursiltr re-install (extends [[Modal cloud-account migration: COPY is too lossy; RE-INSTALL + vendor-activate is the path (prekzursiltr SOLVED)]]).

## Gotcha 1 — the minimal FEP product set MUST include jaguar
`fep_plus` Stage 3 runs `generate_custom_charges.py` → **`RuntimeError: Jaguar is not installed`** → rc=1, no `.fmp`, run finishes in ~1 min (no MD). The FEP_PRODUCTS list in `schrodinger_modal.py` (mmshare/desmond/scisol/ffld/glide/epik) was missing it. **Add `jaguar-v13.2-Linux-x86_64.tar.gz`.**

## Gotcha 2 (the painful one) — order: install EVERYTHING, THEN activate
Vendor license activation installs/fixes a **cert** in the suite (mmshare/internal CA). **Any subsequent `./INSTALL` of a product pulls in a fresh mmshare re-install as an auto-dependency, which OVERWRITES that cert** → `licadmin debug-sources` flips from `err=None` back to **`err='x509 verification failed error 20: unable to get local issuer certificate'`** → `(SLM) -2: Could not check out a license for mmlibs`.
- PROOF: FEP `batvelh17` (pre-jaguar) reached the jaguar stage = license OK; after `add_jaguar` (which re-installed mmshare), `bcv0cs2m3` x509-fails; license re-check `bc5klsn9n` confirms err=x509.
- **CORRECT ORDER:** `prep` → `install` (ALL products incl jaguar in one FEP_PRODUCTS list) → place `.lic` and apply vendor `libmmfileshared.so` update → `fep`. Never add a product after activation without reapplying the library update.
- If an x509 error recurs after adding products or re-installing, simply re-apply the vendor `libmmfileshared.so` update after the suite installation is final.

`fep_sar.py` env/image were NOT the problem (it validated fine in `batvelh17`); both run_imgs install ca-certificates.
