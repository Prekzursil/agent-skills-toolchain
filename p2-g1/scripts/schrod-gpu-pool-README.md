# schrod-gpu-pool.sh — one Schrödinger jobserverd per GPU (real single-node multi-GPU)

Run Desmond / BPMD / any JobDJ-based Schrödinger GPU work **across all GPUs on one
node** instead of everything piling on GPU 0.

## The problem it solves

Schrödinger's modern local **`jobserverd` spawns every GPU subjob in its own
environment**, which has no `CUDA_VISIBLE_DEVICES` → all subjobs default to **GPU 0**.
A driver-level `CUDA_VISIBLE_DEVICES` does **not** survive the job server, and the
hosts-file `gpgpu:` entries are ignored (the jobserverd discovers GPUs at runtime;
`jsc hosts list -v` showing `GPGPU:` empty is expected, not a bug). Verified on a
Scaleway 4×H100 box: `-SUBHOST localhost:4` dispatches 4 concurrent BPMD trials but
all run on GPU 0 (and oversubscription throws `simulate/pack_stage` errors).

## The fix (what this script automates)

**One `jobserverd` per GPU, each started with `CUDA_VISIBLE_DEVICES=i`**, then route
each job to server *i* at launch time. The server's subjobs inherit its `CVD=i` → they
run on GPU *i*. Proven: 4 BPMD ligands ran MD concurrently, one per GPU (each ~88%),
with their `mdsim` processes carrying `CUDA_VISIBLE_DEVICES=0,1,2,3`.

Two non-obvious gotchas this script gets right:

- **Don't hand-copy a server's config dir** — `sed`-rewriting or copying the cert files
  breaks client auth (`failed to parse user-cert`). Use `jsc local-server-start` so each
  server generates its own certs.
- **`SCHRODINGER_JOBSERVER_CONFIG_FILE` is a *server* var, not client routing** — setting
  it on a job also throws `failed to parse user-cert`. The client picks its server from the
  **global default** (`jsc local-server-dir --set`, cached in `~/.schrodinger`), so routing
  is done at launch time: `--set` the target GPU's dir, launch, `sleep` to let it connect,
  `--set` back. The job sticks to the server it connected to; launches are serialized
  (~14 s each), jobs then run concurrently.

## Usage

```bash
export SCHRODINGER=/opt/schrodinger2026-2          # licensed + cured install
# (also need SCHRODINGER_FEATURE_FLAGS / the patched libmmfileshared.so in env)

./schrod-gpu-pool.sh start [N]          # one CVD-pinned jobserverd per GPU (default: all)
./schrod-gpu-pool.sh submit <gpu> <cmd...>   # run <cmd> on GPU <gpu>'s server (detached)
./schrod-gpu-pool.sh status             # pool servers + nvidia-smi
./schrod-gpu-pool.sh stop               # stop all pool servers
```

Example — a 4-ligand BPMD ladder across 4 GPUs (see `bpmd_pool_ladder.sh` pattern: write a
per-ligand `_job.sh`, then `submit <gpu> bash _job.sh`):

```bash
./schrod-gpu-pool.sh start 4
for i in 0 1 2 3; do ./schrod-gpu-pool.sh submit $i bash /root/jobs/bpmd_${LIG[$i]}/_job.sh; done
```

`SCHROD_POOL_ROOT` (default `/root/schrod_pool`) and `SCHROD_POOL_BASE_PORT` are overridable.

## When NOT to use it

**FEP+ `multisim -maxjob N`** already spreads legs across GPUs on the shared server
(multisim self-assigns GPUs) — use that for FEP. This pool is for **BPMD and anything
JobDJ-based** that the shared jobserverd would otherwise pin to GPU 0.

*Provenance: cracked + verified 2026-07-13 on the phenibut α2δ BPMD ladder (Scaleway
4×H100). Full mechanism writeup in basic-memory: "Schrodinger multi-GPU on one node —
WORKING recipe".*
