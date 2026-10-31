---
name: vm-link
description: Persistent bilateral home<->offload-VM access over Tailscale (SSH + rclone
  sftp disk share + reverse tunnel for the blocked direction). Use when establishing,
  verifying, or repairing the VM link, or when jumping/mirroring VMs (e.g. offload-w2025
  -> ovido4).
version: 1.0.0
created: 2026-10-01
tags:
- infrastructure
- tailscale
- rclone
- ssh
- vm
permalink: dqverify-repo-20261013/skills/vm-link/skill
---

# vm-link — bilateral VM access discipline

Estate pattern (proven 2026-10-01 on offload-w2025): home ↔ VM over the
tailnet, file access both directions, everything task-wired, reaper-safe,
VM-agnostic (all binds resolve the CURRENT tailscale IP at runtime).

## Topology

```
home→VM shell+files : ssh (key home_to_vm) → VM :22; rclone sftp VM:2022/2023 (C:/D:)
VM→home files       : reverse tunnel — VM localhost:21022/21023
                      → (ssh -R over the WORKING home→VM direction)
                      → home loopback serves 127.0.0.1:21222/21223 (C:/D:)
VM→home DIRECT data : BLOCKED (mystery: disco pongs, zero packets at home
                      stack; firewall/ShieldsUp verified clean) — tunnel
                      bypasses it permanently. Do NOT re-litigate; check
                      tailnet admin ACLs if ever curious.
```

## Home side (C:\ProgramData\vm-link\)

| File | Role |
|---|---|
| `target.conf` | `user host` (e.g. `prekzursil offload-w2025`) — THE jump pointer. MagicDNS name preferred (survives IP changes) |
| `home-link-serve.cmd` | TS-IP-bound rclone serves 2022/2023 (computed at runtime) |
| `home-link-tunnel.cmd` v2 | loopback serves 21222/21223 + `ssh -R` 21022/21023 → VM; retry loop re-reads `target.conf` each pass |
| `home_to_vm` (+ `.pub` in VM's authorized_keys) | SYSTEM-readable key copy (user-profile keys are NOT readable by the task) |
| `authorized_keys` + `host_ed25519` | rclone sftp auth (VM's key `vm_to_home@offload-w2025` allow-listed) |

Scheduled tasks (SYSTEM, boot+logon): `home-link-serve`, `home-link-serve-logon`,
`home-link-tunnel`, `home-link-tunnel-logon`.

## VM side (C:\ProgramData\vm-link\ on each VM)

| File | Role |
|---|---|
| `serve.cmd` v2 (dynamic) | computes `tailscale ip -4` at runtime, port-guarded starts of C: on :2022 + D: on :2023 — **mirror-proof** (old hardcoded version kept as `serve.cmd.bak-hardcoded`) |
| `authorized_keys` + `host_ed25519` | rclone auth (contains home's `home_to_vm` pub via user/admin authorized_keys for SSH) |

Scheduled tasks (SYSTEM, boot+logon): `vm-link-serve`, `vm-link-serve-logon`.
sshd + WinRM StartType=Automatic. Reaper whitelist has `rclone` (VM) / `vm-link` (home).

## Verify (the audit battery)

```powershell
pwsh ~/source/agent-skills-toolchain/skills/vm-link/verify.ps1
# or, on the deployed tree: pwsh ~/.agents/skills/vm-link/verify.ps1
```
Terminal line: `SUCCESS:vm-link-verify` / `FAILED:vm-link-verify fail=N`.
Checks: home→VM ssh, VM serves :2022/:2023, tunnel task Running, 4/4 home
listeners, serve tasks armed, reaper whitelist needle.

## Jumping / mirroring VMs (runbook)

**Mirror case (1:1 disk copy, e.g. offload-w2025 → ovido4):**
1. On the NEW VM: `tailscale up` (cloned tailscaled state must be re-authed;
   the node gets a NEW tailnet IP — everything else survives the image).
2. Home: update `C:\ProgramData\vm-link\target.conf` → `prekzursil <new-name-or-ip>`.
3. Kill the tunnel ssh (pid from `verify.ps1` context or task restart):
   `Stop-ScheduledTask home-link-tunnel; Start-ScheduledTask home-link-tunnel`.
4. Run `verify.ps1` → SUCCESS required.
5. VM side needs NOTHING — serve.cmd computes its new IP at boot (task).

**Fresh VM case:** deploy the two scripts + tasks (see VM side table), add
`home_to_vm.pub` to user + `administrators_authorized_keys` (icacls
inheritance:r Administrators:F SYSTEM:F), then home steps 2–4 above.

## Gotchas ledger (all ledger-proven 2026-10-01)

- **SYSTEM tasks cannot read user-profile keys** — tunnel died silently until
  the key moved to `C:\ProgramData\vm-link\home_to_vm` with SYSTEM ACLs.
- **Test-NetConnection lies under RAM pressure** (false-closed on known-open
  ports, both machines) — use raw TcpClient (see verify.ps1).
- **Local connect to own tailscale-IP times out** (weak-host off) — that is
  NORMAL, not a serve outage; only cross-node connects prove serving.
- **GCP writes (setMetadata / reset-password) 403 "requires billing" even
  with billing linked** on webcoder-4626 — reads work, writes refuse. Don't
  burn time; use the VM-side agent or RDP instead.
- **Saved RDP credentials are SSO stubs** (empty blob in user context) —
  CredRead gives nothing; don't mine, route around.
- **UAC secure desktop blocks synthetic keystrokes** — UIA-driving an RDP
  session cannot elevate; write user-level files instead.
- `rclone`/`ssh`/`vm-link` processes are dead-parent-by-design under their
  tasks — they live in BOTH reaper whitelists; do not prune.

## Never

- Never bind serves to 0.0.0.0 (tailnet IP or loopback only).
- Never delete `target.conf` semantics away — it is THE jump pointer.
- Never "fix" the VM→home direct blockage by disabling the home firewall —
  the tunnel is the sanctioned bypass.