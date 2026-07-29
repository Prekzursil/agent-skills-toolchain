---
name: codex-databricks-fanout
description: Use when fanning out Codex CLI agents onto Databricks - running many parallel Codex/LLM work units on job clusters, scaling past a local RAM ceiling, or deciding between Databricks / local / Modal / RunPod for a large agent fan-out. Carries the measured constraints from a 608-unit production run, a 48-unit auth-research re-prove, and CRCP ops so a session does not re-derive them wrong.
---

# Codex fan-out on Databricks

Everything below was **measured** on workspace `bolt-datascience`
(`costin.ionescu@bolt.eu` / profile DEFAULT). Facts marked MEASURED are not to be
re-litigated from first principles — a session reasoning from scratch about this
gets the binding constraint wrong (see §1).

**Ops expansions (2026-07-20):** implementer batches, harvest footguns, apply/merge
ownership, and “sloppy session” anti-patterns → §10–§14.

## Implementation

The measured constraints in this doc are enforced by executable code under
[`scripts/`](scripts/) (details in [`scripts/README.md`](scripts/README.md)):

- **`scripts/harness/contract.py`** is the AUTHORITATIVE executable RAIL — the frozen config every
  module reads (policy_id, `r5d.2xlarge`, `concurrency=48`, `stagger_s=3.0`, profile, notebook path).
  This SKILL.md is the measured-constraints doc; `contract.py` is the machine copy of the same rail.
- **`scripts/harness/`** is the driver — `build_batch` → `submit` → `poll` → `harvest` (+ `lanes/`).
- **`scripts/batch_runner.py`** is the on-Databricks worker notebook the driver invokes via
  `RAIL["notebook"]`.
- **`scripts/harness/gate.py`** is the STRUCTURAL completeness gate (§6 — sentinel + fenced fields, no
  byte floor by default), mutation-tested in `scripts/tests/test_gate.py`.
- **`scripts/backends/`** is the role-split compute-backend abstraction: `base.py` holds the
  `BuildBackend`/`VerifyBackend` protocols, `databricks.py` adapts the driver above to them, and
  `github_actions.py` reads a repo's real ubuntu+windows+macos matrix verdict. Read
  `github_actions.py`'s module docstring before trusting `all_green` — it records, with executed
  falsifiers, the job-name shapes it CANNOT match and therefore FAILS OPEN on.
- **`scripts/engine/`** is backend-agnostic and reusable: `verify.py` (the one completion-gate impl
  on the `run_E` path), `ceiling.py` (the R9 hard wave ceiling an UNATTENDED/cron fan-out must pass —
  every branch fails closed, and an unknown quota refuses), `sanitize.py` (neutralize a clone's
  auto-loaded agent config; DEPTH-0 only, and NOT execution safety), `tokens.py` (short-lived
  single-repo push token — the node itself gets none), `backlog.py` (allowlisted structured
  issue/PR fields only; free text never drives privileged action).

Unit + mutation tests: `python -m pytest scripts/tests -q`; `backends/` + `engine/` are additionally
held at 100% line+branch by their own CI step. The `scripts/e2e/` round-trips need a live Databricks
workspace and are run manually, never in CI — `run_wave.py` is the only driver that applies the R9
ceiling, because the interactive ones deliberately do not.

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

**Re-prove (auth research):** conc=48, stagger=3.0s, **48 SUCCESS / 0 FAILED /
0 rate_limited**, elapsed **528s** on `r5d.2xlarge`.
Secret scope `codex-harness-prekzursil` / key `auth_json`.

**2026-07-20 re-prove (CRCP):** 15-unit P1+W1+W2 implement batch **15/15 SUCCESS** in
~560s agent time; 5-unit merge **5/5 SUCCESS**; 89-unit web-endgame research submitted at
conc=48 (run `1023601984546724`).

### What is NOT proven (do not overclaim)

- Token refresh dual-write on long multi-hour runs or multi-node shared auth.json — use
  **per-process `CODEX_HOME`** seeded from the secret if either is required.
