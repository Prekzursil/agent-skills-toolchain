# Estate Runtime Runbook: console poppers, front supervision, freeze classes

Live incident knowledge from 2026-10-18 → 2026-10-21, distilled so the next
occurrence is a lookup instead of a forensic night. Companion to the estate
memory (`cyberstrike-mcp-estate-health`); this file is the repo-side canon.

## 1. "Terminals popping" taxonomy (diagnose by parent attribution)

The one instrument that works: a tight WMI birth-capture loop that records
every `cmd/conhost/powershell/WindowsTerminal` spawn **with its parent
process and command line**, run while the popping is happening. Census calls
miss short-lived spawners; task LastRunTime ↔ event-timestamp correlation is
the fallback when the episode already passed.

Verified popper classes on this estate, in observed order of likelihood:

| Class | Signature | Kill |
|---|---|---|
| **Orphaned updater wait-loops** | `cmd /c call ".\<name>.pending.replace.cmd"` (Cursor's `~/AppData/Local/cursor-agent/versions/pending-launchers/`), `ping -n 6` sleep + `tasklist /FI "PID eq X"` + `find "X" <file>` every 5-10s. The script's retry cap depends on parent env vars; dead parent = infinite loop, survives IDE close, re-fires on updater runs. | Kill ALL loop cmds atomically AND move the `pending-launchers` dir away (killing processes alone is whack-a-mole). Files use relative paths — find them by COMMAND LINE, not disk search. |
| **Scheduled-task health guards misfiring** | Guard judges daemon-up by captured OUTPUT of a CLI call; `runhidden`/no-console + stderr-writing clients (Docker 4.96+) break the capture → false "down" → relaunches a UI app (focus steal). | Judge by EXIT CODE (`$LASTEXITCODE`), never by captured output. Never `Start-Process` an already-running app (show-dashboard/pop class). |
| **Over-cadenced tasks** | e.g. route-fixer at PT1M with 4 trigger types; watchdog at PT5M spawning 30s-sweep instances that self-multiply. | Retune to >= PT10M; supervisor `-Once` idempotent passes beat long-lived watcher processes. |
| **Browser native-host reconnect loops** | `cmd.exe` children of `comet.exe`/`msedge.exe`/`chrome.exe` every ~10s with fresh conhost. | Close the browser (session restores); if it resumes on reopen, reinstall the extension/native host. |
| **Default-terminal delegation** | Windows Terminal as default terminal flashes a window for any unhanded console allocation. | Pin `HKCU\Console\%%Start` `DelegationConsole/DelegationTerminal` to conhost GUID `{B23D10C0-E52E-411E-9D5B-C09FDF709C7D}`. |

Forensic gotchas (each cost us a round): WMI `CommandLine -match` self-match
kills your own shell (filter by Name + exclude `$PID`); counts lie when a
chain respawns siblings (enumerate with birth times + parents); `nssm`
restarts whatever it wraps within seconds.

## 2. CyberStrike front supervision (design of record, 2026-10-21)

- Supervisor: `D:\opt\cyberstrike-mcp\start-cyberstrike-mcp-http.ps1`.
  Profiles `Core` (7) / `Full` (30) / `Heavy` (+cloud-audit). **Default is
  Core** — "fleet only loads 7" means someone launched without `-Profile`.
- Supervision = scheduled task `CyberStrikeMcpWatchdog`: supervisor
  `-Once -Profile Full -Include metasploit,cloud-audit` every **15 min**,
  hidden wrapper, 10-min execution cap, `MultipleInstances IgnoreNew`. The
  `-Once` pass is idempotent (port-scan → adopt → start missing → exit); no
  long-lived watcher process, no repair chains.
- The old `watchdog-mcp-estate.ps1` (30s sweeps, self-multiplication,
  orphan `-RepairFront` chains) is RETIRED — do not re-arm it.
- Front health check: real MCP handshake
  (`POST /mcp` with `Accept: application/json, text/event-stream`) — a bare
  POST without the Accept header returns 406 on healthy fronts.

### Metasploit front: the drifting-port trap (2026-10-21 fix)

Windows **dynamic excluded-port ranges drift after every reboot**
(Hyper-V/WSL reservations; `netsh int ipv4 show excludedportrange protocol=tcp`).
A hardcoded daemon port that was bindable yesterday can be EACCES today.
The metasploit front died exactly this way: launcher
`msfmcpd-stdio.py` forced `MSF_API_PORT=55200` (chosen 2026-09-21 when 55553
was excluded) — after the October reboots 55200 fell inside `55181-55280`
while 55553 became bindable. Env vars in the launcher OVERRIDE the yaml —
patch both or you chase ghosts. Fix of record: attach mode against the
durable `MetasploitLoopbackRpc` daemon on 55553 (creds via `MSF_API_*` user
env, shared by design). Any loopback-daemon port on this estate must be
re-checked against the exclusion table after reboot storms.

## 3. Freeze/deadlock classes (sampler-proven)

Commit-eater sampler: task `CommitEaterSampler` →
`D:\opt\commit-sampler\commit-samples.jsonl` (5-min, top-12 private-bytes,
reboot-surviving triggers — a Once-trigger's repetition does NOT survive
reboot; use Boot+Daily triggers with repetition).

| Class | Signature | Named culprits so far |
|---|---|---|
| Commit-ceiling exhaustion | `0xc00000fd` stack-overflow cascade across unrelated processes | Bolt task-fleet churn into a dead network (disabled 10-19) |
| Physical-RAM exhaustion (paging collapse) | commit far below ceiling but physFree 1-2GB for hours | BlueStacks `HD-Player.exe` 7.7GB + `cyberstrike.exe` TUI growth 7→10GB/day + WSL at cap |
| Shutdown hang | winsrvext/VmSwitch storms at restart | 20x cmd.exe blocking shutdown; Hyper-V VmSwitch NIC-teardown flood (14h hang, 10-20) |

Standing doctrine: pagefile bump (67.6→99.6GB ceiling) only cures the first
class; the second is cured by load discipline (never BlueStacks on full
estate; periodic TUI restarts; WSL cap trim is the held lever).
