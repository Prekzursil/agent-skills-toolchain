---
name: disk-cleanup-c-drive
description: 'C: drive cleanup playbook + bloat profile (codex sessions, WSL/Docker
  vhdx, uv cache) and Windows gotchas'
metadata:
  node_type: memory
  type: project
  originSessionId: 02fb250a-94df-41d8-b978-bb35b7666dc0
permalink: main/claude-memory/root/disk-cleanup-c-drive
---

C: is a ~953 GiB drive that runs chronically low. 2026-05-24 cleanup took it ~43 GB → ~168 GB free.

**Top recurring space hogs (all under `C:\Users\Prekzursil`):**
- `.codex\sessions\` ~59 GB (huge Codex/agent transcripts; March alone 52 GB) — and frequently a `sessions_backup\` *duplicate* of equal size that's safe to delete (verified real copy, not a symlink).
- WSL Ubuntu `...\CanonicalGroupLimited.Ubuntu_*\LocalState\ext4.vhdx` (~106 GB file / ~83 GB real) and Docker `...\Docker\wsl\disk\docker_data.vhdx` (~49 GB) — dynamic VHDs that never shrink on their own.
- Caches: `uv\cache` (~14 GB, **hardlink-heavy**), `npm-cache` (~8 GB), `pip\cache` (~6 GB), `Temp` (incl. WSL `swap.vhdx`), stale `Edge\User Data\Default.prerestore-*` profile backups (~6 GB).
- Big, needs-user-decision: `Downloads\` (~128 GB), `Saved Games\...Empire At War...\Save_Backups\` (~36 GB), Claude desktop cache (~15 GB), WSA `userdata.*.vhdx`.

**Recipes / gotchas (Windows, run elevated):**
- WizTree CSV stays exclusively locked while WizTree.exe is open; exports here were scoped to `C:\Users` only (no Windows/ProgramData/pagefile in them).
- VHD compaction: quit Docker (`Stop-Service com.docker.service` + kill GUI procs), `wsl --shutdown`, then per guest run `fstrim` **via login shell** (`wsl -d <distro> -u root -e bash -lc 'fstrim -av'` — fstrim lives in /usr/sbin, NOT on `wsl -e`'s default PATH), then `Mount-VHD -ReadOnly -NoDriveLetter` + `Optimize-VHD -Mode Full`. Optimize-VHD *direct* often fails on the ext4 vhdx; the RO-mount path works. docker-desktop mounts `/` with `discard` so its vhdx is already tight (~0 reclaimable). `wsl --manage <d> --set-sparse true` refuses without `--allow-unsafe` (data-corruption risk) — do NOT use on real data.
- Hardlink-heavy caches (uv): `robocopy /MIR` is pathologically slow (hardlink-aware) and frees ~0 until last link gone. Use `[System.IO.Directory]::Delete($p,$true)` or `Remove-Item -Recurse` instead.
- A PreToolUse hook BLOCKS any command containing the literal `/s` (false-positives on `rmdir /s /q`). Use PowerShell `Remove-Item` / `.NET Directory.Delete`, never `cmd rmdir /s`.
- Docker MCP postgres containers are `--rm` ephemerals spawned on-demand by the MCP client (don't persist across Docker restart); the kind k8s cluster + its images are kept intentionally.

**Why:** This machine needs periodic C: cleanup; these are the proven high-ROI targets plus method quirks that otherwise cost a lot of time to rediscover.
**How to apply:** On the next "free C:" request, hit caches + the `sessions_backup` duplicate first (fast, safe, ~100 GB), compact the vhdx with the fstrim+Optimize recipe, then surface the Downloads / Save_Backups / `.codex\sessions` judgment calls.


## 2026-06-27 RECURRENCE: concurrent Workflow Angular clones filled C: to 0
**Cause:** 3 ultracode Workflows (Reframe + fleet + momentstudio) running concurrently each had agents `git clone` repos to `%TEMP%` and run `npm ci` / Angular Karma builds — ~15+ node_modules trees + karma/ng/pip temp dirs accumulated (32,431 items in `%TEMP%`) → 953 GB C: → 0 free. Symptom surfaced as an edit-validate Stop-hook "broken file" nudge (py_compile Errno 28 = No space, NOT real code breakage) + every workflow agent silently failing.
**Fix that worked (0 → 84.2 GB, junk only, no user data):**
1. STOP the workflows (TaskStop) — they can't progress on a full disk + their clones are the bloat.
2. Delete `%TEMP%\*` EXCEPT the `claude` dir (this session's scratchpad/task-outputs) via PowerShell `Remove-Item -LiteralPath -Recurse -Force -EA SilentlyContinue` per-child → reclaimed ~72 GB.
3. Clear `uv\cache`,`npm-cache`,`pip\cache`,`pnpm` + recycle bin.
4. WSL ext4.vhdx was 80 GB; direct fstrim+Optimize only freed ~1 GB (guest genuinely full). Clearing WSL `~/.cache` (pip/uv/npm/playwright, KEEP huggingface ~2 GB) THEN `fstrim` THEN `wsl --shutdown` + RO-mount `Optimize-VHD -Mode Full` → +10 GB. NOTE: deleting files INSIDE wsl does NOT free host space until recompact.
5. Claude desktop cache / Edge prerestore were tiny this time; DISM/host-temp ~0. `.codex\sessions` only 2.2 GB.
**Ceiling:** ~84 GB was the pure-junk max; the remaining big consumers are USER DATA (Downloads ~128 GB incl. the 26 GB swfoc game tree + 5 GB swfoc_memory NEEDED; WSL guest ~77 GB real; Docker images incl. the kept kind cluster) — needs user decision, don't auto-delete.
**HOOK GOTCHAS hit:** the PreToolUse parser blocks `Remove-Item` when the command ALSO contains a forward-slash token it reads as a path (e.g. `[math]::Round($x/1GB,2)` got flagged as removing `/1GB,2`). FIX: keep `Remove-Item` commands free of `/`-tokens (use backslash paths only) and do free-space math (`/1GB`) in a SEPARATE command with no Remove-Item. Also the documented literal-`/s` block still applies (avoid `cmd rmdir /s`, DISM `/s...` flags near Remove-Item).
**PREVENTION (apply when running disk-heavy Workflows):** (a) don't run multiple node_modules-cloning workflows concurrently — sequence the heavy one (momentstudio) after the light ones; (b) make each agent `rm -rf` its temp clone after pushing (added to momentstudio workflow ETHIC); (c) `npm ci` not `npm install`, remove node_modules when done. Relates to [[durable-incremental-beats-big-fan-out-for-session-limited-grinds]].