- Serverless as a Codex host — task-fails (no node install surface).

## 2. Account-level facts (MEASURED)

| Fact | Consequence |
|---|---|
| **Interactive / bare cluster create is DENIED** | `jobs submit` with bare `new_cluster` (no policy) → `PERMISSION_DENIED`. |
| **Job runs WITH the default job-cluster policy ARE permitted** | `policy_id = "0002189219BF8EF3"`. |
| **Policy caps `dbus_per_hour` at 18** | Prefer **`r5d.2xlarge`** (~64 GB, x86_64). |
| **Serverless notebook path is NOT a Codex host** | Do not plan on serverless for this fan-out. |
| Egress to `api.openai.com` is **OPEN** | 401 = reached-and-rejected. |
| Runtime ships **no node**; `apt-get` fails fast | Install node tarball by arch + `npm i -g @openai/codex`. |
| **Arch matters**: `m7gd` = **ARM64**; `r5d` = x86_64 | Branch on `uname -m`. |
| `notebook_output` captures **only** `dbutils.notebook.exit(...)` | print() looks like empty success. |
| Auth from secret scope, never job payload | Scope **`codex-harness-prekzursil`**, key **`auth_json`**. |
| Cluster spin-up ≈ **3–5 min** | Batch many units per node. |

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

CLI: `databricks jobs submit --json @payload.json --no-wait`.

## 3. Batching is mandatory

| Venue | Concurrent Codex | Notes |
|---|---:|---|
| Local Windows (~32 GB) | ~4–24 adaptive | RAM thrash above ~24 |
| Job node `r5d.2xlarge` (~64 GB) | **~48 @ stagger 3s, 0×429** | measured |
| Larger node (if policy allows) | 100–200+ | ceiling is **API rate limit** |

`BATCH_CONCURRENCY` via `spark_env_vars`; cap at unit count.

## 4. Classify units before dispatch

- **Portable (remote OK):** public research, threat-intel, supply-chain, pure coding against a
  **tarball bundle** uploaded to DBFS.
- **Local-only:** live Windows paths, local MCP fleet, browser profile cookies, live process
  state, pin to this box’s CODEX_HOME for write-back.

Remote units must **STOP rather than fabricate** if a Windows path is required. Say so in the
prompt (MEASURED: agents will invent Windows paths otherwise).

## 5. Getting results back

**`databricks fs cp` (DBFS→local) is a SILENT NO-OP in this CLI build.** MEASURED: prints
`SRC -> DEST`, exits 0, writes nothing. Use **`databricks fs cat`** per file.

Upload **to** DBFS with `fs cp --overwrite` still works (host→DBFS). The silent no-op is
**DBFS→local**.

### Harvest footguns (2026-07-20 MEASURED)

1. **Never filter out names starting with `_`** — that drops `__main__.py` and similar.
2. **Directories are not files:** `fs cat` on `fixtures/` / `rails/` / `tests/` fails. List then
   cat leaves; walk recursively.
3. **`fs ls -r` is not a flag** on this CLI — walk with repeated `fs ls`.
4. Prefer a dedicated `harvest_*.py` that uses `fs cat` + local AND-gate.

## 6. Completion is an AND-gate, never an exit code

> **DONE** = artifact exists **AND** ≥1 KB **AND** last 600 **bytes** contain `UNIT-COMPLETE`.

Non-zero exit + valid artifact ⇒ still **DONE**. Exit 0 + no artifact ⇒ **severed stream**.

Windows liveness: `os.kill(pid, 0)` raises **WinError 87** — use `OpenProcess`.

## 7. Choosing the execution model

| Option | When it is right | Watch out |
|---|---|---|
| **Codex CLI on Databricks job runs** | Real Codex agents; scale past local RAM | policy_id; stagger; ChatGPT quota |
| LLM API fan-out (API key) | Raw model calls only | Separate bill; loses agent loop |
| Local adaptive orch | Small residual / local-only | RAM thrash above ~24 |
| Modal / RunPod | True isolation | Confirm spend |

**Default to the policy job-cluster path.**

