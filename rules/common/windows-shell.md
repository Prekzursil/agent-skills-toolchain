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

## 8c. A bash HEREDOC mangles backslashes — use the `Write` tool for scripts

`python - <<'PY' … PY` with Windows paths or regex escapes inside fails: `'\\Users\\'` arrives as
`'\Users\'` → `SyntaxError: unterminated string literal`, and `c.replace('\\\\','\\')` becomes
`c.replace('\','\')`. Bit twice in one session (2026-07-19b) despite `<<'PY'` quoting.

- **Fix:** write the script with the **`Write` tool** to the scratchpad, then `python <path>`.
  Content travels as a JSON parameter and is never re-parsed by the shell. Same reasoning as §9.
  Reserve heredocs for backslash-free payloads (e.g. `git commit -F -`).

## 8d. `git diff origin/main --stat` before EVERY PR — a stale branch proposes mass deletion

A branch far behind `main` produces a PR that **deletes everything main has gained**. Measured
2026-07-19b: a leftover feature branch showed **1,188 files / 316,222 deletions** against main.
Cherry-picking the one wanted commit onto a fresh `origin/main` branch reduced it to 7 files / 4
deletions.

- **Fix:** always check the **commit-to-commit** surface `git diff origin/main...HEAD --stat`
  (three dots) — plain `git diff origin/main` also folds in working-tree noise, which is how
  untracked credential files appear to be "in the PR" when they are not.
- Pairs with the worktree empty-index trap (scoped `git add` staging 6,013 deletions).

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



## 10. An apostrophe in a Bash-tool command body breaks the tool's OWN quoting

The Bash tool wraps the command you pass in single quotes before handing it to `sh -c`. So any
**literal `'` inside a heredoc body, a grep pattern, or an inline `python -c '…'`** closes that
outer quote early and the call dies with `unexpected EOF while looking for matching '`' — before a
single byte runs. Ledger-proven across ONE session (2026-07-19), it killed **6+** calls in a row:
a `git commit -F - <<'EOF'` whose message said *"the repo's own CI"* and *"don't"*; a
`diff … | grep -c 'Only in'`; a `python -c "assert x, 'msg'"`; a `sed 's/…/…/'` with `?`/`[]`.
Doubling down (escaping, swapping quote styles) wasted ~9 minutes before the pattern was named.

- **Fix — never inline apostrophe-bearing content into a Bash-tool command.** Write it to a file
  with the `Write` tool, then pass the PATH:
  - commit messages → `git commit -F <path>` (NOT `-m "…"` with prose, NOT a `<<'EOF'` heredoc);
  - PR/issue bodies → `gh pr create --body-file <path>`;
  - multi-line scripts → `python <script.py>` / `bash <script.sh>`, never `python -c '…'`.
- **PowerShell is the escape hatch for git ops** when a file is overkill — its own quoting survives
  apostrophes that Git-Bash mangles (this session's `git commit -F <file>` and `git push` both
  worked first-try in PowerShell after the Bash heredoc route failed repeatedly).
- Generalises to `awk '…'`, `jq '…'`, `perl -e '…'` — anything whose idiom is single-quoted. Prefer
  the dedicated tool (Grep, Write, a script file) over an inline single-quoted shell string.
- Two-strikes (AGENTS.md §4b): after the SECOND `unexpected EOF … matching '` on the same call
  shape, STOP escaping and switch transport (file + `-F`, or PowerShell) — do not attempt a third.

---
*A one-line pointer to this file belongs in AGENTS.md §11 (owned by the D3 item — not
edited here).*


## 11. `MSYS_NO_PATHCONV=1` must be SCOPED, never global — measured PROMPT-1.5 (2026-07-21)

§1 says to use `MSYS_NO_PATHCONV=1` when a git revision contains `:` or a leading `/`. Setting it
**globally** inverts the problem: it also suppresses the conversion that legitimate `/c/Users/...`
PATH arguments depend on.

Measured: `export MSYS_NO_PATHCONV=1` followed by
`git clone --no-hardlinks /c/Users/Prekzursil/source/<repo> repo` -> the clone **silently did not
happen**; every downstream probe then reported `NO` and the whole verification read as a failure.

- **Fix:** Windows-style paths (`C:/Users/...`) for PATH arguments; apply the env var only around
  REVISION arguments (`origin/main:path/to/file`, `HEAD^`, ref syntax, pathspecs).
- This is the same defect class an in-repo guard exists to catch — *"a global suppression is not
  acceptable; enforcement must be command-aware AND argument-aware"* — reproduced on the
  orchestrator while it was verifying that very guard. The rule being written down did not prevent
  it; only the scoping did.

## 12. PowerShell `${drive:...}` inside braces is a provider path — it silently reads/writes a FILE

A `${name}` reference treats a **colon INSIDE the braces** as a namespace/drive qualifier, not part
of the variable name. `${env:PATH}` reads the `env:` namespace and `${function:prompt}` the
`function:` drive — and the footgun: **`${C:\temp\x}` resolves against the `C:` filesystem drive and
gets/sets the CONTENT OF THAT FILE.** So a variable whose name looks like a drive letter followed by
`:` is parsed as a drive-qualified path: `${C:\out} = $data` WRITES a file instead of assigning a
variable, and `${C:\in}` READS one. Reproduced live 2026-07-18: `${C:\Users\…\Temp\probe.txt}`
returned the file's contents, and `${…\probe.txt} = "x"` created the file — neither ever touched a
variable named `C`.

- **Fix — keep the colon OUTSIDE the braces when you mean "the variable, then a literal `:`":**
  `"${C}:\path"` (the brace closes before the `:`) interpolates `$C` then a literal `:\path`;
  `"${C:\path}"` does NOT — it is a file access. When unsure use `$($C):\path` or
  `[string]::Concat($C, ':\path')`, which cannot be reparsed as a provider path.
- The same qualifier rule fires for any single-letter drive name (`A:` through `Z:`) and for the
  scope / namespace prefixes `global:` `local:` `script:` `private:` `env:` `variable:` `function:`
  — a leading `<word>:` inside `${…}` is ALWAYS a qualifier, never a literal.

---
*A one-line pointer to this file belongs in AGENTS.md §11 (owned by the D3 item — not
edited here).*
