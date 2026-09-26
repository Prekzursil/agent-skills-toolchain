---
title: 'CORRECTION: the activated Schrodinger .lic is PORTABLE across Modal accounts
  (no per-account re-activation)'
type: note
permalink: main/projects/phenibut/correction-the-activated-schrodinger-.lic-is-portable-across-modal-accounts-no-per-account-re-activation
tags:
- schrodinger
- license
- modal
- migration
- correction
- phenibut
---

# CORRECTION (2026-06-21): the activated .lic is PORTABLE — no per-account re-activation

Earlier notes said the Schrodinger license needs **vendor re-activation per Modal account** (prekzursiltr x509-failed until the user activated). That is now **superseded**: once the user did the vendor activation (on prekzursiltr), the resulting **activated `26-2.lic`** (saved locally at `D:\Research\_assets\schrodinger-licenses\26-2.lic`) is **self-validating and portable**.

Proof: on the 3rd fresh account **mariusvisalon70**, after re-install + uploading that local `.lic` to `/sch/lic_keep/`, the license_test returned **`err=None`** (entitlement startDate 2026-05-02 / endDate 2050-01-01) and `fep_plus -prepare` rc=0 — **with NO user activation step**. The machineId differs from prekzursiltr's but the entitlement still validates (machineId=None → not machine-locked).

## Updated migration recipe (simpler)
New Modal account = `modal volume create schrodinger` → upload `.zip` → `prep` → `install` (FEP_PRODUCTS incl jaguar, one pass) → **upload the activated `D:\Research\_assets\schrodinger-licenses\26-2.lic` to `/sch/lic_keep/`** → `license` validates immediately. NO vendor re-activation. Supersedes the per-account-activation claim in [[FEP install recipe: install ALL products incl jaguar BEFORE vendor-activating (any re-install clobbers the activation cert)]] and [[Migration to mariusvisalon70 (3rd Modal account) — in progress 2026-06-21]].

Both connected-map FEP runs now LAUNCHED on mariusvisalon70 L40S: `a2d_connected` (fep_pv_a2d) + `sar_known_connected` (fep_pv_known, the +6.09 validation core).
