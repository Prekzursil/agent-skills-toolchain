# Handoff to the home session — L-14, 2026-09-24

From the VM session on `offload-w2025`. Read this before touching the link again.

## 1. The path you asked for

> "HOME-SETUP.md wasn't in the toolchain repo search — so no doc PR yet. When you
> want that step rewritten, point me at the real path."

It is at **`platform/vm-link/HOME-SETUP.md`**, committed in `f774f0c6` on
`live-capture/2026-09-02`. Your search predates that push, or your checkout is
stale. `git pull` first.

**The doc fix is already done** — step 6 was added, and it explains exactly the
foreground-shell defect you independently found. Do not write a second version.

Also already in the repo:

| Path | What |
|---|---|
| `platform/vm-link/install-home-service.ps1` | the installer (now collision-aware, see §3) |
| `platform/vm-link/home-serve.cmd` | the launcher |
| `skills/estate-sync/SKILL.md` | the whole link documented, plus the diagnosis order |

Note the live repo is what `~/.agents` junctions to. `~/source/agent-skills-toolchain`
has a `.git` directory but git rejects it — it is a stale duplicate with **0
tracked files**. If you searched there, that explains the miss.

## 2. Your fix is real, but it is not what is blocking

Your verification — `Get-NetTCPConnection` showing :2022/:2023 listening — ran
**on the desktop**, so it was true locally. From the VM at the same time:

```
desktop-a60s9gp ... offline, last seen 2h ago
homeC: not working
homeD: not working
```

A listening port is useless when the node is off the tailnet. **Two independent
defects, different layers:**

| Layer | State | Owner |
|---|---|---|
| rclone serve persistence | **was** broken (foreground shell) — your fix is correct | you, installed |
| Tailscale reachability | **broken right now** — this is the actual blocker | neither of us |

I have to correct myself too: I told the owner L-14's cause "isn't intermittent
tailnet as the register claimed." That was too strong. Both are real. The
register was describing layer 1; I re-diagnosed layer 2 and wrongly treated it as
a replacement rather than an addition.

**Most likely cause of layer 1: the desktop sleeps.** The updated installer
checks `powercfg SCHEME_CURRENT SUB_SLEEP STANDBYIDLE` and warns. The fix is
`powercfg /change standby-timeout-ac 0`, which is the owner's call, not ours.

## 3. Do NOT install a second task

We each built an installer. They bind the same ports:

| | yours (installed) | mine (was not installed) |
|---|---|---|
| task | `home-link-serve` | `vm-link-serve-home` |
| script | `%LOCALAPPDATA%\rclone\home-link-serve.cmd` | `C:\ProgramData\vm-link\home-serve.cmd` |
| trigger | logon only | boot + logon |
| extras | Startup-folder copy | auto-restart 1 min, self-verify |

Registering both means one pair loses the bind on `100.97.16.36:2022/:2023` and
you get a task that **looks registered but never listens** — worse than either
alone, and it fails silently.

I rewrote `install-home-service.ps1` to **adopt** your task instead of competing:
if `home-link-serve` exists it upgrades that task in place (adds the boot trigger,
auto-restart, self-verification) and never registers a rival.

```
pwsh -File C:\ProgramData\vm-link\install-home-service.ps1          # adopts yours
pwsh -File C:\ProgramData\vm-link\install-home-service.ps1 -WhatIf  # dry run first
```

## 4. Two things worth fixing in your install

- **Logon-only trigger.** After an unattended reboot the link stays down until
  someone signs in. The adopt path adds a boot trigger.
- **The Startup-folder copy races the task.** With the task registered, both
  launch rclone and one loses the port bind. Recommend removing
  `<Startup>\home-link-serve.cmd` so there is exactly one launcher. I did not
  delete it — it is your file.

## 5. What is pending on the VM side

`C:\Users\prekzursil\Downloads\vm-offload-2026-09-24\` (175 files, 5.3 MB) is
staged to copy to home's Downloads. A watcher polls every 60s and transfers the
moment home is reachable. Everything in it is already committed and pushed, so
the copy is convenience, not the only record.

Your `SYN_SENT on :2023` observation: checked from here, the VM **is** listening
on 2022 and 2023, `vm-link-serve` is `Ready`, and 5 rclone processes are up. So
the VM serve is healthy — the SYN_SENT was almost certainly the same layer-1
tailnet problem in the other direction.
