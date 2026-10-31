---
permalink: dqverify-repo-20261013/rules/common/windows-shell
---

# Windows-Shell Footguns (non-negotiables)

Windows 11 · **PowerShell 7** (primary) + **Git Bash / MSYS** (POSIX). Every item is
ledger-proven; each cost real data loss (a wiped save, broken CI, mangled release refs).
Cross-tool: Codex CLI and Antigravity do **not** read `~/.claude/rules/`, and the
codex-orchestrator bootstrap REPLACES `$CODEX_HOME/AGENTS.md` on every install/update —
re-apply the pointer afterwards.

**Full incident evidence, measurements and repro steps:**
`~/.agents/knowledge/rule-evidence/windows-shell-full.md` — read it when a rule below
surprises you or you need the numbers.

## Silent-data-loss class

1. **MSYS rewrites `/…` args.** Git Bash converts `/sdcard/x`, `/data/…`, `/c/…` into
   Windows paths before the program sees them. Combined with a redirect, the shell opens
   the target for write — **truncating it to 0 bytes BEFORE the failed source read**.
   → `export MSYS_NO_PATHCONV=1` around POSIX-arg commands (adb/docker/ssh), or use
   PowerShell. **Always verify after a write** (size/md5); the empty state is silent.
2. **`New-Item -ItemType File -Force` on an existing file RECREATES IT EMPTY.** `-Force`
   means truncate, not "ensure exists". → guard with `Test-Path`; write via
   `Set-Content`/`Out-File`/the Write tool. Never use it as a touch.
3. **Device round-trips (adb, `/data`, `/sdcard`) — worst case of #1.** Do them in
   PowerShell, back up on-device first (`cp SAVE SAVE.before-<ts>`), `md5sum` after every
   write.
4. **`MSYS_NO_PATHCONV=1` must be SCOPED, never global.** Global suppression also kills
   the conversion legitimate `/c/Users/...` PATH args depend on — a `git clone` silently
   did not happen and every downstream probe read as failure. Apply it only around
   REVISION arguments (`origin/main:path`, `HEAD^`, pathspecs).
5. **PowerShell `${drive:...}` inside braces is a PROVIDER PATH, not a variable.**
   `${C:\out} = $data` **writes that file**; `${C:\in}` reads it. → keep the colon
   outside the braces: `"${C}:\path"`, or `$($C):\path`. Applies to any `A:`–`Z:` and to
   `global: local: script: private: env: variable: function:`.

## Git / ref class

6. **PowerShell `^` is the escape character** — `git rev-parse v1.4.1^{commit}` corrupts.
   → `git rev-list -n 1 <tag>`, or single-quote the whole ref. Same for `HEAD^`, `~^`.
7. **Never pass backslash paths as git revisions or pathspecs.** → forward slashes and the
   `--` separator: `git show origin/main:path/to/file`.
8. **`git diff origin/main...HEAD --stat` before EVERY PR** (three dots — plain `git diff
   origin/main` folds in working-tree noise). A stale branch proposes mass deletion:
   measured 1,188 files / 316,222 deletions, reduced to 7 files / 4 deletions by
   cherry-picking onto a fresh branch.

## CRLF class

9. **Agent-written `.sh` carry CRLF; real WSL/Linux bash REJECTS them** (Git Bash
   tolerates, so `bash -n` there passes while the script is broken). → `*.sh eol=lf` in
   `.gitattributes`; verify with `wsl.exe bash -n script.sh`.
10. **A Windows-local formatter/linter green does NOT imply CI-green.** Git stores LF, CI
    checks out LF, your working tree is CRLF — formatters decide differently on the two.
    → verify against the BLOB: `git cat-file -p <rev>:<path>` or `git show <rev>:<path>`.
    **NEVER `git archive` for this — on Windows it re-applies CRLF and hands back the
    OPPOSITE of the blob** (measured: archive 3,837 B / 100 CRLF vs cat-file 3,737 B / 0).
    Pin tool versions (`uvx tool@<pinned>`); ambient versions format differently.
    Your own edit scripts inherit this: reading with `newline=""` keeps `\r\n`, so a
    pattern written with `\n` matches 0 times.

## Tool-transport class

