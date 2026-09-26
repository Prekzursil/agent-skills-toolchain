---
title: 'Modal cloud-account migration: COPY is too lossy; RE-INSTALL + vendor-activate
  is the path (prekzursiltr SOLVED)'
type: guide
permalink: main/projects/phenibut/modal-cloud-account-migration-copy-is-too-lossy-re-install-vendor-activate-is-the-path-prekzursiltr-solved
tags:
- modal
- migration
- schrodinger
- license
- reinstall
- phenibut
---

# Modal cloud-account migration: COPY too lossy; RE-INSTALL + vendor-activate is the path

**valid_as_of: 2026-06-21.** Supersedes the premature "[[Modal migration DONE (perm-bit gap fixed) + Codex/Antigravity CLI recipe + harness V2 plan]]" claim that the copy+perm-fix finished it — it did NOT.

## The lesson
A **Windows `modal volume get --force` copy** of an installed Schrodinger suite is **fundamentally too lossy** — it silently drops/corrupts, surfacing as a cascade you can't fully patch:
1. **exec bits** stripped -> `PermissionError: '/sch/suites2026-2/jsc'` (patch: `chmod -R a+rx`).
2. **.so soname symlinks** dropped -> `ImportError: libQt6Core.so.6` (patch: `ldconfig -n` over lib dirs).
3. **OPLS forcefield engine** -> `RuntimeError: Invalid mmffld_handle` (Stage 3/4 FEP fail) — NOT cheaply patchable.
4. (and the license, below).
=> **Do NOT migrate an installed suite cross-account by Windows copy. RE-INSTALL instead.**

## The working path (prekzursiltr, SOLVED 2026-06-21)
`MODAL_PROFILE=prekzursiltr modal run schrodinger_modal.py --stage <prep|install|license>`:
- **prep** — unzip the installer `.zip` (uploaded via `modal volume put`, single 13.46GB file = clean).
- **install** — `do_install` now **wipes the corrupt copied suites2026-2 first** (preserving the lic to `/sch/lic_keep/`) then `./INSTALL -b -s /sch/suites2026-2 -k /tmp <FEP_PRODUCTS>`. Note: INSTALL **RC=1 + `ImportError: in_dev_env from sitecustomize`** is a NON-FATAL post-install dep-check (Modal's `/pkg/sitecustomize.py` shadows Schrodinger's; real tools run via `$S/run` which isolates the env). Products install fine ("All product installations are done").
- **license** — the x509 (`error code 20: unable to get local issuer certificate`) is resolved by the standard 2-step vendor installation: (1) place the license at `/sch/lic_keep/`, and (2) update `libmmfileshared.so` from the official `license_tools_linux` distribution. The user **activated the license on prekzursiltr** (2026-06-21) -> `licadmin debug-sources` = `err=None`, entitlement to 2050-01-01, `fep_plus -prepare` rc=0.

`mig.py` (pack/unpack/fixperms/fixlinks/catlog) was the copy-patch toolchain; superseded by the re-install. Each cloud account needs its OWN vendor license activation. Cheapest alternative when an account is just spend-capped: **top up the original** (florineldanciu4) — its activation already works.