## 8. Pre-flight checklist

1. `policy_id=0002189219BF8EF3` — never bare `new_cluster`.
2. Node ≤ policy DBU — start with **`r5d.2xlarge`**.
3. Branch install on `uname -m`.
4. Auth via secret scope `codex-harness-prekzursil` / `auth_json`.
5. Batch units; `BATCH_STAGGER_S` **3.0** (raise on 429s).
6. `BATCH_CONCURRENCY` ≤ unit count.
7. Summary via `dbutils.notebook.exit(json.dumps(...))`.
8. Harvest with **`databricks fs cat`**, never `cp` (local direction).
9. Score with C1 AND-gate.
10. 429 cluster ⇒ stagger too tight, not “capacity exceeded”.
11. Leave **local-only** units on Windows.
12. Upload subject source as **tarball** when units must code against a tree (§10).

## 9. Harness paths

| Path | Role |
|---|---|
| `/Users/costin.ionescu@bolt.eu/codex-batch/batch_runner` | Proven notebook |
| `~/scratch/codex-auth-research-fanout/databricks/` | auth-research build/submit/poll/harvest |
| `~/scratch/crcp-e2e-p0-fanout/` | CRCP implement/merge batches (2026-07-20) |
| `~/scratch/crcp-web-account-fanout/` | web-account endgame research (89 units) |
| Secret scope `codex-harness-prekzursil` | `auth_json` |

Related: `workflow-authoring`, `orchestration-patterns`, `cloud-infra-toolchain`,
`rules/common/cross-vendor-dispatch.md`, `rules/common/fan-out-contract.md`.

---

## 10. Research units vs implementer units (do not mix carelessly)

### Research / audit (portable)

- Prompt writes **one** markdown artifact to `/dbfs/.../results/<id>.md`.
- AND-gate on that file only.
- No subject tree required (or optional tiny README bundle).

### Implementer / merge (needs source)

1. Pack a **tarball** of the subject (e.g. `crcp/*.py` + synthesis report) — no secrets, no outbox dumps.
2. Upload to **both**:
   - your run’s `…/crcp-source.tar.gz`
   - **`dbfs:/tmp/codex-batch/harness-bundle.tar.gz`** — batch_runner often hardcodes this path
3. Prompt: read-only unpack under `/local_disk0/codexwork/bundle`.
4. Deliverables: full module files under `result_dir` **plus** report ending `UNIT-COMPLETE: <id>`.
5. Prefer **full file replacements**, not fragile diffs (apply is copy-by-name).

### Parallel implementers MUST have exclusive file ownership

If two agents both rewrite `live_bridge.py`, last writer wins and wiring is lost (MEASURED:
P0 spool-wire overwritten by P1 HTTP-auth rewrite).

| Good | Bad |
|------|-----|
| Unit A owns `live_bridge.py` only | Three units each “patch live_bridge” |
| Unit B owns `write_path.py` only | Shared free-for-all |
| Unit C owns `tests/test_*.py` only | Same test file from two units |

For integration after parallel modules exist, run a **merge wave** with disjoint ownership
(e.g. A=spool wire, B=SSE wire, C=health, D=`__main__`, E=tests).

## 11. Apply harvested code without breaking Windows

1. **Apply order:** older wave first, newer wave overwrites on name collision when intentional.
2. **Never hardcode** `/local_disk0/codexwork/bundle` as the only import root in runners that
   must work on Windows — detect `tools/crcp` relative to the script, fall back to env
   `CRCP_SOURCE_ROOT`, then remote path (MEASURED: `run_merge_tests.py` failed until fixed).
3. **SQLite on Windows:** prefer `journal_mode=DELETE` (or checkpoint + ignore cleanup errors).
   WAL leaves handles that break `TemporaryDirectory` cleanup.
4. **Smoke after apply:** import every new module; run contract tests; one live probe if local.

## 12. Codex / ChatGPT auth planes (do not confuse them)

