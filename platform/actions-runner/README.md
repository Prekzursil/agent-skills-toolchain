# Self-hosted Actions runner — decision doc

Measured on offload-w2025, 2026-09-24. Repo: `Prekzursil/agent-skills-toolchain` (private).
Every number below came from `gh api` or the local host at that date; nothing is estimated
from memory. Where I could not measure something, it says so.

---

## 0. The premise changed under us — read this first

The task that produced this doc assumed a self-hosted runner still had to be *argued for*
and *built*. Both halves are already false:

| Assumption | Measured reality |
|---|---|
| "no runner exists yet" | **`home-wsl` is registered and was serving jobs today.** Labels `self-hosted,Linux,X64,home-wsl`. |
| "we must decide whether to switch CI to it" | **`vars.QUALITY_RUNNER` is already set to `self-hosted`.** |
| "workflows would need rewriting" | **12 jobs across 6 workflows already switch on that variable** (see §2). |
| "CI lives in `.agents/.github/workflows`" | That path **does not exist on the checked-out branch** (`live-capture/2026-09-02`). The 16 workflow files live on `main`. |

So this is not a greenfield "should we?" It is a **triage of a runner that already exists and
is currently failing open**. The install script in this directory is therefore a *rebuild /
relocate* tool, not a first install.

**The headline finding is not about minutes.** It is this:

> Home is **offline** (`tailscale status`: `desktop-a60s9gp … offline, last seen 2h ago`;
> `tailscale ping` times out; L:/M: not mounted). GitHub nevertheless still reports
> `home-wsl` as `status=online busy=true`. GitHub keeps assigning jobs to a runner that
> is not there. **14 runs are queued, 0 in progress**, the oldest waiting **19.5 hours**.

That is a *ghost runner*. It is strictly worse than having no self-hosted runner at all,
because GitHub-hosted fallback never happens — the job just waits forever. Fixing that is
worth more than anything else in this document. §5 gives the fix.

---

## 1. WHERE should it run

Neither candidate is good. I am not going to pretend otherwise.

### offload-w2025 (this VM)

| Property | Value |
|---|---|
| OS | Windows Server 2025 Datacenter 10.0.26100 |
| CPU / RAM | 12 logical cores / 96 GB |
| Free disk | **15.2 GB on C:** (of 149.9 GB) |
| WSL | **not installed** (`wsl.exe --status` → "The Windows Subsystem for Linux is not installed") |
| Docker | **no docker CLI** |
| Lifetime | **disposable — may be shut down at any time (owner, explicitly)** |

Two disqualifiers, one of them hard:

1. **Label mismatch (hard).** Every gated job asks for `fromJson('["self-hosted", "linux"]')`.
   A native Windows runner registers `Windows`, never `linux`, so it would **never be matched** —
   jobs would queue exactly as they are queueing now. To serve these workflows this box must run
   the runner **inside WSL2**, which is not installed. That is a real install (kernel + distro +
   runner ≈ 3–5 GB) against **15.2 GB free**. Feasible, tight, and not free.
2. **Disposability (hard for persistence, soft for cost).** A registration on a machine that can
   vanish leaves another ghost runner behind — the exact failure we are trying to kill.

### desktop-a60s9gp (home)

| Property | Value |
|---|---|
| Role | desktop, sleeps |
| Tailnet | `100.97.16.36` |
| State right now | **offline, last seen 2h ago**; `tailscale ping` → no reply |
| Runner | **already installed and registered** (`home-wsl`, so WSL already works there) |

Disqualifier: it sleeps, and sleeping is what creates the ghost runner.

### Recommendation

**Keep the runner at home (desktop-a60s9gp). Do not move it to this VM.** Reasons, in order:

1. Home already satisfies the `linux` label via WSL. The VM does not, and buying that costs a
   WSL2 install on a 15 GB disk.
2. The VM is disposable. Persistence work on a disposable host is work you do twice.
3. Home's defect (sleep) is **fixable in configuration**. The VM's defect (may be destroyed) is
   not fixable at all — it is the machine's purpose.

**The failure mode of my pick, stated plainly:** *home sleeps, and every hour it sleeps is an
hour CI is silently stalled rather than loudly failing.* That is what is happening right now,
and it is the worst kind of CI failure because the queue looks "pending", not "red". This
recommendation is **only valid if you also apply the ghost-runner fix in §5** — specifically
`--ephemeral`. Without that fix, "keep it at home" is the wrong answer and you should turn the
self-hosted rail off entirely (`QUALITY_RUNNER=ubuntu-latest`) until home stops sleeping.