11. **A here-string PAYLOAD is scanned as if it were a command.** `Set-Content -Value
    @'…'@` was blocked as *"Remove-Item on system path '/' is blocked"* because the
    markdown body quoted a destructive command. Measured failure rates: **Write tool
    0.0% (0/40)**, here-string **13.6% (8/59)**, `Set-Content` any form **14.7% (11/75)**.
    → use the **Write tool** for file creation; content travels as a JSON parameter and is
    never scanned. A document containing literal `@'` / `'@` cannot be here-string'd at all.
12. **An apostrophe in a Bash-tool command breaks the tool's OWN quoting** — it wraps your
    command in single quotes, so a literal `'` in a heredoc body, grep pattern or
    `python -c '…'` dies with `unexpected EOF while looking for matching '`. Killed 6+
    consecutive calls in one session. → write to a file and pass the PATH:
    `git commit -F <path>`, `gh pr create --body-file <path>`, `python <script.py>`.
    PowerShell is the escape hatch for git ops. **Two strikes → switch transport, never
    attempt a third escaping variant.**
13. **Bash heredocs mangle backslashes** even under `<<'PY'`: `'\\Users\\'` arrives as
    `'\Users\'` → `SyntaxError`. → Write tool for scripts, then `python <path>`. Reserve
    heredocs for backslash-free payloads.
14. **No bash process substitution `<(…)` in PowerShell** (`The '<' operator is
    reserved`). → write a temp file, pass the path.
15. **Git Bash lacks `bc` and several coreutils.** → `python -c` for arithmetic; check a
    tool exists with `Get-Command` in PowerShell, **not** `which` in Git Bash (misses
    `.cmd` shims).

## SSH / sshd class

16. **Windows `sshd_config` ENDS with `Match Group administrators`** — appending your
    directives silently puts them inside that block and sshd refuses to start
    (`Directive 'ListenAddress' is not allowed within a Match block`). → splice **before
    the first `^\s*Match\s`**, never at EOF. Validate with `sshd.exe -T` (the only
    authoritative check) before restarting.
17. **Admins do NOT use `~/.ssh/authorized_keys`** — they authenticate against
    `C:\ProgramData\ssh\administrators_authorized_keys`, which sshd rejects unless its
    ACLs are SYSTEM + Administrators only:
    `icacls <file> /inheritance:r /grant "Administrators:F" /grant "SYSTEM:F"`.
    Wrong ACLs fail as a silent auth rejection, not an error.
18. **Codex/ChatGPT-desktop over SSH needs THREE fixes and they mask each other** — the
    app shows one string (`SSH connection failed`) for all three. In order: (a) run
    OpenSSH **10.0p2** (Windows' bundled 9.5p2 cannot offer `mlkem768x25519-sha256`);
    (b) populate `known_hosts` (`ssh-keyscan`); (c) set `HKLM:\SOFTWARE\OpenSSH`
    `DefaultShell` to Git bash + `DefaultShellCommandOption` `-c`.
    **`user: (null)` in an sshd log means host-key verification failed, NOT a bad key** —
    no username is ever sent. `Failed publickey for <user>` is the real credential
    rejection. Note `DefaultShell` is global: every SSH client then inherits MSYS path
    conversion (#1).

## Incident-discipline class (2026-09-29, both ledger-proven same night)

19. **Never mass-kill by substring match.** A cleanup needle ('biomni') piped from
    `Where-Object { CommandLine -match }` to `Stop-Process` killed NINE live processes
    incl. brokers started minutes earlier (2026-09-29, ledger #340; same class as the
    2026-07-14 reaper 'hub' collision). → ENUMERATE first (`Get-CimInstance ... | Select
    ProcessId, CommandLine`), read each line, then kill individually by exact PID. A
    kill command whose filter is a substring of a RUNNING component is a bug.
20. **Never rewrite a config you only partially loaded.** A merge script loaded
    `.claude.json`, then wrote back `{'mcpServers': ...}` alone — silently dropping 91
    top-level keys (projects/history). Caught by post-write verify, restored from backup
    (2026-09-29, ledger #341). → load the FULL dict, mutate the key in place, dump the
    FULL dict, then re-open and assert the untouched keys survived. Partial `json.dump`
    of a loaded-subset is data destruction with a success exit code.