| Plane | Store | Role | Endgame? |
|-------|--------|------|----------|
| Codex OAuth | `~/.codex/auth.json` access_token | API consumer for Codex + CRCP backend-api | **No** — expires |
| ChatGPT **web** account | Browser / Desktop session cookies + device ids | Same human account on chatgpt.com | **Yes** — durable owner plane |

CRCP list/fetch/send via Codex tokens is a **temporary rail**. Design research and long-lived
control planes toward **web session primary**, Codex AT secondary. Fan-outs that explore
“web endgame + plugins + Bolt/Databricks surfaces” belong in
`scratch/crcp-web-account-fanout/` (89-unit catalog pattern).

Never upload browser cookies or full JWTs to DBFS/results.

## 13. Local loopback + proxy (CRCP / agent-mail)

MEASURED: system proxy (Fiddler) returns **502** for `http://127.0.0.1:8812` and can mask
health. Always:

- `NO_PROXY=127.0.0.1,localhost` (and clear `HTTP_PROXY`/`HTTPS_PROXY` for probes)
- Python: `urllib.request.build_opener(urllib.request.ProxyHandler({}))` for loopback health
- Prefer `curl.exe --noproxy "*"` over PowerShell `Invoke-WebRequest` when Fiddler is on

Agent-mail supervisor logon task must actually **run**; “Ready” scheduled task with never-run
LastRunTime is not a live bus.

## 14. Sloppy-session anti-patterns (ban these)

Sessions that “look busy” but produce nothing usually do one of:

1. **Assume bare `new_cluster` works** → PERMISSION_DENIED. Always policy_id.
2. **Harvest with `fs cp`** → empty local tree, claim success. Use `fs cat`.
3. **Trust exit code alone** → severed streams. AND-gate on `UNIT-COMPLETE`.
4. **Fire 180 units at t=0** → synchronized 429. Stagger ≥3s.
5. **Inline 30KB prompts on Windows CreateProcess** → os error 206. Prompt-by-file / batch JSON.
6. **Parallel implementers without ownership** → silent last-writer-wins.
7. **Hardcode job-node paths into repo runners** → green on DBX, red on Windows.
8. **Filter harvest `name.startswith('_')`** → drop `__main__.py`.
9. **Treat Codex token as durable web login** → wrong endgame; design for web plane.
10. **Skip post-apply smoke** → import/API skew (e.g. `_auth_mtime` after CredentialSnapshot).
11. **Poll with default 10m timeout on multi-hour jobs** → false failure; longrun / background poll.
12. **Put secrets in batch.json or DBFS results** → rotate, never just delete.

## 15. Minimal operator recipe (copy)

```powershell
# 1) Build batch.json (units with id, prompt, artifact path under /dbfs/.../results)
# 2) Upload
databricks fs mkdirs dbfs:/tmp/my-fanout/results
databricks fs cp batch.json dbfs:/tmp/my-fanout/batch.json --overwrite
# optional source bundle:
databricks fs cp crcp-source.tar.gz dbfs:/tmp/codex-batch/harness-bundle.tar.gz --overwrite

# 3) jobs submit --json @submit_payload.json --no-wait   (policy + r5d.2xlarge + stagger)

# 4) Poll
databricks jobs get-run <run_id> -o json

# 5) Harvest (NEVER fs cp for download)
databricks fs ls dbfs:/tmp/my-fanout/results
databricks fs cat dbfs:/tmp/my-fanout/results/<unit>.md > results/<unit>.md

# 6) AND-gate + apply + smoke imports/tests
```

Model default for batch_runner units: **`gpt-5.6-sol`** (as configured in notebook).

## 16. Evidence anchors (this workspace)

| Run / date | What |
|------------|------|
| 608-unit mega-audit | Scale + stagger necessity |
| 343617464274709 | 48/48 @ stagger 3s |
| 982136530224451 | CRCP P0 implement 3 units |
| 690432742789715 | CRCP P1+W1+W2 15/15 SUCCESS ~560s |
| 961988947593804 | CRCP merge wiring 5/5 |
| 1023601984546724 | Web-account endgame research 89 units @ c48 |
