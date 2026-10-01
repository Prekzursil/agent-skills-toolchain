<!-- verbatim final report of background subagent adf31aee54ed99752, saved 2026-09-19 -->

## Directions

### 1. Staging Space; production is promote-only
- What: A private duplicate of the Space (same model mounts and variables, Dev Mode off). Every change must boot there and pass a canary, and production only receives shas that passed.
- Why it matters for this owner: This is the only control that catches `f90bb44`, because lint and tests cannot see a ZeroGPU contract violation. There were 23 pushes in 2h35m, and 12 of the 22 gaps were shorter than one boot.
- Feasibility and constraints:
  - Verified: PRO accounts can host 10 ZeroGPU Spaces. `duplicate_repo` takes hardware, volumes and variables. Secrets are not copied to a duplicate. Quota is per account (docs: spaces-zerogpu, spaces-overview, manage-spaces).
  - Unverified: the quota cost of a canary, since no captured log records generation timing.
- Effort: M.
- Decision it forces: What must staging prove before promotion?
  - (a) It boots.
  - (b) It boots and passes a 16-token canary.
  - (c) (b) plus an API and tool smoke test.
  - Recommend (b). Trade-off: every change costs 10+ minutes, which forces batching.

### 2. Verify after deploy, else redeploy the known-good sha
- What: A verifier checks that the pushed sha equals `runtime.sha` and the build id served by `/healthz`. It then waits for readiness, runs the canary and records the sha as known-good. On hard failure it redeploys the previous known-good sha. When production is red, roll back first.
- Why it matters for this owner: Production was still down at 00:10Z, and the forward fix `f88b120` cannot import. Restoring `17dce0c` would cap an outage at one boot. `/healthz` returns a constant (`openai_api.py:47-48`), so it proves nothing about the model.
- Feasibility and constraints:
  - Verified: `restart_space` has no revision argument, so rollback has to be a new commit. `fetch_space_logs` exists.
  - Unverified: how the app learns its own build id; I suggest the pipeline writes a `build_info.json`.
- Effort: M.
- Decision it forces: How is rollback triggered?
  - (a) Manually.
  - (b) Automatically, on hard signals only (error stage, sha mismatch, not ready in 12 min).
  - (c) Automatically on any failure.
  - Recommend (b). Trade-off: a false positive costs a boot, and a rollback also reverts product copy.

### 3. One cheap, mandatory gate on a clean checkout
- What: One command under Python 3.12 that runs four checks:
  - an undefined-name lint (ruff F821 or pyflakes);
  - the unit tests;
  - an import-smoke of `app.py` with heavy libraries stubbed;
  - a claim lint that rejects commit messages whose numbers are absent from a whitespace-insensitive diff.

  Also pin `TOK_PER_SEC`, `DURATION_CAP` and preset sizes in a torch-free `config.py` with tests, and add `* text=auto eol=lf`.
- Why it matters for this owner:
  - `py_compile` passes on the broken HEAD (verified here).
  - An undefined-name scan finds exactly three names: `_load_draft` (l.189, import time), `_resolve_image_urls` (l.553) and `_media_from_message` (l.666, every chat turn). An import-smoke alone misses the last two.
  - The failing test needs `_personas_archive/`, which `deploy_space.py` excludes from upload.
  - I tested the claim lint: it fails 5 of the 6 F1 commits. `17dce0c` passes it, because the commit only rewrote a help string ("presets stay on large") while `app.py:866` still sets `gpu_size="xlarge"`. Only a pinned test catches that one.
  - New finding: `08af7ea` flipped `app.py` to CRLF, producing a 1,992-line diff that hides a 2-line change.
- Feasibility and constraints:
  - Verified locally (73 tests, 0.02 s; git only).
  - The pushing box runs Python 3.14 (inferred from `.pyc` debris); ZeroGPU supports 3.12.12 and 3.10.13 only.
  - The claim lint needs a waiver trailer for false positives.
- Effort: S.
- Decision it forces: Where does the gate run?
  - (a) Inside `deploy_space.py`.
  - (b) In CI on every PR.
  - (c) Both.
  - Recommend (c), starting with (a) today. Trade-off: (a) alone can be bypassed and sees the dirty working directory.

