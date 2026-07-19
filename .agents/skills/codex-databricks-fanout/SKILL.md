---
name: codex-databricks-fanout
description: Use when fanning out Codex CLI agents onto Databricks — running many parallel Codex/LLM work units on job clusters, scaling past a local RAM ceiling, or deciding between Databricks / local / Modal / RunPod for a large agent fan-out. Carries the measured constraints from a 608-unit production run + a 48-unit auth-research re-prove so a session does not re-derive them wrong.
---

# Codex fan-out on Databricks

Everything below was **measured on 2026-07-19** on workspace `bolt-datascience`
(`costin.ionescu@bolt.eu` / profile DEFAULT). Facts marked MEASURED are not to be
re-litigated from first principles — a session reasoning from scratch about this
gets the binding constraint wrong (see §1).

## 1. The constraint everyone guesses wrong

A session planning this will typically assert:

> *"Databricks is Spark/Jobs, not Codex CLI hosts. Codex OAuth + auth.json must NOT fan out to N
> workers — that's the dual-writer failure mode."*

**Both halves are wrong as stated.**

**Databricks job nodes host Codex CLI fine.** The runtime is ordinary Linux. You install
node + `@openai/codex` (or the official tarball) and run `codex exec`. It is not
*Spark-native*, but "not a Codex host" is false — **608 units** (mega-audit) and a
**48-unit auth-research re-prove (run 343617464274709)** completed this way.

**One shared `auth.json` served 180 concurrent Codex processes on one node with zero auth
corruption.** MEASURED, batch-01. Of 180, exactly 120 failed and **every single failure was
`429 Too Many Requests — exceeded retry limit`**, all dying in a 37–41s band. They fired at t=0,
hit the same rate window, burned codex's internal retries together, and gave up together. The 60
survivors were pristine. The node still had **228.9 GB free**.

That is a **thundering herd against the API rate limit**, not a capacity problem and not an auth
race. The real binding constraint at high fan-out is **arrival rate**, and the fix is a stagger:

```python
stagger = float(os.environ.get("BATCH_STAGGER_S", "3.0"))   # seconds between launches
with cf.ThreadPoolExecutor(max_workers=conc) as ex:
    for i, u in enumerate(units):
        ex.submit(run_unit, u, i * stagger)   # rolling arrival, not a burst
```

**Re-prove (auth research, same day):** conc=48, stagger=3.0s, **48 SUCCESS / 0 FAILED /
0 rate_limited**, elapsed **528s** on `r5d.2xlarge` (66.7 GB host, 26.2 GB free at end).
Secret scope `codex-harness-prekzursil` / key `auth_json`.

### What is NOT proven (do not overclaim)

The 180-way and 48-way tests shared one auth.json among **readers** on **one node** over a
**short** window. Two cases remain **UNVERIFIED** and are where a genuine dual-writer race would live:

- a run long enough that a **token refresh fires mid-run** and two processes write back concurrently
  (the Claude-side analogue is real: sporadic 401s from a refresh-race between instances sharing
  `.credentials.json`);
- the same auth.json used across **multiple nodes** at once.

If you need either, give each process its **own `CODEX_HOME`** seeded from the secret, so no two
processes ever write the same file. That is the correct mitigation — not avoiding fan-out.
Settling experiment: run >2h at concurrency ≥50 and watch for a 401 cluster after the refresh window.

## 2. Account-level facts (MEASURED)

