---
title: VBScript removed on this box; runhidden.exe hides scheduled-task terminals
  (2026-09-17)
type: note
permalink: main/reference/vbscript-removed-on-this-box-runhidden.exe-hides-scheduled-task-terminals-2026-09-17
---

# VBScript removed; runhidden.exe hides scheduled-task terminal pop-ups

Context: owner reported console windows (PowerShell/cmd/python) flashing on the desktop during
gameplay. Root cause = ~26 estate Scheduled Tasks running console programs in the **Interactive**
session, several on short repeat intervals. Fixed 2026-09-17/18.

## Observations
- [fact] This Windows build (10.0.29648) has **VBScript fully removed**: no `VBScript.RegExp` CLSID,
  no `vbscript.dll` in System32 or SysWOW64. `wscript`/`cscript` fail with "Can't find script engine
  VBScript". Any `.vbs`-based hidden launcher SILENTLY BREAKS the task (returns exit 1, never runs the
  command). The classic `WScript.Shell.Run(cmd,0,True)` hide trick is DEAD on this machine.
- [decision] Hidden-launch method = `runhidden.exe`, a GUI-subsystem C# helper at
  `C:\Users\Prekzursil\.local\opt\hidden-launchers\runhidden.exe` (source `runhidden.cs` beside it).
  It `CreateProcess()`es the original command with `CREATE_NO_WINDOW`, waits, returns the child exit
  code. Compiled with `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /target:winexe`.
- [fact] Task action rewritten from `Execute=<exe> Args=<args>` to
  `Execute=runhidden.exe  Args="<exe>" <args>` (exe re-quoted if spaced). LogonType stays
  **Interactive**, so session/env/DPAPI/network/desktop and exit-code + single-instance semantics are
  all preserved — only the window is suppressed. Verified: only the action changed; triggers+principal intact.
- [fact] 23 tasks wrapped (recurring in-game offenders BoltLakeInterceptor PT2M, CursorBridgeDrainer
  PT5M, CyberStrikeMcpWatchdog PT5M, MCPAgentMailSupervisor + ClaudeScienceWatchdog PT10M, hourly
  BoltWatches/CursorQuotaProbe, PT6H Bolt-Vuln-Audit-Ralph/HarnessRecallRefresh, plus once/logon
  flashers). Backups + generator + revert live in
  `C:\Users\Prekzursil\.agents\maintenance\hide-terminals-2026-09-17\` (see README.md there).
- [fact] 3 tasks deliberately NOT wrapped: `cua-driver-serve` (Start-Process a GUI, needs visible
  desktop; only flashes once at logon), `CS-TUI-BoltOkta` + `CS-TUI-BoltOktaNew` (interactive TUIs
  with NO auto-trigger — they never pop up unless started manually).
- [fact] GOTCHA: a leading space in the command line passed to `CreateProcess(NULL, cmdline)` makes it
  fail with ERROR_INVALID_PARAMETER (87). Must `.Trim()` the child command line. This was the whole
  reason the first runhidden build returned 87 and ran nothing.
- [fact] GOTCHA: the estate PowerShell PreToolUse guard blocks any command that combines a delete call
  (`Remove-Item`, `[IO.File]::Delete`) with a `/`-prefixed token in the same command — it misreads
  `/nologo`, `/c`, `/target` as a "system path" being removed ("Remove-Item on system path '/nologo'
  is blocked"). Keep `csc /flags` compiles and file deletions in SEPARATE commands.
- [decision] Preferred hide method on this estate going forward = runhidden.exe wrap (keeps Interactive
  session), NOT LogonType->S4U (S4U runs in session 0 and cannot decrypt user-scope DPAPI secrets, so
  it can silently break credential/session tasks — violates the owner "never downgrade capability" rule).

## Undo / extend
- Revert all: `powershell -File revert-all.ps1` in the maintenance folder.
- Revert one: `hide-terminals.ps1 -Tasks '<name>' -Revert`.
- Wrap more later: `hide-terminals.ps1 -Tasks '<name>'` (idempotent; SKIPs already-wrapped).

Relates to [[Windows shell non-negotiables]] and estate scheduled-task automation.
