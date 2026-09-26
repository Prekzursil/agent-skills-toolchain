---
title: Scaleway a2d FEP copy-loss replay and live Jaguar 2026-08-24
type: guide
permalink: main/projects/phenibut/scaleway-a2d-fep-copy-loss-replay-and-live-jaguar-2026-08-24
tags:
- phenibut
- scaleway
- fep
- jaguar
- mmffld
- copy-loss
- basic-memory
---

valid_as_of: 2026-08-25
supersedes: the 2026-08-24 live snapshot in this same note

## Hook vs rule (owner asked)
- **Rule (mandatory by contract):** pull basic-memory at session start / after compaction / when prior work is in play; write durable facts. Vault does NOT auto-load.
- **Grok enforcement:** there is NO SessionStart gate that blocks tools until a memory pull. Claude PreCompact can checkpoint; Grok does not. Treat pull+write as mandatory anyway.

## Box (measured 2026-08-24 21:03 UTC; still the live target on 2026-08-25)
- Profile `gpuok` (Access Key prefix SCW13YV). Server `phenibut-a2d-fep` id `0d9930a8-5ec4-41a2-9f93-05eebf6b44e0` IP **51.159.180.9** fr-par-2 **H100-SXM-4-80G** EUR 12.771/h.
- Persist `e8882044-a45f-4d4a-9388-32c45c5a2488` mounted `/mnt/persist` (~27 GB used).
- SSH: never `>` overwrite `authorized_keys` (did that once; reboot restored org keys). MPI key APPEND only.

## FEP+ from sch_local.tgz COPY — REFUTED (replay of 2026-06-21 lesson)
Same cascade as [[Modal cloud-account migration: COPY is too lossy; RE-INSTALL + vendor-activate is the path (prekzursiltr SOLVED)]]:
1. exec bits stripped (chmod patched)
2. .so soname symlinks dropped (script patched)
3. **`RuntimeError: Invalid mmffld_handle`** in generate_custom_charges after Jaguar HF ESP. Graph DID build: **9 edges**, similarity 0.458, includes pregabalin↔gabapentin and baclofen↔R_phenibut. Then died. **Do not patch the copy.**

Hosts file ignored (`IGNORE_SCHRODINGER_HOSTS`). JobDJ localhost Max:1, no gpgpu field.

## Jaguar on the copy — NOT a result
Triad launched; jobs exited ~30s (`jexec` rc 3). Not a real SCF. Copy tree is broken for production Jaguar too.

## Correct path (in flight)
Official `2026-2_Schrodinger_Linux.zip` (14.45 GB) uploading to `/mnt/persist/` (measured 675 MB at 21:03 UTC). Then:
`./INSTALL -b -s /mnt/persist/suites-fresh -k /tmp` with FEP_PRODUCTS **including jaguar-v13.2 in ONE pass**, then `.lic` + vendor `libmmfileshared.so`. Never INSTALL after activate. See [[FEP install recipe: install ALL products incl jaguar BEFORE vendor-activating (any re-install clobbers the activation cert)]].

## Do not
- Mix Vina / ATM / FEP numbers
- Two-target novelty from α2δ ATM −0.805 (wrong sign vs Zvejniece +1.13)
- Terminate this box (pause, not terminate)
- Grind chmod/symlink on the copy suite
