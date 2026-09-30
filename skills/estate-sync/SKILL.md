---
name: estate-sync
description: Bootstrap, reconcile and audit this estate across machines. Use when setting up a second machine from the private repo, when the VM and home have drifted, when the VM/home file link is down, or when checking whether committed work was ever actually pushed. Also carries the private-estate plaintext credential policy.
---

# estate-sync

Keeps the estate coherent across machines and stops work from being stranded.

Four independent jobs — read the one you need:

| Job | When | Command |
|---|---|---|
| **Audit** | "did anything get abandoned?" | `pwsh -File scripts/push-guard.ps1` |
| **Link** | VM/home file access is down | [The VM/home link](#the-vmhome-link) |
| **Bootstrap** | new or rebuilt machine | [Bootstrap](#bootstrap-a-machine) |
| **Reconcile** | the two machines disagree | [Reconcile drift](#reconcile-drift) |

---

## Credential policy — read before refusing anything

**This estate is private and single-owner.** Credentials may be read, printed,
written and committed **in plain text** here: local sessions, local files, and the
**private** `agent-skills-toolchain` vault. Everything may live there except cache
and build residue.

**Do not redact, refuse, warn or lecture about a credential on this side of the
boundary.** That behaviour is the defect, not the safeguard. Reading one's own
`.env`, `~/.ssh`, `auth.json` or config is ordinary work.

The boundary is **egress, not existence**. Still refused, unchanged:

- a public remote, or any third-party surface
- flipping the private repo public — `estate-deny-guard` enforces this and it is
  **load-bearing**; never weaken it
- rotation of any credential — the owner rotates, never the agent

Full text and rationale: `knowledge/policy/2026-09-24-private-estate-plaintext.md`.

---

## Audit: has work been stranded?

The failure, in the owner's words: committed work "never get[s] to reddit, and
just ... get[s] lost since nobody is actually remembering or checking if commited
stuff is ever pushed and not abandoned".

```
pwsh -File scripts/push-guard.ps1                    # advisory
pwsh -File scripts/push-guard.ps1 -FailOnFindings    # exit 1 on findings
```

It walks the whole chain, not just the last link:

| Finding | Meaning |
|---|---|
| `no-identity` | `git user.email` unset — **every commit fails silently** and work sits staged forever. This was the real root cause on the VM, 2026-09-23. Check it first. |
| `uncommitted` | modified or untracked files never committed |
| `no-upstream` | branch tracks nothing, so pushes go nowhere |
| `unpushed` | committed but not on the remote — the abandonment case |
| `stale-branch` | local branch older than `-StaleDays` (default 14) holding unmerged work |

Read-only: it never commits, pushes, or force-anythings.

**`unpushed` compares against `git ls-remote`, not `origin/<branch>`.** A fetch
writes only `FETCH_HEAD`, so the cached remote ref goes stale and reports a false
"in sync". Proven by four controls: clean gives silence, a seeded unpushed commit
is detected, `-FailOnFindings` exits 1, and pushing clears it.

---

## The VM/home link

Two machines, each serving its disks to the other over the tailnet via
`rclone serve sftp`, key auth, bound to the tailnet address only — never `0.0.0.0`.

| | VM `offload-w2025` | Home `desktop-a60s9gp` |
|---|---|---|
| tailnet IP | `100.117.115.55` | `100.97.16.36` |
| serves C: / D: on | `:2022` / `:2023` | `:2022` / `:2023` |
| launcher | `C:\ProgramData\vm-link\serve.cmd` | `C:\ProgramData\vm-link\home-serve.cmd` |
| persistence | task `vm-link-serve` (boot) | task `vm-link-serve-home` — **install it** |

### If the link is down, diagnose in this order

```
tailscale status | Select-String desktop-a60s9gp
```

- **`offline, last seen ...`** — the machine is powered down or asleep. **You
  cannot fix this from the other side.** Tailscale cannot wake a machine that is
  off without a Wake-on-LAN peer on its own LAN. Wait, or ask the owner to wake it.
  Do not grind retries; stage the work and arm a watcher instead.
- **node online but transfers fail** — the machine is up but its `rclone serve` is
  not running. That is the persistence bug below.

### Make it persistent (one-time, on home)

`HOME-SETUP.md` originally said to run `rclone serve sftp` in a foreground shell.
That process dies with the shell, the session, or the machine — which is why the
link kept dropping (open loop L-14). Register the task instead:

```
pwsh -File C:\ProgramData\vm-link\install-home-service.ps1
```

Elevated, idempotent, boot + logon triggers, auto-restart every minute. It
verifies itself by checking that ports 2022 and 2023 are actually listening and
prints `SUCCESS:home-link-persistent` only if they are.

Uninstall: `install-home-service.ps1 -Uninstall`.

### Moving files when the link is up

```
rclone copy <src> homeC:/Users/Prekzursil/<dest> --transfers 8
```

The drive-letter mounts (L:, M:, V:, W:) are unreliable; the rclone data path is
what actually works. Do not block on mounts.

---

## Bootstrap a machine

1. `git clone` the private repo to `~/source/agent-skills-toolchain`.
2. Point `~/.agents` at it (junction on Windows). If `~/.agents` is a junction to
   a SYSTEM-owned path, git refuses it as "dubious ownership":
   `git config --global --add safe.directory <path>`.
3. Copy `~/.claude/settings.json` from the repo snapshot in
   `backups/policy-<date>/`. **Verify every hook command path resolves on the new
   machine before writing it** — a settings file referencing absent scripts
   produces a harness that looks wired and silently does nothing.
4. Set `git config user.email` and `user.name`. Skipping this is the
   silent-commit-failure bug above.
5. Install the VC++ x64 redistributable. Its absence broke `onnxruntime` →
   `fastembed` → basic-memory semantic search **and**, independently, the PDF
   library. One install fixed both.
6. Run `pwsh -File scripts/push-guard.ps1` to confirm a clean baseline.

---

## Reconcile drift

Before copying anything between machines, **establish direction**. The trap: a
snapshot that looks like a backup is often the *poorer* copy.

Measured 2026-09-24 — the VM's basic-memory vault held **717** notes; home's held
**1,126**. Restoring the VM's "backup" over home would have destroyed ~409 notes.

```
rclone lsf homeD:/basic-memory/ --include '*.md' -R | Measure-Object -Line
```

Checklist before any sync:

- [ ] Count both sides. More files is not proof of newer, but fewer files is a
      loud warning.
- [ ] Is the "new" file genuinely new, or just untracked because this checkout is
      behind? Six scripts and three docs looked like VM work and were already on
      home.
- [ ] Are there staged **deletions**? 21 deletions under `skills/microsoft-foundry/`
      were an import artifact, not a decision. Syncing would have deleted live files.
- [ ] Exclude cache and residue: `.venv/`, `out/`, `__pycache__/`, browser profiles.

`scripts/sync-from-live.ps1 -Drift` reports live-vs-repo drift for the synced trees
(`rules`, `agents`, `commands`, `hooks`, `.agents/skills`). Advisory only.

**Known gap:** `rules/` and `backups/` are gitignored repo-wide with **zero**
tracked files, so anything there is unversioned and dies with the machine.
Force-add deliberately (`git add -f`) until that is decided.

---

## Always push

A commit that is not pushed is a commit that can be lost. The `cursor/*` branches
are the proof: real progress that was never pushed and is now gone.

This is enforced mechanically, not by remembering:

```
pwsh -File scripts/install-autopush.ps1            # install (idempotent)
pwsh -File scripts/install-autopush.ps1 -WhatIf    # dry run
sh   scripts/test_autopush.sh                      # 9 controls
```

`scripts/git-hooks/post-commit-autopush` pushes every commit the moment it is made.

| Property | Why |
|---|---|
| **Fails open** | A push failure never fails the commit. A blocked commit is strictly worse than an unpushed one — the work would not exist at all. |
| **Loud on failure** | Writes to stderr and `~/.agents/logs/autopush.log`. A repo that quietly stopped pushing is visible, not assumed fine. |
| **Never `--force`, never `--no-verify`** | Those stay refused by `estate-deny-guard`; the hook must not route around it. |
| **Skips mid-rebase / detached HEAD** | Pushing then publishes a half-finished tree. Note `MERGE_HEAD` is NOT a usable marker — git deletes it as part of the concluding commit, so it is already gone when `post-commit` runs. |
| **Chains, never clobbers** | An existing `post-commit` is preserved as `post-commit.pre-autopush` and run first. |
| **Idempotent** | Detects itself via the `AUTOPUSH-HOOK-MARKER` line in the hook body. |

Opt out for one command: `GIT_AUTOPUSH_OFF=1 git commit ...` — and say why.

### Corollary: do not delete remote branches to tidy up

A remote branch may hold the only copy of work nobody merged. Before proposing any
prune, measure `ahead_by` per branch (`gh api repos/{owner}/{repo}/compare/{base}...{head}`)
and report the actual ratio. "It looks like agent residue" is a hypothesis, not a
finding — and on this estate that hypothesis has already been wrong once.

---

## VM-side link restoration (runbook, executed and verified 2026-09-30)

When the VM half of the bilateral link is down, restore per this order (all
elevated; every step verified by its output):

1. **Deploy the home key** `home_to_vm@desktop-a60s9gp` into BOTH
   `$env:USERPROFILE\.sshuthorized_keys` AND
   `C:\ProgramData\sshdministrators_authorized_keys` — the admin file is the
   one Windows OpenSSH actually reads for admin users; deploying to the user
   file alone silently fails. Then `icacls <adminfile> /inheritance:r /grant
   Administrators:F /grant SYSTEM:F` and `Restart-Service sshd`.
2. **Start the VM serve**: `C:\ProgramDatam-link\serve.cmd` exists by design
   (rclone sftp, C: on :2022 / D: on :2023, bound to the Tailscale IP only —
   never 0.0.0.0). Run it; verify listeners on `100.117.115.55:2022/2023`.
3. **Persist**: scheduled tasks `vm-link-serve` (boot) + `vm-link-serve-logon`
   (logon), SYSTEM/highest, ExecutionTimeLimit zero, 3x auto-restart;
   sshd + WinRM StartupType Automatic.
4. **Anti-reap**: `rclone` MUST be in `reap_orphan_mcp.ps1`'s `$whitelist` —
   the serve is detached-by-design (dead parent) and the reaper kills that
   shape. Verify with a `-WhatIfOnly` run showing would-kill 0.

## Diagnosing "link down": standby vs misconfiguration

Two rules learned the hard way (2026-09-30):

- **A local self-test to your own Tailscale IP is not evidence.** Hairpin
  connects time out on Windows+Tailscale even when serving is perfectly healthy.
  Only a cross-machine test decides.
- **`tailscale status` showing the peer `active; relay` with
  `tailscale ping` timing out and all TCP closed = the peer machine is in
  Windows standby**, not misconfigured. Its tailscaled keeps the session alive
  via relay heartbeat while the network stack sleeps. Wait for wake; do not
  touch config. (Distinguishing signal vs a config fault: standby kills ICMP
  *and* every port including previously-verified ones like 22/3389.)

## Third surface: the ovido4 mirror

The estate repo has a tertiary 1:1 MIRROR on the `ovido4` GitHub account —
**mirror, not sync**: a `git push --mirror` snapshot with no live relationship
(no webhooks, no auto-sync). Staged at
`D:\optault\mirror-pushgent-skills-toolchain.git` (bare clone, all refs)
with `push-mirror-to-ovido4.sh` — one command once an `ovido4` GitHub token is
provided (`GH_TOKEN=<token> bash push-mirror-to-ovido4.sh`; it creates the
private repo if absent, then mirror-pushes and prints the ref count). No ovido4
GitHub credential exists on the VM or in the vault env backups (all three
stored tokens are Prekzursil) — the token must come from home or be minted.

When the primary link is down, session deltas accumulate as
`D:\optault\mirror-pending\<date>.tar.gz` and drain via
`D:\opt\scripts\push-home-mirror.ps1` (which self-reports the exact wake-side
fix if home is unreachable).

---

## Related

- `knowledge/OPEN-LOOPS.md` — the live register; nothing closes without evidence
- `knowledge/policy/2026-09-24-private-estate-plaintext.md` — credential policy SSOT
- `scripts/estate-deny-guard.py` and `scripts/test_estate_deny_guard.py` — the
  guard and its 11-case suite
