# Hide Scheduled-Task terminal pop-ups — 2026-09-17

## Problem
Console windows (PowerShell / cmd / python) kept flashing on the desktop during gameplay.
Cause: ~26 estate Scheduled Tasks run console programs in the **Interactive** session, several
on short repeat intervals (BoltLakeInterceptor every 2 min, CursorBridgeDrainer/CyberStrikeMcpWatchdog
every 5 min, MCP/ClaudeScience supervisors every 10 min, hourly Bolt watchers, plus once-at-logon
flashers). `-WindowStyle Hidden` on `powershell.exe` still flashes a console briefly, and many
tasks had no hiding at all.

## Why the usual VBScript trick was NOT used
This Windows build (10.0.29648) has **removed the VBScript engine** — no `VBScript.RegExp` CLSID and
no `vbscript.dll` in System32/SysWOW64. `wscript`/`cscript` fail with *"Can't find script engine
VBScript"*, so any `.vbs` hidden launcher silently breaks the task. (Confirmed by test: a VBS-wrapped
task returned exit 1 and never ran its command.)

## Fix
`runhidden.exe` — a tiny GUI-subsystem launcher (`C:\Users\Prekzursil\.local\opt\hidden-launchers\`).
It `CreateProcess()`es the original command with the `CREATE_NO_WINDOW` flag, waits, and returns the
child's exit code. Each task's action was rewritten from:

    Execute = <exe>            Arguments = <args>
to:
    Execute = runhidden.exe    Arguments = "<exe>" <args>   (verbatim, exe re-quoted if spaced)

Because the task still runs as **Interactive** with the same working directory, the child keeps the
identical session, environment, DPAPI/credential access, network access and desktop access — only the
console window is suppressed. Exit-code and single-instance semantics are preserved (runhidden waits
and returns the real exit code).

## Scope
- **23 tasks wrapped** — see `backup\*.xml` (one pristine backup per task; filename = task name).
- **3 deliberately left untouched:**
  - `cua-driver-serve` — launches a GUI via Start-Process (needs the visible desktop); only flashes
    once at logon and is already `-WindowStyle Hidden`.
  - `CS-TUI-BoltOkta`, `CS-TUI-BoltOktaNew` — interactive terminal UIs with **no auto-trigger**
    (only run when you start them manually), so they never pop up on their own.
- Vendor GUI updater tasks (Driver Booster, ASUS, SmartDefrag, NVIDIA, Edge/Google/Comet, Ubisoft)
  are **not** terminals and were out of scope.

## Files
- `runhidden.exe` / `runhidden.cs`  — the launcher + its source (`.local\opt\hidden-launchers\`).
- `hide-terminals.ps1`              — generator/reverter. `-Tasks <names>` wraps; add `-Revert` to undo.
- `revert-all.ps1`                  — reverts every wrapped task from backup in one call.
- `backup\<task>.xml`               — pristine task definitions before wrapping.

## Verification (2026-09-18)
- 23/23 tasks now execute via runhidden.exe; 23 backups present; 3 excluded tasks untouched.
- runhidden proven: exit-code propagation (7), quoted spaced-path exe + real file side effect (0),
  BoltLakeInterceptor live (result 0), GuardTracerRound end-to-end (result 0), HarnessRecallRefresh (0).
- Triggers and Interactive principal confirmed unchanged (only the action was replaced).

## Undo
    powershell -File revert-all.ps1        # all tasks
    powershell -File hide-terminals.ps1 -Tasks 'TaskName' -Revert   # one task

## Add more tasks later
    powershell -File hide-terminals.ps1 -Tasks 'NewTaskA','NewTaskB'
(Idempotent: already-wrapped tasks report SKIP. Only wraps console-program actions.)
