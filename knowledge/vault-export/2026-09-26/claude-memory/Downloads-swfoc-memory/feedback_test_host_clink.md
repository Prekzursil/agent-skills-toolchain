---
name: Test Host Clink Injection Workaround
description: How to run dotnet test on Windows when Clink is registered as cmd AutoRun
type: feedback
permalink: main/claude-memory/downloads-swfoc-memory/feedback-test-host-clink
---

# Test Host Crashes Due to Clink

## Problem

`dotnet test` crashes the test host with errors like:
```
Test host process crashed : Unable to inject Clink.
A fatal error was encountered. The library 'hostpolicy.dll' required to execute the application was not found in 'C:\Users\Prekzursil\.dotnet'.
The application to execute does not exist: 'C:\Users\Prekzursil\AppData\Local\Temp\swfoc-launch-started-{guid}\corruption\testhost.dll'.
```

The "swfoc-launch-started-{guid}" temp dir is from a Live test that uses `RuntimeAdapter.AttachAsync` to spawn the game. Clink intercepts cmd subprocesses and breaks the testhost process.

## Root Cause

`HKCU\Software\Microsoft\Command Processor\AutoRun` is set to:
```
"C:\Program Files (x86)\clink\clink.bat" inject --autorun --profile ~\clink
```

Every time bash spawns a cmd child, Clink injects. When dotnet test forks testhost, the inject fails on testhost's process and crashes it.

## Why: How to apply

**Why**: bash on Windows uses cmd.exe as the process spawner. Clink hooks every cmd invocation. Setting `CLINK_NOAUTORUN=1` does NOT disable injection because the registry AutoRun still fires before the env var is read.

**How to apply**: Run `dotnet test` via PowerShell `Start-Process` with `-NoNewWindow`. Start-Process spawns the target process directly via Win32 `CreateProcess`, not through cmd. Clink doesn't inject because there's no cmd in the chain.

Working invocation:
```powershell
Start-Process -FilePath "dotnet" `
    -ArgumentList "test","--filter","...","--no-build","--logger","trx" `
    -WorkingDirectory $workDir `
    -NoNewWindow -Wait -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err"
```

The full helper script is at `C:\Users\Prekzursil\Downloads\swfoc_memory\run_editor_tests_v2.ps1`.

## Test Filter

Live tests that need an attached Swfoc process must be excluded — they fail with `ATTACH_NO_PROCESS` when no game is running:
- `LiveSmoke`, `LiveCredits`, `LiveTactical`, `LiveAttach`
- `LivePromotedActionMatrix`, `LiveRoeRuntime`, `LiveHeroHelper`
- `RuntimeAttachSmoke`

`AsyncCommand_TryShowError_DoesNotThrow` previously popped real WPF MessageBox dialogs in the test process. Fixed by adding an `ErrorDisplayHook` static delegate to `AsyncCommand` so tests can swap in a no-op recorder. The hook also short-circuits when `Application.Current is null` (test process).

## Other tests that needed deparalleling

`SupportBundleService.CopyRecentReproBundles` was reading `Directory.GetCurrentDirectory()` to find `TestResults/runs`. Three tests called `Directory.SetCurrentDirectory(workDir)` which is process-global state and broke under xunit parallel execution. Fix: added `WorkingDirectoryOverride` to `SupportBundleRequest`; tests now pass an explicit workspace path instead of mutating CWD.