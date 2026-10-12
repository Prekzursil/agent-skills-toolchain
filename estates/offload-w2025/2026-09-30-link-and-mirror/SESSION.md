# Session: link restoration, home-work audit, mirror staging (2026-09-30, ZCode on VM)

The VM-side session that paired with home's Claude session (same night, both
working the bilateral link). This documents what THIS session did and verified,
per the estate convention that every handling session leaves a record.

## 1. VM-side link restoration (executed before home's session was seen)

Home sent a 5-step admin runbook; executed via the elevated runner and verified:
- `home_to_vm@desktop-a60s9gp` key deployed to BOTH authorized_keys files (the
  admin-file path is load-bearing); icacls locked; sshd restarted.
- `serve.cmd` launched: listeners live on `100.117.115.55:2022` (C:) and `:2023`
  (D:) — tailnet-IP binding only, netstat shows no 0.0.0.0 for the link.
- Tasks `vm-link-serve` / `vm-link-serve-logon` registered (SYSTEM/highest,
  boot+logon, 3x restart); sshd+WinRM Automatic.
- `rclone` added to the reaper whitelist (was absent — serve would have died
  within 30 min of the next sweep).
- Full report collected to `vm-link-report.txt` (the exact outputs home asked
  for, pasted back in-session).

## 2. Audit of home's session (from the VM side)

Home's work audited against what the VM observes:
- **Configuration: correct on every verifiable point.** His serve instances,
  `vm-link-sftp-tailscale*` firewall rules, task wiring, and reaper dry-run
  (would-kill 0) all match the designed topology; his grounding rediscovered the
  same architecture the VM side uses (rclone sftp, key auth, TS-IP binding).
- **His one misread, corrected:** he treated his failed local self-test
  (python TCP to own TS IP) as a harmless hairpin artifact. Cross-machine
  testing shows the same failure — the actual cause is home entering standby
  after his session ended (~00:41 home time). Signature: `active; relay` +
  `tailscale ping` timeout + all ports closed. Config untouched by this — it
  will answer on wake. Both lessons are now in the estate-sync skill.
- His blockers (gcloud billing wall on webcoder-462916, CredRead SSO-stub)
  are real and remain owner-side; note the VM already had the key deployed by
  the runbook, so home→VM SSH works without the metadata path the moment he
  retries with `ssh -i ~/.ssh/home_to_vm prekzursil@100.117.115.55`.

## 3. Mirror staging (ovido4)

- Bare 1:1 mirror staged at `D:\opt\vault\mirror-push\agent-skills-toolchain.git`
  (766 refs, all branches/tags from Prekzursil/agent-skills-toolchain).
- `push-mirror-to-ovido4.sh` = one-command activation once an ovido4 GitHub
  token exists (creates private repo if absent, `git push --mirror`, prints
  ref count). Mirror-not-sync semantics by design.
- **Blocked:** no ovido4 GitHub credential on the VM or in the vault env
  backups (all three stored tokens — GH_TOKEN, GITHUB_TOKEN, GITHUB_MCP_PAT —
  verified as Prekzursil's). Token must come from home or be minted.

## 4. Skill and repo state

- `skills/estate-sync/` did not exist in the repo (live-only skill — drift).
  Now committed with today's additions: the VM-side runbook, the standby-vs-
  config diagnostics, and the ovido4-mirror section.
- Home mirror of session deltas: still pending home wake
  (`push-home-mirror.ps1` staged with tarball).

## Session lineage

ZCode session on offload-w2025; fleet runs dwfrun-768d32c7 → dwfrun-16020bbf
(completed); vault branch vm/offload-w2025-2026-09-29-offensive-stack
(058bb9de..7ba1aba1); main merged at 76cf0e88 (+ this commit).