Confidence: **high** that home is the better of the two hosts (direct measurement of both).
Confidence: **moderate** that home + `--ephemeral` is sufficient long-term — it converts a
silent stall into a clean re-queue, but it does not make a sleeping desktop a server. If CI
must be reliable, the honest answer is *a host that does not sleep and is not disposable*, and
neither machine you own is that.

---

## 2. What CI currently runs

**16 workflow files** on `main`; GitHub reports 19 registered workflows + 5 dynamic
(Copilot, GHAS, Dependabot ×2, Dependency Graph).

### The gated set — already self-hosted-aware

These 6 files (12 job definitions) carry:

```yaml
runs-on: ${{ (github.event.inputs.runner-type || vars.QUALITY_RUNNER) == 'self-hosted'
             && fromJson('["self-hosted", "linux"]') || 'ubuntu-latest' }}
```

| Workflow | Lines | Jobs | Triggers | cancel-in-progress |
|---|---|---|---|---|
| `quality.yml` | **1875** | ~11 (9 gated) | push, PR, dispatch | true |
| `hook-audit.yml` | 163 | 4 | push, PR, dispatch | true |
| `mcp-audit.yml` | 96 | 4 | push, PR, dispatch | true |
| `rule-audit.yml` | 144 | 4 | push, PR, dispatch | true |
| `skill-dual-write.yml` | 192 | 3 | PR, dispatch | true |
| *(plus the matrix entries inside `quality.yml`)* | | | | |

### The ungated set — hardcoded `ubuntu-latest`

`autofix-models`, `codex-runner`, `dependabot-auto-merge`, `interpreter-floor`,
`no-runtime-junk`, `p2-agent-runner`, `p2-agent-shard`, `p2-loop-runner`,
`p2next-rail-count`, `pr-reconcile`, `routing-benchmark` (also `cron: 0 3 * * 0`).

These **cannot** move to a self-hosted runner without editing them.

### How long does it take

Measured, job level:

- `gate-hook-audit` on `self-hosted+linux` → **0.7 min**.
- Gated gates are generally short (sub-minute to a few minutes).
- Across the last 1000 runs: mean wall-clock **7.5 min**, median **0.33 min**, p90 **10.8 min**,
  max **293.9 min**. The tiny median is an artifact — most runs are cancelled or skipped
  within seconds, not real work.

### Volume

- **33,373** total runs all-time.
- Last 1000 runs span **1.74 days** → **~574 runs/day**. Today alone: **817**.

### Is CI red? Yes — for two unrelated reasons

**(a) Every GitHub-hosted job is failing instantly.**

Sampling the ubuntu-only workflows across today (UTC):

```
12:00Z  n=18   success=3    failure=0
13:00Z  n=3    success=0    failure=3
14:00Z  n=6    success=0    failure=6
16:00Z  n=30   success=0    failure=30
17:00Z  n=6    success=0    failure=6
18:00Z  n=6    success=0    failure=6
```

A clean break at **13:00Z on 2026-09-24**: 51 consecutive failures, zero successes since.
The failing jobs look like this:

```json
{"conclusion":"failure","labels":["ubuntu-latest"],"runner_name":"","steps":[],
 "started_at":"...18:29:35Z","completed_at":"...18:29:39Z"}
```

**Zero steps, empty `runner_name`, dead in 4 seconds.** The job never received a runner. That
is not a test failure — it is GitHub declining to give the repo a hosted runner.

Most probable cause: the repo went private and hosted minutes became metered/refused.
Confidence: **moderate-to-high (~75%)** — the temporal correlation with privatisation is
strong and the signature (no runner, no steps, instant fail) is the classic entitlement
refusal, but I could **not** confirm it directly: the modern billing endpoints returned
`410 moved`, `/user/settings/billing/budgets` returned `404`, and the PAT lacks the `checks`
scope (`403`) so GitHub's own explanatory annotation was unreadable. **Verify in one click:**
<https://github.com/settings/billing> → Spending limit for Actions. If it is $0, that is the
whole answer and raising it un-breaks 11 workflows immediately.

**(b) The self-hosted jobs that do run have a genuine failure.**

`skill-dual-write` on `home-wsl`: setup/checkout/python/pip all **succeed**, then step 5
`gate-skill-dual-write self-test` **fails** and steps 6–17 skip. That is a real product
failure in the gate's own self-test, unrelated to runners or billing.

Plus the starvation: **14 queued / 0 in progress**, waits of 26.7 min, 42.6 min, 67.9 min for
`quality`/`rule-audit`, and **872–1174 min (14–19.5 h)** for Dependabot graph/security updates.

