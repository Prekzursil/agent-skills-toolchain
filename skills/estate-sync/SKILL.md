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

## Related

- `knowledge/OPEN-LOOPS.md` — the live register; nothing closes without evidence
- `knowledge/policy/2026-09-24-private-estate-plaintext.md` — credential policy SSOT
- `scripts/estate-deny-guard.py` and `scripts/test_estate_deny_guard.py` — the
  guard and its 11-case suite
