---
title: hook-experiment-PROTOCOL
type: note
permalink: dqverify-repo-20261013/cyberstrike/plugin/hook-experiment-protocol
---

# hook-experiment.ts — owner-assisted protocol for sleep/throw modes (2026-09-22)

**Lane:** cs-sota experiments · **Status:** DOCUMENTED, NOT RUN (destructive modes never run
in the owner live TUI session — this file is the handoff). Default mode `log` is passive and
safe; the live TUI (started 2026-09-22T14:30) runs it (`plugin/hook-experiment.log:1`
`"mode":"log"`).

## 0. What the experiment settles (static findings from cyberstrike.exe v1.1.16, 2026-09-20)

| Mode | Static claim to confirm/refute at runtime |
|---|---|
| `log` | Loader proof: config `plugin` array with **file:// URL** loads the plugin (VERIFIED live: TUI log `2026-09-22T143008.log:32` + `plugin/hook-experiment.log:1`). |
| `sleep` | `Plugin.trigger` (binary L756266) awaits hooks with NO timeout/race → a sleeping `tool.execute.before` delays the call by the full sleep; the host never truncates. |
| `throw` | Tool processors wrap execute in try/catch (binary L571711) → a throw becomes `status:"error"` tool part + `{success:false}`; process survives; turn continues (exit-2-equivalent denial, fail-open). |

Refutation signals: a shorter-than-sleep delta or host-side cancel = dispatcher timeout EXISTS
(refutes sleep claim); a frozen TUI or dead process = denial is NOT fail-open (refutes throw claim).

## 1. Hard preconditions (do not skip)

1. **RAM gate (G-26):** free RAM > 8 GB — check the statusline `mem%` segment or
   `systeminfo | findstr Available` before restarting anything.
2. **TUI restart is an owner-chosen boundary** (live session policy): pick a moment with no
   engagement in flight. Never restart the TUI to run this while an operation is live.
3. **Plugin must be mounted** in `cyberstrike.json` at TUI start. The array entry MUST be the
   file:// URL form — the bare-path string form boot-crashes the server
   (`bun add <path>@latest` → MissingPackageJSON → BunInstallFailedError cascade; anchor log
   `~/.local/share/cyberstrike/log/2026-09-20T230623.log`, commit `04aff13`):

   ```json
   "plugin": ["file:///C:/Users/Prekzursil/.config/cyberstrike/plugin/hook-experiment.ts"]
   ```

   NOTE: HEAD (04aff13) currently has NO plugin array (it removed the crashing bare-path
   entry). The file:// form is proven-safe by the live 14:30 session.

## 2. Why the env var needs a RESTART (read this or the run proves nothing)

`MODE` and `SLEEP_MS` are read **once at plugin load time** (module-scope `const` in
`hook-experiment.ts:39-40`). Setting `CS_HOOK_EXP_MODE` in a shell AFTER the TUI is running
does nothing — the TUI process env was fixed at its start. Every mode change = one TUI restart.

## 3. Owner-assisted run protocol (per mode, ~5 min each)

### 3a. sleep mode

```powershell
# from the shell that will LAUNCH the TUI (child inherits the env):
$env:CS_HOOK_EXP_MODE  = "sleep"
$env:CS_HOOK_EXP_SLEEP_MS = "8000"   # default 8000; keep small on a RAM-pressed box
# launch the TUI from THIS shell (adjust to your normal launch command):
cyberstrike
```

1. Verify load: fresh line in `~/.config/cyberstrike/plugin/hook-experiment.log`
   with `"mode":"sleep"`. If it says `"mode":"log"` the env did not reach the process —
   stop, relaunch from the env-bearing shell.
2. Trigger ONE cheap tool call in the CS session (e.g. ask the agent to read a small file,
   or a `run: echo ping` with a free model). Nothing heavier.
3. READ the log (stop-and-report: re-read the file, do not re-run anything):
   - EXPECT `tool.execute.before:start` then `tool.execute.before:end` with
     `elapsedMs ≈ CS_HOOK_EXP_SLEEP_MS` (±200 ms), and the tool result arriving AFTER the
     delay, TUI responsive.
4. Copy the log lines to the receipts tree:
   `D:/bolt/admin-crack-2026-09-19/raw/cs-sota/hook-exp-sleep_<date>.log`.

### 3b. throw mode

```powershell
$env:CS_HOOK_EXP_MODE = "throw"   # separate restart; unset SLEEP_MS is fine (unused)
cyberstrike
```

1. Verify `"mode":"throw"` in the log (same check as above).
2. Trigger ONE tool call.
   - EXPECT an errored tool part containing `CS hook-experiment intentional deny (mode=throw,
     callID=...)`, the TUI stays alive, the turn continues.
3. Save the log to `.../cs-sota/hook-exp-throw_<date>.log`.

### 3c. cleanup / rollback (after both modes)

1. Restart the TUI WITHOUT the env vars (mode falls back to passive `log`), or remove the
   plugin array entry if the experiment is over — config-only, reversible either way.
2. Keep `plugin/hook-experiment.ts` + the logs as evidence; record the two verdicts
   (CONFIRMED/REFUTED per mode) in the run receipt.

## 4. Safety notes

- `sleep`/`throw` apply to EVERY `tool.execute.before` in the session while active — that is
  why they are never run in the owner's live working session, only in a dedicated restart.
- The `event` observer channel handler never throws (dispatch is unawaited/uncaught, binary
  L756291 — an exception there would be an unhandled rejection).
- No network, no credential data; the log writes tool names + callIDs only.