---

## 3. The actual minutes cost today

`GET /users/Prekzursil/settings/billing/usage?year=2026&month=9`, plan = **Pro**
(3,000 included Actions minutes/month).

**September 2026, this repo:**

| Date | Minutes | Gross | Discount | **Net** |
|---|---:|---:|---:|---:|
| 09-01 | 475 | $2.85 | $2.85 | $0.00 |
| 09-02 | 2,844 | $17.06 | $17.06 | $0.00 |
| 09-19 | 3,830 | $22.98 | $22.98 | $0.00 |
| 09-20 | 8,514 | $51.08 | $51.08 | $0.00 |
| 09-21 | 8,475 | $50.85 | $50.85 | $0.00 |
| 09-22 | 8,397 | $50.38 | $50.38 | $0.00 |
| 09-23 | 504 | $3.02 | $3.02 | $0.00 |
| **Total** | **33,039** | **$198.23** | **$198.23** | **$0.00** |

Context: all repos in September = **81,340 min**, gross **$500.39**, net **$0.00**.
`momentstudio` is actually the bigger consumer at 45,007 min. August, this repo: 3,490 min.

Observed unit price in this account's data: **$0.006/min** for `Actions Linux` (that is the
number GitHub's own billing rows carry; list price for Linux 2-core is normally $0.008).

**Reading these numbers honestly.**

Net is **$0.00 on every single day** — discount exactly equals gross. That is the
public-repo entitlement (public repos get unlimited free Actions). It confirms the repo was
still effectively public for billing purposes through 09-23. Billing data currently ends
**09-24 09:31Z** and shows **0 items with netAmount > 0**, so *the metered era has not
produced a single charged minute yet*. The bill for the private era does not exist to be read.

So: **is a self-hosted runner worth it?**

Yes — and unusually clearly, *if* the run volume stays where it is. Projecting September's
measured 33,039 min/month onto private-repo pricing:

```
33,039 min − 3,000 included = 30,039 billable
30,039 × $0.006             ≈ $180 / month   (this repo alone)
```

That is not a trivial number, and it is the *floor*: 09-20→09-22 ran ~8,500 min/day, which
alone would be ~$51/day. At that rate the Pro allowance of 3,000 minutes is gone in **under
9 hours**.

**But the stronger conclusion is that the run volume itself is the defect.** Of the last 300
runs: **146 cancelled, 75 failed, 44 skipped, 28 succeeded** — a 9% success rate. 574 runs/day
against a repo with `cancel-in-progress: true` everywhere means push storms are spawning runs
that immediately cancel each other. Buying a self-hosted runner to absorb 33,000 minutes of
mostly-cancelled work is optimising the wrong variable. **Cut the run volume first; the runner
question gets much smaller afterwards.** A self-hosted runner is worth it *in addition to*
that, not *instead of* it.

---

## 4. `install-runner.ps1`

Ships alongside this doc. Idempotent, boot-persistent, and **embeds no credential**.

```powershell
# Get a SHORT-LIVED registration token (valid ~1h) — never stored:
gh api -X POST /repos/Prekzursil/agent-skills-toolchain/actions/runners/registration-token --jq .token

pwsh -File platform\actions-runner\install-runner.ps1 -RegistrationToken '<paste>'
pwsh -File platform\actions-runner\install-runner.ps1 -Status
pwsh -File platform\actions-runner\install-runner.ps1 -Uninstall -RemovalToken '<paste>'
```

Design choices, and why:

- **`-RegistrationToken` is a mandatory runtime parameter.** It is never written to disk, never
  defaulted, never read from a file in the repo. The script scrubs it from memory on exit. A
  registration token is short-lived by design; a removal token is fetched separately.
- **Runs the runner inside WSL2**, because the workflows demand the `linux` label and a native
  Windows runner can never match it. The script **preflights** WSL and **refuses to continue**
  if it is absent rather than silently installing a Linux kernel on a 15 GB disk.
- **`--ephemeral` by default.** This is the ghost-runner fix (§5): the runner takes exactly one
  job then deregisters, so a machine that sleeps mid-job leaves *no* phantom online runner for
  GitHub to assign work to.
- **Persistence mirrors `vm-link/install-home-service.ps1`**: a Scheduled Task with `-AtStartup`
  **and** `-AtLogOn` triggers, `-StartWhenAvailable`, `RestartCount 999` / 1-minute interval,
  `ExecutionTimeLimit` zero, `-Force` registration so re-running replaces rather than duplicates.
  A Scheduled Task is used rather than WSL systemd because systemd is not guaranteed enabled in
  the distro, whereas the task works either way — the same reasoning that put `vm-link-serve-home`
  on a task.
