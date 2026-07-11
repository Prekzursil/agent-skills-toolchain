# Codex Runner — setup

One **private** runner (this repo) drives OpenAI Codex against **any** of your repos
on your **ChatGPT subscription** (no pay-per-token API key) and opens a **PR** with the
result. The account credential lives only here; target repos are reached via a PAT, so
your public repos never hold the secret.

## 1. Set the two secrets (in THIS repo → Settings → Secrets and variables → Actions)

**`CODEX_AUTH_JSON`** — the full contents of your local `~/.codex/auth.json`. Pipe it so
the tokens never touch your clipboard:

```powershell
# PowerShell
gh secret set CODEX_AUTH_JSON --repo Prekzursil/agent-skills-toolchain --body (Get-Content "$HOME\.codex\auth.json" -Raw)
```
```bash
# bash
gh secret set CODEX_AUTH_JSON --repo Prekzursil/agent-skills-toolchain < ~/.codex/auth.json
```

**`CODEX_RUNNER_PAT`** — a **fine-grained** Personal Access Token
(github.com → Settings → Developer settings → Fine-grained tokens):
- **Resource owner:** Prekzursil
- **Repository access:** select the repos the runner may work on (or *All repositories*)
- **Permissions:** *Repository* → **Contents: Read and write**, **Pull requests: Read and write**. Nothing else.
- *(Only if you enable the optional write-back step below:* also grant **Secrets: Read and write** on `agent-skills-toolchain`.)*

```powershell
gh secret set CODEX_RUNNER_PAT --repo Prekzursil/agent-skills-toolchain --body "<paste-the-PAT>"
```

## 2. Run it

Actions tab → **Codex Runner** → *Run workflow* → fill in:
- **target_repo**: e.g. `Prekzursil/momentstudio`
- **task**: e.g. `Open a PR fixing the open CodeQL alerts`
- **base_branch**: blank = default branch
- **model**: default `gpt-5.5` — **change to whatever slug your account accepts** (your local config uses `gpt-5.6-sol`; verify in CI on the first run).

Or from the CLI:
```powershell
gh workflow run "Codex Runner" --repo Prekzursil/agent-skills-toolchain -f target_repo=Prekzursil/momentstudio -f task="Bump dependencies and open a PR"
```

**"All repos"** = run it once per repo (different `target_repo` each time), or later add a
`schedule:` trigger + a matrix that loops a repo list. It is **one host for the whole
fleet** — you do not copy the secret anywhere else.

## 3. Safety model (why it's built this way)

- **Trigger is `workflow_dispatch` only** — only write-access users can start it, so no
  fork/outside actor can reach `CODEX_AUTH_JSON`. **Never** add `pull_request_target` or a
  fork-triggerable event to this workflow.
- **Propose-only:** the runner opens PRs; it never merges. Protect payment/auth branches
  with branch protection + CODEOWNERS so you always review.
- **Inputs go through `env:`**, never spliced into a shell line (avoids the
  `actions/code-injection` class CodeQL flags).
- Rotate anytime with `codex logout && codex login`, then re-set `CODEX_AUTH_JSON`.

## 4. Token refresh (reliability)

Codex refreshes — and **rotates** — its tokens on use. The stored `auth.json` will
eventually go stale. Two options:
- **Simple (default):** when a run fails on auth, re-run `codex login` locally and re-set
  `CODEX_AUTH_JSON`. Fine for occasional use.
- **Auto (optional):** uncomment the "Persist refreshed auth.json" step at the bottom of
  `codex-runner.yml` **and** give `CODEX_RUNNER_PAT` the `Secrets: write` permission on
  this repo. The runner then writes the rotated token back after each run.
