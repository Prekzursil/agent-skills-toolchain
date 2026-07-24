# Windows-Shell Footguns (non-negotiables)

Cross-tool rule read by Claude Code · Codex CLI · Antigravity (agy). This box is
Windows 11 with two shells in play — **PowerShell 7** (primary) and **Git Bash / MSYS**
(POSIX). Each has a silent-data-loss trap. All five below are LEDGER-PROVEN — every one
cost real damage (a full save wipe, broken CI scripts, mangled release refs). Treat them
as hard rules, not tips.

## 1. MSYS path-conversion silently rewrites `/…` args (0-byte truncation)

Git Bash / MSYS auto-converts any argument that looks like a POSIX path
(`/sdcard/x`, `/data/…`, `/c/…`) into a Windows path before the program sees it —
e.g. `adb push src /sdcard/SAVE_DATA` becomes `…/Git/sdcard/SAVE_DATA` and the push
**fails**. Combined with a redirect (`cat /sdcard/x > devfile`), the shell opens
`devfile` for write — **truncating it to 0 bytes BEFORE the failed source read runs** —
so the target is left EMPTY (md5 `d41d8cd98f00b204e9800998ecf8427e`).

- **Fix:** `export MSYS_NO_PATHCONV=1` before any Git-Bash command carrying `/sdcard`,
  `/data`, or absolute POSIX args (adb, docker, ssh) — or run it in PowerShell instead.
- **Always verify after a write** (`md5sum` / size check) — the empty-file state is
  otherwise silent. *(Evidence: bcsfe save-wipe 2026-05-27.)*

## 2. PowerShell `^` is the escape char — it mangles `rev-parse tag^{commit}`

In PowerShell, `^` is the escape/continuation character, so
`git rev-parse v1.4.1^{commit}` gets corrupted (it can even reach git as a base64
`-encodedCommand` fragment) and dereferences to the wrong object or errors.

- **Fix:** deref a tag→commit with `git rev-list -n 1 <tag>` (no `^`), or single-quote
  the whole ref `'v1.4.1^{commit}'`. Same trap for any `HEAD^`, `HEAD^^`, `<ref>~^`.
  *(Evidence: Reframe v1.4.1 release sweep 2026-07-09.)*

## 3. Agent-written `.sh` files carry CRLF → real bash rejects them

Files written on Windows often get CRLF line endings. **Git Bash tolerates CRLF; real
WSL/Linux bash does NOT** — `then\r` parses as a command and you get errors like
`elif: unexpected` / `syntax error near unexpected token`. A `bash -n` self-check in
Git Bash passes while the script is actually broken under WSL.

- **Fix:** add `*.sh eol=lf` (and `*.ps1 eol=crlf` if needed) to `.gitattributes`;
  verify shell scripts with the REAL interpreter — `wsl.exe bash -n script.sh` — not
  Git Bash. Never trust a Git-Bash `bash -n` as proof a script runs on Linux.
  *(Evidence: Claude Science hardening — agent CRLF broke 2 scripts 2026-07-07.)*

## 4. `New-Item -Force` on an existing FILE truncates its content