### 4. GitHub as source of truth; CI the only production writer
- What: A private GitHub repo becomes the source of truth. The Space becomes a mirror written by one workflow through Trusted Publishers (OIDC, nothing stored). Agent tokens can write to staging only. The PR template is the hand-off note (intent, claims, gate output, staging sha, rollback sha), and a workflow concurrency group is the lease.
- Why it matters for this owner: Today the truth is a Windows folder plus the Space. `upload_folder` never deletes, so the now-ignored `idx.json` and `runlog_tail.txt` are still tracked. `f88b120` was pushed unlinted four minutes after the break, which shows advisory gates get skipped under pressure.
- Feasibility and constraints:
  - Verified: the Trusted Publisher token lasts one hour, is scoped to one repo, and is pinned to repository, branch and workflow. `huggingface/hub-sync` mirrors deletions (docs: trusted-publishers, repositories-github-actions).
  - Unverified: OIDC against a private Space, and whether branch protection on a private repo needs a paid GitHub plan.
- Effort: M.
- Decision it forces: Who holds production-write credentials?
  - (a) Any agent.
  - (b) One agent.
  - (c) CI only.
  - Recommend (c). Trade-off: no hot-fixing from a terminal.

### 5. Space configuration as code; Dev Mode off in production
- What: Four pieces:
  - a checked-in `space.yaml` covering hardware, Dev Mode, variables, secret names and volumes;
  - a read-only drift job that compares it with the live Space;
  - a `repo.config` webhook that reports changes;
  - a `requirements.lock` frozen from a good boot.
- Why it matters for this owner:
  - A write-scoped `NF4_UPLOAD_TOKEN` appeared in production, beside python_eval and web tools, with no record.
  - Config changes restart the app.
  - `set_space_volumes` replaces all mounts, so two agents each adding one can unmount the model.
- Feasibility and constraints:
  - Verified: `get_space_variables`, `get_space_secrets` (names only), `runtime.volumes`, and the `repo.config` webhook scope.
  - Verified: Dev Mode discards changes on sleep and skips requirements installs (docs: spaces-dev-mode, webhooks).
  - Unverified: how pushes behave under Dev Mode.
- Effort: S-M.
- Decision it forces: When is Dev Mode on in production?
  - (a) Always.
  - (b) Never; staging only.
  - (c) During incidents only.
  - Recommend (b), rehearsed on staging first because ranged requirements re-resolve on a clean rebuild. Trade-off: no SSH into production.

### 6. Retire the laptop keep-alive and the dead updater
- What: Replace the updater with lock-bump PRs that must pass staging. Replace the laptop keep-alive with a scheduled CI check that reads stage, sha, readiness and canary tok/s, and stores a telemetry row and the boot log per run.
- Why it matters for this owner:
  - The updater is verified dead: `bump_within_range` returned `None` in all 20 trials. If it worked, it would ship after tests that import none of the bumped libraries.
  - The keep-alive has logged only two 502s.
  - No decode speed is logged anywhere, so 22 versus 9.2 tok/s stays folklore.
- Feasibility and constraints:
  - Verified: `fetch_space_logs` and `hf spaces logs` exist.
  - Unverified: any API for remaining ZeroGPU quota.
- Effort: S.
- Decision it forces: What happens to the keep-alive?
  - (a) Drop it and accept a cold boot after 48 h idle.
  - (b) Move it to a CI cron.
  - (c) Keep the Windows task.
  - Recommend (a) plus the scheduled check. Trade-off: CI needs a read-scoped token.

## Killed ideas
- `py_compile` as the gate: it passes on the broken HEAD.
- An AST rule for module-level model loads: brittle, and a staging boot proves the same thing.
- A lease file in the Space repo: every write rebuilds production.
- A webhook-triggered HF Jobs auditor: it bills per run.
- Restarting at a pinned revision: there is no such API parameter.

## Biggest unknown
Who issues the ~300 s restarts.
- `f90bb44` says lazy-load was added to escape an "autorestart loop". The restarts therefore start the whole chain: workaround, CUDA violation, outage, rushed fix.
- If the pushing agent's own automation issues them, item 4 moves to first place. If the platform issues them, item 5 rises.
- Cheapest test: search that agent's transcript and scheduled tasks for `restart_space`, or pause it for 15 minutes and watch whether the restarts stop.

*Method: read-only review. I made no calls to the live Space and did not look for tokens. Platform facts come from read-only `hf_fs` reads of hf://docs plus one GitHub docs fetch. File references are relative to `/tmp/claude-1000/-workspaces-agent-skills-toolchain/ca9aa7a4-16ad-4e9d-bafe-00eed0171063/scratchpad/space-latest/` (HEAD `f88b120`).*