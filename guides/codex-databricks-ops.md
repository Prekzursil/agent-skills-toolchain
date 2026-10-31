---
title: codex-databricks-ops
type: note
permalink: dqverify-repo-20261013/guides/codex-databricks-ops
---

# Codex on Databricks — operator playbook (no sloppy sessions)

**Audience:** any agent session that needs to run many Codex units fast without re-deriving
broken recipes. **Canonical skill:** `.agents/skills/codex-databricks-fanout/SKILL.md`
(also mirrored under `~/.agents/skills/codex-databricks-fanout/`).

**Rules:** `rules/common/cross-vendor-dispatch.md` §9 · `rules/common/fan-out-contract.md` §C.

## Why this guide exists

Sloppy sessions repeatedly:

- try bare cluster create → DENIED  
- harvest with `fs cp` → empty tree, false success  
- trust exit codes → severed streams  
- parallel-edit the same file → last writer wins  
- treat Codex OAuth as durable ChatGPT web login  

This document is the short ops path. The skill has measured numbers and the full submit JSON.

## 60-second recipe

```text
1. batch.json  → units[] with id, prompt, artifact=/dbfs/tmp/<run>/results/<id>.md
2. pack optional source.tar.gz → dbfs:/tmp/codex-batch/harness-bundle.tar.gz + run path
3. jobs submit --json @payload --no-wait
     policy_id=0002189219BF8EF3, r5d.2xlarge, BATCH_STAGGER_S=3, BATCH_CONCURRENCY≤48
4. poll: databricks jobs get-run <id>
5. harvest: databricks fs cat (NEVER fs cp for download)
6. AND-gate: size≥1KB and UNIT-COMPLETE in last 600 bytes
7. apply + smoke on Windows
```

Notebook: `/Users/costin.ionescu@bolt.eu/codex-batch/batch_runner`  
Auth secret: scope `codex-harness-prekzursil` key `auth_json`

## Unit types

| Type | Writes | Bundle | Ownership |
|------|--------|--------|-----------|
| Research | one `.md` | optional README | n/a |
| Implement | `.md` + full `.py` modules | **required** subject tarball | **exclusive** paths per unit |
| Merge | one owned file set | current tree tarball | disjoint by design |

## Proven harness directories (this machine)

| Path | Purpose |
|------|---------|
| `~/scratch/codex-auth-research-fanout/databricks/` | original auth research |
| `~/scratch/crcp-e2e-p0-fanout/` | CRCP P0/P1/merge implement |
| `~/scratch/crcp-web-account-fanout/` | web-account endgame research (89 units) |

## Auth planes (do not conflate)

- **Codex `auth.json`** — temporary consumer for backend-api / Codex CLI. Expires.
- **ChatGPT web session** — durable owner plane for the human chatgpt.com account. Different store.

CRCP list/send via Codex token is **not** the endgame for “web account access.”

## Local health probes (Fiddler)

```powershell
$env:NO_PROXY = "127.0.0.1,localhost"
curl.exe --noproxy "*" http://127.0.0.1:8812/api/health
curl.exe --noproxy "*" http://127.0.0.1:8820/livez
```

Python loopback: `ProxyHandler({})`.

## Ban list (print and obey)

1. bare `new_cluster` without policy_id  
2. `fs cp` for DBFS→local  
3. DONE without `UNIT-COMPLETE`  
4. stagger 0 at high concurrency  
5. shared rewrite of the same module in one wave  
6. hardcoding `/local_disk0/...` as only import root in repo scripts  
7. secrets in batch.json or result artifacts  
8. claiming web-account durability from access_token alone  

## Evidence (selected)

- 48/48 auth research @ stagger 3s  
- CRCP 15/15 implement SUCCESS ~560s (run 690432742789715)  
- CRCP merge 5/5 (run 961988947593804)  
- Web-endgame 89-unit submit (run 1023601984546724)