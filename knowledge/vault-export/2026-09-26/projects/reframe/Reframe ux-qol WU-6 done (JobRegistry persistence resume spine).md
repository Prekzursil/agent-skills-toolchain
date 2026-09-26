---
title: Reframe ux-qol WU-6 done (JobRegistry persistence resume spine)
type: note
permalink: main/projects/reframe/reframe-ux-qol-wu-6-done-job-registry-persistence-resume-spine
tags:
- reframe
- ux-qol
- sidecar
- milestone
---

# Reframe ux-qol WU-6 — DONE (2026-06-20)

Branch `feat/ux-qol-design`, commit **736ad47** (pushed, 6090fce..736ad47). 7 files, +568/-29.

## What WU-6 did (resume spine, sidecar-only)
- `jobs.py`: added `JobStatus.INTERRUPTED` (real wire value, NO info() mapping — unlike PENDING->"queued"); injected keyword-only `store: JobStore|None=None` into `JobRegistry` (default None = in-memory back-compat); single `_set_status` choke-point routes all four sinks (running/done/cancelled/error) through one write-through; write-through on `create` + the guarded `record_request` path; `rehydrate()` reloads records, maps non-terminal (pending/running/queued)->INTERRUPTED (persisted re-mark), keeps terminal verbatim, restores `request` for `job.retry`, NEVER auto-spawns (S5 no-silent-spend), advances id counter past rehydrated numeric ids.
- `rpc.py`: threaded `store` through `RpcServer.__init__`/`build_server`/`main`; `main` rehydrates once at startup when store supplied.
- `__main__.py`: composition seam — capture `Services` from `register_all()` (it returns svc), build `DiskJobStore(svc.data_dir/"jobs")`, inject into `rpc.main`. This is the ONLY place data_dir (Services-owned) meets the registry (RpcServer-owned).

## Gates
- WU-6 files at **100% line+branch** (jobs/rpc/__main__ verified isolated). job_store.py is WU-5's, 100% in full suite.
- ruff check+format clean; basedpyright 1.39.8 = 0 errors (7 pre-existing missing-ML-import warnings in unrelated features/*_backend.py).
- Full sidecar suite 3047 passed (py 3.12).

## KEY GOTCHA — pre-existing coverage gap on py 3.12/3.14
The strict `--cov=media_studio --cov-fail-under=100` gate reports **99.79%**, but this is NOT from WU-6. Independently proven via a fresh clone of the clean base commit (WU-5): the SAME 5 files already report partials — `vlm_backbone.py`, `vlm_backbone_backend.py`, `ai_job.py:142->exit`, `budget.py:93->exit`, `presets.py:109->exit` (the `->exit` branch). CI ran an older coverage.py where these didn't trip. Do NOT try to "fix" these for a WU — they are out of scope and unrelated. WU-6's own diff adds zero new gaps.

## Env notes
- Repo cloned to a unique Windows temp path; py 3.12 via `py -3.12` (CI uses 3.12); basedpyright via `npx basedpyright@1.39.8`.
- `.pre-commit-config.yaml` exists but is NOT installed as a git hook — ran ruff+basedpyright manually to match.
