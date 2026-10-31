---
title: codex-fleet-sweep-setup
type: note
permalink: dqverify-repo-20261013/docs/codex-fleet-sweep-setup
---

# Codex Fleet Sweep — setup & token model

The **fleet sweep** lets the PUBLIC control plane (QZT, `Prekzursil/quality-zero-platform`)
drive the PRIVATE Codex runner (`Prekzursil/agent-skills-toolchain :: codex-runner.yml`)
on a schedule, across many of your repos, without ever letting QZT touch the runner's
`auth.json`. This document explains the three fine-grained PATs it needs, where each one
lives, and how the wave and the token-refresh write-back interlock.

> TL;DR — create 3 fine-grained PATs, set 2 as **QZT** secrets and 1 as an
> **agent-skills-toolchain** secret. `auth.json` never leaves the runner repo.

---

## 1. Architecture (who holds what)

```
                 codex-targets.yml (public, non-secret)
                         │  reads
   ┌─────────────────────▼─────────────────────┐
   │  QZT (PUBLIC) — control plane, NO auth     │
   │  .github/workflows/codex-fleet-wave.yml    │
   │  secrets: CODEX_DISPATCH_PAT               │──┐ gh workflow run (Actions: write)
   │           CODEX_FLEET_READ_PAT             │  │ + gh pr list dedupe (PR: read)
   └────────────────────────────────────────────┘  │
                                                    ▼
   ┌────────────────────────────────────────────────────────────────┐
   │  agent-skills-toolchain (PRIVATE) — runner, HOLDS auth          │
   │  .github/workflows/codex-runner.yml                             │
   │  secrets: CODEX_AUTH_JSON  (the ChatGPT-sub auth.json)          │
   │           CODEX_RUNNER_PAT (contents+PR write on TARGET repos)  │
   │           CODEX_SECRETS_PAT (Secrets: write on THIS repo) ◄─────┼── token-refresh
   └───────────────────────────────┬────────────────────────────────┘   write-back
                                    ▼  opens a propose-only DRAFT PR
                              target repo (e.g. Reframe)
```

**Security split (never violate):** `auth.json` lives ONLY in the private runner repo as
`CODEX_AUTH_JSON`. QZT coordinates purely by *triggering* the runner. The dispatch PAT that
QZT holds can start a run but cannot read the runner's secrets, contents, or `auth.json`.
Triggers are `schedule` + `workflow_dispatch` only — **never** `pull_request_target` or any
fork-triggerable event.

---

## 2. The three tokens

All three are **fine-grained** personal access tokens (Settings → Developer settings →
Fine-grained tokens → *Generate new token*). Fine-grained PATs apply one permission set to
their selected repositories, so scope each token to exactly the repos it needs.

| Token | Stored as a secret in | Repository access | Permissions | Used for |
| --- | --- | --- | --- | --- |
| `CODEX_DISPATCH_PAT` | **QZT** | `agent-skills-toolchain` **only** | Actions: **Read and write**; Metadata: Read | `gh workflow run codex-runner.yml` (trigger the runner) |
| `CODEX_FLEET_READ_PAT` | **QZT** | the fleet target repos | Pull requests: **Read**; Metadata: Read | `gh pr list` open-PR dedupe |
| `CODEX_SECRETS_PAT` | **agent-skills-toolchain** | `agent-skills-toolchain` **only** | Secrets: **Read and write**; Metadata: Read | token-refresh write-back to `CODEX_AUTH_JSON` |