| Fact | Consequence |
|---|---|
| **Interactive / bare cluster create is DENIED** | `dbx_cluster_create` and `jobs submit` with bare `new_cluster` (no policy) → `PERMISSION_DENIED: You are not authorized to create clusters` (MEASURED run 744811610636848). |
| **Job runs WITH the default job-cluster policy ARE permitted** | `jobs submit` + `new_cluster.policy_id = "0002189219BF8EF3"` ("default job cluster policy") works. Do **not** stop at "cannot create clusters". |
| **Policy caps `dbus_per_hour` at 18** | Huge nodes (`r6id.8xlarge` / 256 GB class) fail policy even when submit is otherwise valid. Prefer **`r5d.2xlarge`** (~64 GB, x86_64, local NVMe) for ~40–80 concurrent Codex. |
| **Serverless notebook path is NOT a Codex host** | `environments` / serverless submit may accept the run then **task-fail** (no install surface for node/codex). Do not plan on serverless for this fan-out. |
| Egress to `api.openai.com` is **OPEN** (401 = reached-and-rejected) | Codex on a worker can reach the API. |
| Runtime ships **no node**; `apt-get` fails fast | Install node tarball by arch + `npm i -g @openai/codex` (batch_runner does this). |
| **Arch matters**: `m7gd` = **ARM64**; `r5d`/`m5d`/`r6i` = x86_64 | Branch on `uname -m`. |
| `notebook_output` captures **only** `dbutils.notebook.exit(...)` | A `print()`ing notebook returns EMPTY on success — looks like failure. |
| Auth from secret scope, never job payload | Scope **`codex-harness-prekzursil`**, key **`auth_json`**. |
| Cluster spin-up ≈ **3–5 min** | Batch many units per node. |
| `clusters list` is **workspace-wide** | This user can **see** ~30+ clusters (including others' JOB clusters). **List ≠ attach/control.** |

### Required submit shape (copy this)

```json
{
  "run_name": "codex-fanout-…",
  "tasks": [{
    "task_key": "fanout",
    "notebook_task": {
      "notebook_path": "/Users/costin.ionescu@bolt.eu/codex-batch/batch_runner",
      "base_parameters": {
        "batch_json": "/dbfs/tmp/…/batch.json",
        "result_dir": "/dbfs/tmp/…/results",
        "scope": "codex-harness-prekzursil",
        "stagger_s": "3.0"
      },
      "source": "WORKSPACE"
    },
    "new_cluster": {
      "policy_id": "0002189219BF8EF3",
      "spark_version": "15.4.x-scala2.12",
      "node_type_id": "r5d.2xlarge",
      "driver_node_type_id": "r5d.2xlarge",
      "num_workers": 0,
      "spark_conf": {
        "spark.master": "local[*]",
        "spark.databricks.cluster.profile": "singleNode"
      },
      "custom_tags": {
        "ResourceClass": "SingleNode",
        "CostCenter": "ENG-DATA-PLATFORM"
      },
      "aws_attributes": {
        "availability": "ON_DEMAND",
        "zone_id": "auto",
        "instance_profile_arn": "arn:aws:iam::287845475429:instance-profile/datascience-instance-profile"
      },
      "spark_env_vars": {
        "BATCH_CONCURRENCY": "48",
        "BATCH_STAGGER_S": "3.0",
        "JFROG_USERNAME": "{{secrets/jfrog-artifactory-secrets/artifactory-username}}",
        "JFROG_PASSWORD": "{{secrets/jfrog-artifactory-secrets/artifactory-password}}"
      },
      "data_security_mode": "LEGACY_SINGLE_USER_STANDARD",
      "enable_elastic_disk": true,
      "cluster_log_conf": {
        "s3": {
          "destination": "s3://bolt-databricks-logs/cluster-logs/bolt-datascience",
          "region": "eu-central-1"
        }
      }
    }
  }]
}
```

CLI: `databricks jobs submit --json @payload.json --no-wait` (not a permanent job create).

## 3. Batching is mandatory

At multi-minute spin-up, one unit per job run wastes wall clock. Batch many units onto one node
and stagger starts.

Sizing (MEASURED this machine + workspace):

| Venue | Concurrent Codex | Notes |
|---|---:|---|
| Local Windows (31.6 GB) | ~4–24 adaptive | RAM thrash; use `adaptive_slots.py` |
| Job node `r5d.2xlarge` (~64 GB) | **~48 @ stagger 3s, 0×429** | auth-research re-prove |
| Larger node (when policy allows) | 100–200+ | ceiling is **API rate limit**, not RAM |

Set `BATCH_CONCURRENCY` via `spark_env_vars` (batch_runner reads it; `0` = auto from free RAM).

## 4. Classify units before dispatch

- **Portable** (safe remote): public source research, threat-intel, supply-chain, playbooks, any unit
  that can use GitHub/`raw.githubusercontent.com` + web.
- **Local-only**: live Windows paths, local MCP fleet, live process state, CODEX_HOME pin on this box
  (examples: `B09-windows-path-sandbox`, `E08-integration-claude-grok`).

Classify in the catalog. Remote units must **STOP rather than fabricate** if a Windows path is required.

## 5. Getting results back

**`databricks fs cp` (DBFS→local) is a SILENT NO-OP in this CLI build.** MEASURED: prints
`SRC -> DEST`, exits 0, writes nothing. Use **`databricks fs cat`** per file.

Harness: `scratch/codex-auth-research-fanout/databricks/harvest.py` (and siblings `build_batch.py`,
`submit_fanout.py`, `poll_run.py`).

## 6. Completion is an AND-gate, never an exit code

Score with the shared predicate (`completion_predicate.py` / `hooks/_shared/completion.py`):

> **DONE** = artifact exists **AND** ≥1 KB **AND** last 600 **bytes** contain `UNIT-COMPLETE`.

Non-zero exit + valid artifact ⇒ still **DONE**. Exit 0 + no artifact ⇒ **severed stream**.
Failed detector ⇒ **UNKNOWN**, never FAILED.

Windows liveness note: `os.kill(pid, 0)` raises **WinError 87** — use `OpenProcess` (fixed in
`completion_predicate.process_alive`).

## 7. Choosing the execution model

| Option | When it is right | Watch out |
|---|---|---|
| **Codex CLI on Databricks job runs** (proven) | Real Codex agents; scale past local RAM | Use **policy_id**; stagger; ChatGPT quota |
| LLM API fan-out (API key) | Raw model calls only | Separate bill; loses agent loop |
| Local adaptive orch | Small residual / local-only units | RAM thrash above ~24 |
| Modal / RunPod containers | True isolation per agent | Confirm spend first |

**Default to the policy job-cluster path** unless a requirement rules it out.

## 8. Pre-flight checklist

1. `databricks jobs submit` with **`policy_id=0002189219BF8EF3`** — never bare `new_cluster`, never
   interactive `clusters create`.
2. Node ≤ policy DBU cap — start with **`r5d.2xlarge`** (x86_64).
3. Branch install on `uname -m`.
4. Auth via secret scope `codex-harness-prekzursil` / `auth_json` (not batch JSON).
5. Batch units; `BATCH_STAGGER_S` default **3.0** (raise on 429s).
6. `BATCH_CONCURRENCY` ≤ unit count (more workers than units is waste).
7. Return summary via `dbutils.notebook.exit(json.dumps(...))`.
8. Harvest with **`databricks fs cat`**, never `cp`.
9. Score with C1 AND-gate; Windows `process_alive` must use OpenProcess.
10. Treat a 429 cluster as "stagger too tight", not "capacity exceeded".
11. Leave **local-only** units on the Windows box.

## 9. Harness paths (this workspace)

| Path | Role |
|---|---|
| `/Users/costin.ionescu@bolt.eu/codex-batch/batch_runner` | Proven notebook |
| `~/scratch/codex-auth-research-fanout/databricks/` | build / submit / poll / harvest |
| `~/scratch/codex-auth-research-fanout/adaptive_slots.py` | Local RAM-aware concurrency |
| `~/scratch/codex-auth-research-fanout/completion_predicate.py` | C1 AND-gate + Windows liveness |
| Secret scope `codex-harness-prekzursil` | `auth_json` |

Related: `workflow-authoring`, `cloud-infra-toolchain`, `rules/common/cross-vendor-dispatch.md`.
