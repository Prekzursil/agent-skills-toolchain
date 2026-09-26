---
title: 'Scaleway Schrodinger fresh-box: local jobserverd ignores hosts-file GPU config
  (4-GPU spread wall)'
type: note
permalink: main/projects/phenibut/scaleway-schrodinger-fresh-box-local-jobserverd-ignores-hosts-file-gpu-config-4-gpu-spread-wall
tags:
- schrodinger
- scaleway
- gpu
- jobserverd
- bpmd
- fep
- compute
- phenibut
- research-report
- SOLVED
---

# Schrödinger multi-GPU on ONE node — CONFIRMED mechanism (research + empirical, 2026-07-13)

Researched two ways (Exa **deep-research-pro** + a 5-agent ultracode Workflow) AND verified empirically on the Scaleway 4×H100 box. This supersedes my earlier "apply the hosts recipe" guess.

## Root cause (empirically CONFIRMED, not inferred)
The modern local **`jobserverd` spawns every GPU subjob in ITS OWN environment**, which has **no `CUDA_VISIBLE_DEVICES`** → all subjobs default to **GPU 0**. Proof: with 4 BPMD drivers each launched `CUDA_VISIBLE_DEVICES=0/1/2/3`, `/proc/<driver>/environ` shows the CVD is set on the driver, but `/proc/<mdsim-subjob>/environ` shows **CVD empty**, and `nvidia-smi` showed GPU0 = 3748 MiB ≈ 4 stacked contexts. **Driver-level CVD does NOT propagate through the shared job server.**

Corroborating (Exa, primary Schrödinger docs): the modern jobserverd **discovers GPUs at runtime via CUDA, not from hosts-file `gpgpu:` entries** — so `jsc hosts list -v` showing `GPGPU:` empty / `Processors: 0` for localhost is **EXPECTED, not a bug**. There is **no `jsc` command to register GPU slots**, and `jsc local-server-start` has **no port/dir flag** (no easy multi-server).

## What actually works
- **FEP+ `multisim -maxjob N`** DOES spread across GPUs (confirmed: the a2d-1 FEP map run8, `scw_fep_dashboard` showed 4 GPUs). multisim self-assigns GPUs to its concurrent subjobs — a different code path than BPMD's JobDJ.
- **BPMD `binding_pose_metadynamics.py -SUBHOST localhost:N`** does **NOT** spread: dispatches N concurrent trials (A=N) but all pile on GPU 0; oversubscription → `simulate/pack_stage` tracebacks + killed trials.
- **To pin BPMD to distinct GPUs** you must start the **jobserverd itself with `CUDA_VISIBLE_DEVICES=i`** → one job server per GPU. No simple `jsc` flag; would need `SCHRODINGER_JOBSERVER_CONFIG_FILE` per-server juggling (undocumented, not pursued — diminishing returns).
- **NVIDIA MPS** shares ONE GPU among processes; it does NOT spread across GPUs — not the tool here.

## Hosts-file facts (from the Workflow, primary docs)
- Search path, **first match wins**: `$SCHRODINGER_HOSTS` → `./schrodinger.hosts` (cwd) → `$HOME/.schrodinger/schrodinger.hosts` → `$SCHRODINGER/schrodinger.hosts`. (On our box none of the first three exist, so my `$SCHRODINGER/schrodinger.hosts` edits WERE the active file — confirming it's the jobserverd that ignores gpgpu, not a wrong-file issue.)
- `processors:` = **CPU cores** (NOT GPU count; default on localhost = all cores); `parallel:` = MPI yes/no flag; `gpgpu: <id>, <desc>` one line per GPU; official multi-GPU examples are all **queue/Slurm** hosts. Desmond manual: `learn.schrodinger.com/public/getting-started/2025-2/.../gpu_run_desmond.htm`.

## Reliable fallback (IN USE for the α2δ BPMD controls)
`-SUBHOST localhost:1`, **sequential ligands**, one GPU — exactly the prior Modal single-A100 protocol → comparable PoseScores, stable, no oversubscription. gabapentin + baclofen controls run this way (~2h).

## Pitfall (mine, 2026-07-13)
`pkill -9 -f desmond` from inline `ssh box "...desmond..."` kills your own SSH session (cmdline contains "desmond") → always run kills from a **script file**.

**Sources:** Exa deep-research-pro `r_01kxdjca…` (Schrödinger jobcontrol Python-API docs, Desmond User Manual 2025-2, Sigma2/OSC HPC guides, NVIDIA MPS docs) + 5-agent Workflow `wf_4db4f600`. Relates to [[schrodinger-cloud-fep-modal]] (per-edge/per-container parallelization), [[schrodinger-fep-on-modal-parallelize-per-edge-not-in-container-multi-gpu]], [[compute-monitor-preference-verbose-accurate-live-eta-user-standing-request]].