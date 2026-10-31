---
name: estate-sync
description: Bootstrap, reconcile and audit this estate across machines. Use when setting up a second machine from the private repo, when the VM and home have drifted, when the VM/home file link is down, or when checking whether committed work was ever actually pushed. Also carries the private-estate plaintext credential policy. Also for establishing, verifying, or repairing the bilateral VM/home link (Link v2: dynamic binds, reverse tunnel, verify battery).
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

## The VM/home link (v2 — dynamic binds, reverse tunnel, verify battery)

Two machines serve their disks to each other over the tailnet via `rclone serve sftp`,
key auth, bound to the tailnet address or loopback only — never `0.0.0.0`.
Canonical scripts live in `skills/estate-sync/assets/link/` (deployed to
`C:\ProgramData\vm-link\` and `C:\Users\<user>\.local\bin\` as noted).

### Topology (proven 2026-10-01)

```
home→VM shell+files : ssh (key home_to_vm) → VM :22 ; rclone sftp VM:2022/2023 (C:/D:)
VM→home files       : reverse tunnel — VM localhost:21022/21023
                      → (ssh -R over the WORKING home→VM direction)
                      → home loopback serves 127.0.0.1:21222/21223 (C:/D:)
VM→home DIRECT data : network-blocked (disco pongs fine, zero packets at home stack;
                      firewall/ShieldsUp verified clean — do NOT re-litigate; the
                      tunnel is the sanctioned bypass)
```

### VM-agnostic rules (mirror-proof)

- Every serve computes the CURRENT `tailscale ip -4` at runtime (`vm-serve.cmd` v2);
  hardcoded addresses rot on the first mirror/jump.
- The jump target lives in ONE file: `C:\ProgramData\vm-link\target.conf`
  (`<user> <host-or-magicdns>`). The tunnel retry loop re-reads it every pass —
  update one line + restart `home-link-tunnel`, no reboot.
- Full mirror procedure (machine image → cross-project instance): see
  `estates/offload-w2025/2026-09-30-link-and-mirror/MIRROR-RUNBOOK.md`.

### First-boot hazard on mirrored machines (measured 2026-10-01)

A clone boots with the SOURCE's tailscaled state and **steals its tailnet identity**,
knocking the real machine offline. Before/at first boot on any mirror:
`tailscale logout` then fresh `tailscale up --hostname=<new-name>`. Check the tailnet
admin console for stale duplicate nodes.

### Verify the whole link (audit battery)

```
pwsh -File skills/estate-sync/assets/link/verify.ps1
```
Checks: home→VM ssh, VM serves :2022/:2023, tunnel task Running, 4/4 home listeners,
serve tasks armed, reaper whitelist needle. Terminal `SUCCESS:vm-link-verify` /
`FAILED:vm-link-verify fail=N`. 7/7 green required.

### Gotchas ledger (all ledger-proven 2026-10-01)

- SYSTEM tasks cannot read user-profile SSH keys — tunnel died silently until the key
  moved to `C:\ProgramData\vm-link\home_to_vm` with SYSTEM ACLs.
- `Test-NetConnection` lies under RAM pressure (false-closed on open ports, both
  machines) — use raw TcpClient (`verify.ps1` does).
- Local connect to your OWN tailscale IP times out (weak-host off) — normal, not an
  outage; only cross-node connects prove serving.
- GCP writes 403 "requires billing" even when billing is linked (webcoder-462916);
  reads work. Use the VM-side agent or RDP instead of burning time.
- Saved RDP credentials are SSO stubs (empty blob in user context) — don't mine.
- UAC secure desktop blocks synthetic keystrokes — write user-level files instead.
- `rclone`/`ssh`/`vm-link` processes are dead-parent-by-design under their tasks —
  whitelisted in BOTH reapers (`vm-link` needle home, `rclone` VM); do not prune.

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
   `$env:USERPROFILE\.ssh\authorized_keys` AND
   `C:\ProgramData\ssh\administrators_authorized_keys` — the admin file is the
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

The estate has TWO mirror surfaces — a **VM-level 1:1 mirror** (GCP machine image,
executed 2026-10-01) and a **repo-level git mirror** (staged, awaiting token).

### VM-level 1:1 mirror (GCP machine image — the Macrium equivalent)

`offload-mirror` in ovido4's project (`project-90b4a09f-be6f-4040-a6c`) is a
byte-identical clone of `offload-w2025` created via GCP machine image. Full
runbook: `estates/offload-w2025/2026-09-30-link-and-mirror/MIRROR-RUNBOOK.md`.

**The three blockers and their fixes** (so nobody rediscovers them):

1. **Billing write-block is account-specific**: `BILLING_DISABLED` on GCP
   writes affects ovido4@gmail.com but NOT prekzursil1993 (roles/owner), even
   on the same project. Switch account to do writes.
2. **Global CPU quota**: `CPUS_ALL_REGIONS` limit=12 per project; a 12-vCPU
   VM consumes it all. Cannot co-locate a second instance in the same project.
   Deploy to the other project instead.
3. **Cross-project service account**: machine image inherits the SOURCE
   project's SA; target account lacks `iam.serviceAccountUser` on it. Fix:
   pass `--service-account=<target-project-number>-compute@developer.gserviceaccount.com`
   explicitly on `instances create`.

**What NOT to use**: wbadmin/Windows Server Backup (requires feature install
reboot); GCP metadata SSH key deploy (no compute-accounts-daemon on custom
images). Use `reset-windows-password` + paramiko for initial access instead.

**The working sequence**:
```bash
# 1. snapshot + image (as prekzursil1993, source project)
gcloud compute machine-images create mirror-full-YYYYMMDD \
  --source-instance=offload-w2025 --source-instance-zone=europe-central2-a \
  --project=webcoder-462916 --storage-location=europe-central2

# 2. deploy (as ovido4, target project)
gcloud compute instances create offload-mirror \
  --source-machine-image=projects/webcoder-462916/global/machineImages/mirror-full-YYYYMMDD \
  --zone=europe-central2-a --project=project-90b4a09f-be6f-4040-a6c \
  --machine-type=n2-custom-12-98304 \
  --service-account=<target-SA> --scopes=default

# 3. access
gcloud compute reset-windows-password offload-mirror --user=prekzursil ...
# then paramiko password-login → deploy SSH key → key auth
```

### Repo-level git mirror (staged)

A git `push --mirror` snapshot of the vault repo. Staged at
`D:\opt\vault\mirror-push\agent-skills-toolchain.git` (bare clone, all refs)
with `push-mirror-to-ovido4.sh` — one command once an ovido4 GitHub token is
provided. No ovido4 GitHub credential exists on the VM or in the vault env
backups (all three stored tokens are Prekzursil) — the token must come from
home or be minted.

### Mirror-pending convention

When the primary link is down, session deltas accumulate as
`D:\opt\vault\mirror-pending\<date>.tar.gz` and drain via
`D:\opt\scripts\push-home-mirror.ps1` (which self-reports the exact wake-side
fix if home is unreachable).

---

## Related

- `knowledge/OPEN-LOOPS.md` — the live register; nothing closes without evidence
- `knowledge/policy/2026-09-24-private-estate-plaintext.md` — credential policy SSOT
- `scripts/estate-deny-guard.py` and `scripts/test_estate_deny_guard.py` — the
  guard and its 11-case suite