- **Self-verifies** and prints the `SUCCESS:` / `FAILED:` terminal-state marker, same convention
  as `install-home-service.ps1`.

It does **not** run here. This VM has no WSL, so the preflight would refuse — correctly.

---

## 5. Security note — and the ghost-runner fix

### The security condition that actually matters

**A self-hosted runner executes workflow code from the repo, as a real user, on real hardware,
with no teardown between jobs.** A GitHub-hosted runner is a fresh VM destroyed after each job;
a self-hosted runner is your desktop. Anything a workflow can express — arbitrary shell, network
egress, reading `$HOME`, reading the tailnet, reading every credential this estate keeps in plain
text — runs with the privileges of the account hosting it.

For a **private, single-owner** repo where every commit is the owner's own, that is acceptable:
the code running on the box is code the owner wrote, and the trust boundary is already the
owner's machine.

**It stops being acceptable the moment a workflow can be triggered by code the owner did not
write.** Concretely, any one of these ends it:

1. **The repo gains a second writer**, or any collaborator with push access.
2. **The repo goes public again**, or a fork can raise a PR — `pull_request_target`, or even
   `pull_request` on a self-hosted runner, lets an outsider's branch execute on your hardware.
   GitHub's own documentation says self-hosted runners are *not recommended* for public repos
   for exactly this reason. Note `gh repo edit --visibility public` is a hard-banned command in
   this estate, which is the same rule wearing a different hat.
3. **A bot's output becomes executable.** This repo already runs `codex-runner.yml`,
   `p2-agent-runner.yml`, `p2-agent-shard.yml`, `autofix-models.yml` and Dependabot
   auto-merge. The moment agent- or Dependabot-authored content reaches a branch that triggers
   a self-hosted job, the runner is executing code no human reviewed. **This repo is closer to
   that line than a typical single-owner repo** — `dependabot-auto-merge.yml` exists, and the
   Dependabot jobs are among those currently queued for the self-hosted runner.

Mitigations, in the order I would apply them: keep `--ephemeral` on; never let
`pull_request_target` reach a self-hosted job; keep the runner off any branch an automated
agent can push to without review; and prefer that the runner run as a **low-privilege account
that is not the owner's interactive session** — which, on a home desktop where the runner lives
in WSL under the owner's user, it currently is not.

### The ghost-runner fix (do this regardless of the rest)

Right now GitHub believes `home-wsl` is `online busy=true` while the machine has been
unreachable for two hours. Jobs assigned to it wait indefinitely — 19.5 hours observed.

1. **`--ephemeral`** (the script's default). One job per registration, then deregister. A
   sleeping machine leaves no phantom.
2. **Clear the current ghost now**, so the 14 queued jobs move:
   ```powershell
   gh api /repos/Prekzursil/agent-skills-toolchain/actions/runners --jq '.runners[]|"\(.id) \(.name) \(.status)"'
   gh api -X DELETE /repos/Prekzursil/agent-skills-toolchain/actions/runners/<id>
   ```
   Deleting a runner **registration** is not a credential operation and is safe; it does not
   touch tokens and the runner re-registers on next boot.
3. **Decide the fallback deliberately.** With the hosted rail also broken (§2a), flipping
   `QUALITY_RUNNER` to `ubuntu-latest` will *not* rescue CI until the spending limit is checked.
   Fix the spending limit first, then you have a working fallback to fall back *to*.

---

## 6. What I could not verify

Stated plainly so none of it reads as settled:

- **The exact reason hosted jobs fail.** Billing endpoints returned `410 moved`, the budgets
  endpoint `404`, and the PAT lacks `checks` scope (`403`) so GitHub's annotation text was
  unreadable. The metered-minutes explanation is inference from timing + signature, ~75%.
- **The private-era bill.** Billing data ends 09-24 09:31Z with zero charged items. The
  ~$180/month figure is a projection of September's *measured* volume onto the *observed*
  $0.006/min rate, not an invoice.
- **Whether `home-wsl` is wedged or merely asleep.** The API says `busy=true`; the host is
  unreachable. Both produce the same symptom from here.
- **Disk reporting on this VM.** C: and D: both report free 15.2 GB / size 149.9 GB — identical
  to the decimal. Possibly the same volume surfaced twice. Worth a glance before sizing anything.
- **`gate-skill-dual-write self-test`'s actual assertion.** Log blobs for the older runs had
  already expired (`BlobNotFound`). The failing step is identified; its message is not.