`New-Item -ItemType File -Force <path>` does not "ensure exists" — on an existing file
it **recreates it empty**, destroying the content. (`-Force` only means "create parents /
overwrite" — for a file that means truncate.)

- **Fix:** guard it — `if (-not (Test-Path $p)) { New-Item -ItemType File $p }`. To write
  content use `Set-Content`/`Out-File` (or the Write tool), never `New-Item -Force` as a
  touch. *(Evidence: PowerShell tool contract — documented data-loss.)*

## 5. The MSYS `/data`·`/sdcard` save-wipe pattern (worst-case of #1)

The concrete catastrophic instance of #1: pushing/patching an Android app save
(`adb push` + in-place `cat > SAVE_DATA`) from Git Bash silently wiped a live game save
to 0 bytes because path-conversion failed the push while the redirect had already
truncated the destination. The damage is irreversible without a backup.

- **Fix:** for any device/save round-trip (adb, `/data`, `/sdcard`) do the transfer in
  **PowerShell**, back up on-device first (`cp SAVE_DATA SAVE_DATA.before-<ts>`), and
  `md5sum` the destination after every write. Never assume a redirect-over-network
  succeeded. *(Evidence: bcsfe-save-roundtrip skill; same 2026-05-27 wipe.)*

## 6. No bash process-substitution `<(…)` in PowerShell

`ParserError: The '<' operator is reserved for future use.`
(`wf_d573a873-cf8|a97926b10:72` — `… redact.py' <(git show …)`).
**Fix:** write to a temp file first, then pass the path.

## 7. Never pass Windows backslash paths as git revisions or pathspecs

`fatal: ambiguous argument 'origin\main;.github\workflows\quality.yml': unknown revision`
(`wf_d573a873-cf8|aa4f394c6:65`).
**Fix:** use forward slashes and the `--` separator: `git show origin/main:path/to/file`.

## 8. Git Bash lacks `bc` and several coreutils

`bc: command not found` (`wf_d573a873-cf8|aa4f394c6:61`).
**Fix:** use `python -c` for arithmetic. Verify a tool exists before scripting around it — and
check with `Get-Command` in PowerShell, not `which` in Git Bash (which misses `.cmd` shims).

## 8b. A Windows-local formatter/linter green does NOT imply CI-green (CRLF-vs-LF)

A working-tree file is **CRLF**; git normalises it to **LF** in the stored blob; CI on Linux checks
out the LF form. **Formatters can make different decisions on the two forms.** Ledger-proven
2026-07-19: `uvx ruff@0.15.17 format --check` reported *"1 file already formatted"* on Windows while
CI reported *"Would reformat"* for the SAME commit — on the LF form ruff wanted different comment
indentation inside a subscript (`hooks/stopfailure-notify/notify.py`). The local green was measured
against the wrong bytes, so it verified nothing.

- **Fix — verify against the BLOB, not the working tree:** `git archive <rev> | tar -x -C <tmp>`
  emits blob content (LF) = exactly what CI checks out. Run the gate there. Equivalent:
  `git cat-file -p <rev>:<path>` for a single file.
- **Same trap bites your own edit scripts:** reading with `newline=""` preserves `\r\n`, so a
  pattern written with `\n` silently matches 0 times. Split on the file's detected EOL, or read
  with universal newlines. (This produced a false `anchor 0` in the very commit that fixed it.)
- **Pin parity matters too:** CI pinned ruff `0.15.17`, local had `0.15.22` — different versions
  format differently. Use `uvx <tool>@<pinned-version>`, never the ambient one.
- Generalises to any formatter/linter with line-ending-sensitive output (ruff, black, prettier).

## 8e. Windows `sshd_config` — appending is WRONG; global directives are illegal after `Match`

The stock Windows OpenSSH `C:\ProgramData\ssh\sshd_config` **ends** with:

```
Match Group administrators
       AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys
```

So the natural move — append your directives to the end — silently puts them **inside that Match
block**, and sshd refuses to start:
`Directive 'ListenAddress' is not allowed within a Match block` (measured 2026-07-20).

- **Fix:** splice the managed block **before the first `^\s*Match\s` line**, never at EOF.
- **Always validate with the daemon's own parser before restarting:** `sshd.exe -T` prints the
  effective config and exits non-zero on a syntax error. It is the only authoritative check —
  a config that "looks fine" is not evidence.
- **Admins do NOT use `~/.ssh/authorized_keys`.** Because of that Match block, a user in the
  Administrators group authenticates against
  `C:\ProgramData\ssh\administrators_authorized_keys`, and sshd **rejects the file unless its ACLs
  are SYSTEM + Administrators only**: `icacls <file> /inheritance:r /grant "Administrators:F"
  /grant "SYSTEM:F"`. Wrong ACLs fail as a silent auth rejection, not an error.
- Loopback-only hardening that works: `ListenAddress 127.0.0.1` + `ListenAddress ::1` +
  `PubkeyAuthentication yes` + `PasswordAuthentication no`.
- Git Bash ships a **newer** ssh client than Windows' bundled sshd, so a PQ-key-exchange warning on
  a loopback connection is expected and cosmetic — not a misconfiguration.

## 8f. Codex/ChatGPT-desktop over SSH to a Windows host needs THREE fixes, and they mask each other

Measured 2026-07-20. The app shows ONE error string — `SSH connection failed` — for three unrelated
causes. Each becomes visible only after the previous is fixed, so diagnosing from the UI string
alone produces a wrong root cause every time. Fix in this order:

1. **Post-quantum KEX.** Windows ships OpenSSH **9.5p2**, which cannot offer `mlkem768x25519-sha256`;
   the app's client requires it and drops at `[preauth]`. Repro: force
   `-o KexAlgorithms=mlkem768x25519-sha256` at 9.5p2 → *"no matching key exchange method found"*.
   Fix: run the standalone **OpenSSH 10.0p2** (`C:\OpenSSH-Win64`) instead; it offers `mlkem768*`
   and `sntrup761*`.
2. **`known_hosts`.** With KEX working the client still aborts right after key exchange, logging
   `user: (null) ... Connection reset [preauth]` and the srclimit penalty
   *"connections without attempting authentication"*. That is NOT an auth failure — no credential is
   ever offered, because host-key verification failed first. Fix: populate
   `~/.ssh/known_hosts` (`ssh-keyscan -p <port> -t ed25519,rsa 127.0.0.1`). Confirm with
   `-o StrictHostKeyChecking=yes` — it must go from exit 255 to exit 0.
3. **DefaultShell.** Now authenticated, the session fails with
   `'sh' is not recognized...` / `'[' is not recognized...` because Windows sshd hands the session to
   **cmd.exe** while Codex sends a POSIX script. Fix (machine-wide):
   `HKLM:\SOFTWARE\OpenSSH` → `DefaultShell` = `C:\Program Files\Git\bin\bash.exe`,
   `DefaultShellCommandOption` = `-c`. Restart sshd. Verify with
   `ssh ... "sh -c 'if [ -d /c ]; then echo OK; fi; uname -s'"` → `OK` + `MINGW64_NT-...`.

**Diagnostic rule this cost:** `user: (null)` in an sshd log means host-key verification, not a bad
key — the username is never sent. Distinguish it from `Failed publickey for <user>`, which is a real
credential rejection. And `DefaultShell` is global: every SSH client on the box then gets Git Bash,
inheriting MSYS path conversion (§1).

## 9. A here-string PAYLOAD is scanned as if it were a command

`Set-Content -LiteralPath '…\MASTER-QUEUE.md' -Value @'…'@` was **blocked** with
*"Remove-Item on system path '/' is blocked"* — twice
(`ace575c04fbd5dacb.jsonl:12`, `aec903e2c2280af5c.jsonl:97`) — because the markdown BODY quoted a
destructive command. The guard is built-in and cannot be patched locally.
Measured cost of the here-string route vs the tool it was replacing:

| Route | calls | failures | rate |
|---|---|---|---|
| `Write` tool | 40 | 0 | **0.0%** |
| here-string `@'…'@` | 59 | 8 | **13.6%** |
| `Set-Content` (any form) | 75 | 11 | **14.7%** |

**Fix:** use the `Write` tool for file creation — content travels as a JSON parameter and is never
scanned as a command line. Reserve here-strings for appends and for piping into a native exe. A
document that contains literal `@'` / `'@` sequences CANNOT be written by a here-string at all —
they terminate it and corrupt the file.

---
*A one-line pointer to this file belongs in AGENTS.md §11 (owned by the D3 item — not
edited here).*
