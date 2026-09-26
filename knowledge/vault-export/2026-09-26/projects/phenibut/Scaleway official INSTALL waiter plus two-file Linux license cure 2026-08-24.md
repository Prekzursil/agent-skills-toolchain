---
title: Scaleway official INSTALL waiter plus two-file Linux license cure 2026-08-24
type: guide
permalink: main/projects/phenibut/scaleway-official-install-waiter-plus-two-file-linux-license-cure-2026-08-24
tags:
- phenibut
- scaleway
- fep
- jaguar
- license
- libmmfileshared
---

valid_as_of: 2026-08-24

## Two-file Linux cure (do this on EVERY fresh Linux install)
Same overlay as `26-2-linux_extract_to_install_dir.tar.gz` / `D:\schrodinger\license_tools_linux`:
1. `licenses/26-2.lic`
2. `internal/lib/libmmfileshared.so` (vendor license_tools build, NOT a verifier bypass)
Then overwrite **EVERY** `libmmfileshared.so` under `$SCHRODINGER` — mmshare ships its own unpatched copy; patching one file leaves jobs dying. Gate on `licadmin debug-sources` → `err=None`. Enable `SCHRODINGER_FEATURE_FLAGS=+SCHRODINGER_LICENSE_MANAGER`.

## Box
`gpuok` `phenibut-a2d-fep` `51.159.180.9` H100-SXM-4. Official zip scp already in flight (do NOT start a second). Waiter PID 14680 `WAIT_ZIP` expect 14448198385. INSTALL target `/mnt/persist/suites-fresh` with FEP_PRODUCTS **including jaguar-v13.2 in one pass**, then the two-file overlay, then launch `launch_a2d_fep.sh` / `launch_a2d_jaguar.sh` (both now refuse the copy-suite).

Cure artifacts on persist: `/mnt/persist/26-2-linux_extract_to_install_dir.tar.gz`, `/mnt/persist/lic/libmmfileshared.so` (1080144), `/mnt/persist/lic/26-2.lic` (21376).

Pause not terminate. Do not overwrite authorized_keys. Do not mix ATM/Vina/FEP. α2δ ATM −0.805 is wrong-signed vs Zvejniece +1.13.