> **Why `CODEX_SECRETS_PAT` is a runner-repo secret, not a QZT secret.** The write-back step
> runs *inside* `codex-runner.yml` (in agent-skills-toolchain), and a workflow can only read
> secrets from its own repo. Putting it there is also the *secure* choice: the refreshed
> `auth.json` is written back in-place and never crosses into QZT. (The task brief's "set them
> as QZT secrets" applies to the two dispatch/read PATs; the secrets PAT belongs to the runner.)

### What each token deliberately CANNOT do
- `CODEX_DISPATCH_PAT`: no Contents, no Secrets → cannot read `auth.json`, source, or any
  other secret of the runner repo. It can only start `codex-runner.yml`.
- `CODEX_FLEET_READ_PAT`: read-only on pull requests → cannot write code, merge, or dispatch.
- `CODEX_SECRETS_PAT`: scoped to the runner repo's secrets only → cannot touch target repos.
  Keep it **separate** from `CODEX_RUNNER_PAT` (least privilege; different blast radius).

### Single-token alternative for the dedupe (optional, simpler, slightly broader)
If you would rather manage one dispatch token instead of two, scope `CODEX_DISPATCH_PAT` to
the **whole fleet** with **Actions: Read and write** *and* **Pull requests: Read**, and skip
`CODEX_FLEET_READ_PAT` entirely. The wave uses
`${{ secrets.CODEX_FLEET_READ_PAT || secrets.CODEX_DISPATCH_PAT }}` for the dedupe, so it
"just works" either way. Tradeoff: this grants Actions: write on the target repos too (it can
trigger their workflows). `auth.json` stays protected regardless (no Contents/Secrets grant).
The two-token model above is the least-privilege default and is recommended.

---

## 3. Create the PATs and set the secrets

### 3.1 `CODEX_DISPATCH_PAT` (QZT secret)
1. Generate a fine-grained token. **Resource owner:** your account. **Repository access →
   Only select repositories →** `agent-skills-toolchain`.
2. **Permissions → Repository →** Actions: *Read and write*. (Metadata: *Read-only* is added
   automatically.)
3. Copy the token, then set it as a QZT secret:
   ```bash
   gh secret set CODEX_DISPATCH_PAT --repo Prekzursil/quality-zero-platform
   # paste the token when prompted (or: --body "$TOKEN")
   ```

### 3.2 `CODEX_FLEET_READ_PAT` (QZT secret)
1. Generate a fine-grained token. **Repository access → Only select repositories →** add
   every fleet repo you intend to sweep (at minimum the ones you set `enabled: true`).
2. **Permissions → Repository →** Pull requests: *Read-only*.
3. Set it as a QZT secret:
   ```bash
   gh secret set CODEX_FLEET_READ_PAT --repo Prekzursil/quality-zero-platform
   ```
   *(Skip this token if you chose the single-token alternative in §2.)*

### 3.3 `CODEX_SECRETS_PAT` (agent-skills-toolchain secret)
1. Generate a fine-grained token. **Repository access → Only select repositories →**
   `agent-skills-toolchain`.
2. **Permissions → Repository →** Secrets: *Read and write*.
3. Set it as a secret on the **runner** repo (not QZT):
   ```bash
   gh secret set CODEX_SECRETS_PAT --repo Prekzursil/agent-skills-toolchain
   ```
4. Then enable the write-back step — see §5.

---

## 4. How the wave runs

- **Schedule:** `codex-fleet-wave.yml` fires daily at 22:00 UTC (off-peak). It also has a
  manual `workflow_dispatch` with two inputs: `only_repo` (dispatch a single repo, bypassing
  its `enabled` flag) and `dry_run` (preview the plan without triggering anything).
- **Plan:** it reads `codex-targets.yml`, and `scripts/build_codex_matrix.py` expands every
  `enabled: true` target × its `tasks[]` into a dispatch plan (per-repo `model` / `effort` /
  `max_changed_files` override the top-level `defaults`).
- **Dedupe:** before each dispatch it lists the target's open PRs (`gh pr list --state open`)
  and **skips** any repo that already has an open runner proposal (so a sweep never piles a
  second draft PR on top of one you haven't reviewed yet). It matches on EITHER the
  `codex-runner` label OR the runner's unlabeled-fallback signature — PR title
  `Codex: automated change` or a head branch under `codex/`. The second match matters because
  the runner falls back to an **unlabeled** `gh pr create` on any target that lacks the
  `codex-runner` label (every fresh target), so a label-only check would miss those and
  re-dispatch them nightly.
- **One lane:** dispatch is fully serial. Between targets the wave waits for the runner to be
  idle (no in-flight `codex-runner` run) before firing the next. This is required because
  GitHub keeps at most **one pending run per concurrency group** and silently cancels older
  pending runs — firing a burst at the single-lane runner would otherwise drop most of them.
- **Roll-up:** a final step writes a table to the run summary — plan entries, dispatched,
  skipped (open PR / dry-run), and errors. The job exits non-zero only if there were genuine
  errors (e.g. a token/scope problem), so benign "all skipped" runs stay green.

Manual examples:
```bash
# Preview tonight's sweep without dispatching anything:
gh workflow run codex-fleet-wave.yml --repo Prekzursil/quality-zero-platform -f dry_run=true

# Dispatch a single repo now (bypasses its enabled flag; it must have tasks defined):
gh workflow run codex-fleet-wave.yml --repo Prekzursil/quality-zero-platform -f only_repo=Reframe
```

---

## 5. Token-refresh write-back — why, and how it interlocks

Codex authenticates from the ChatGPT-subscription `auth.json`. That credential's refresh
token **rotates on renewal**, so a captured `auth.json` goes stale after a few days. For a
*scheduled* sweep that means the runner silently starts failing auth ~days after you first set
`CODEX_AUTH_JSON` — exactly the failure mode a nightly wave must survive. The fix: after each
run, write the (possibly refreshed) `auth.json` back into the `CODEX_AUTH_JSON` secret so the
next run starts from a fresh token.

That write-back is the reason `CODEX_SECRETS_PAT` exists. It ships **commented-out** at the
bottom of `codex-runner.yml`. To enable it:

1. Create and set `CODEX_SECRETS_PAT` (§3.3).
2. Uncomment the "Persist refreshed auth.json back to the secret" step (see MANIFEST for the
   exact lines). **Two corrections are required when you uncomment** (details in MANIFEST):
   - **Move it to run *before* the `Cleanup (always)` step.** Cleanup `rm -rf`s `$CODEX_HOME`;
     if the write-back runs after it, `auth.json` is already gone and the secret would be
     overwritten with an empty value.
   - **Guard on a non-empty file** (`[ -s "$CODEX_HOME/auth.json" ] || exit 0`) so a missing
     file can never blank the secret.

**Interlock summary:** QZT (`CODEX_DISPATCH_PAT`) triggers the runner → the runner uses
`CODEX_AUTH_JSON` to run Codex and opens a draft PR → the runner uses `CODEX_SECRETS_PAT` to
persist the refreshed `auth.json` back to `CODEX_AUTH_JSON`. QZT never sees `auth.json` at any
point; the refresh loop is entirely inside the private repo.

---

## 6. Security checklist

- [ ] `CODEX_DISPATCH_PAT` scoped to `agent-skills-toolchain` only (or fleet-wide if you took
      the single-token option), Actions: R/W, **no** Contents/Secrets.
- [ ] `CODEX_FLEET_READ_PAT` read-only on pull requests (or omitted under the single-token option).
- [ ] `CODEX_SECRETS_PAT` is a **separate** token from `CODEX_RUNNER_PAT`, scoped to the runner
      repo's Secrets only, stored on agent-skills-toolchain.
- [ ] `codex-fleet-wave.yml` triggers are `schedule` + `workflow_dispatch` only — never
      `pull_request_target` or any fork-triggerable event.
- [ ] The wave's `permissions:` is `contents: read` (it uses PATs, not `GITHUB_TOKEN`, for
      cross-repo actions).
- [ ] Rotate any PAT if a run log ever suggests exposure; revoking a fine-grained PAT is
      instant and does not affect the others.