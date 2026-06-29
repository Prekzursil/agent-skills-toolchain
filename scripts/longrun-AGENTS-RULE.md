# AGENTS RULE DRAFT — longrun discipline

> **STATUS: DRAFT ONLY** — Do not copy this file verbatim into AGENTS.md.
> Integrate the rule text below into the appropriate section of AGENTS.md
> (e.g. after the existing "Record decisions and failures" section, or as a
> new "Long-running operations" section). Adjust wording to match the file's
> existing voice and bullet style.

---

## Candidate rule text

### 4a. Wrap all long operations with `longrun` (>60s rule)

**Any operation expected to run longer than 60 seconds MUST be launched
via `longrun.ps1` (Windows) or `longrun.sh` (bash), using
`run_in_background` + `Monitor`, not a blocking foreground call.**

In scope (non-exhaustive):
- Test suites (`dotnet test`, `npx jest`, `pytest`, `go test ./...`)
- Coverage runs (`jest --coverage`, `nyc`, `coverage run`)
- CI watch / file watchers (`--watch` modes, polling loops)
- Static analysis over large trees (`lizard -C 15 .`, `semgrep`, `bandit -r`)
- Long LLM generations or multi-agent dispatch (Codex CLI, parallel agent fans)
- Any `Start-Sleep`-based polling loop the agent writes itself

**Rules:**

1. **Always end with a terminal `SUCCESS:<id>` or `FAILED:<id>` marker** —
   never exit a long operation silently. The marker is the primary defence
   against repeat-invocation loops (reduces re-runs ~7× before a detector
   fires).

2. **Print the stable log path before launch** so a stop-and-report action
   can always read the full output, even after the process exits.

3. **Support stop-and-report on demand:** when asked for status mid-run or
   after a run, re-read the printed log path (`Get-Content … -Tail 30`) and
   diff changed files (`Get-ChildItem -Recurse -File | Where-Object
   LastWriteTime -GT …`). Do not re-run the command to "check" it.

4. **Heartbeat interval ≤ 30s for interactive sessions.** Default 15s is
   fine; use 5–10s for tests expected to finish in 1–2 minutes so the user
   sees progress quickly.

5. **Enable `-HangTimeoutSec`** (or `--hang-timeout-sec`) for any command
   that could deadlock silently (test runners waiting for a port, coverage
   tools waiting for a file lock). Suggested values:
   - Test suite: 120s
   - Coverage: 180s
   - CI/CD steps: 300s

6. **Codex mirror:** apply the same discipline to long Codex CLI generations
   via `codex-cli-runtime`. Wrap codex invocations with `run_in_background`
   + `Monitor`; terminal marker integrates with `codex-result-handling`
   parsing step.

**Anti-patterns (NEVER do these):**

```powershell
# NEVER — blocks session, no progress visibility:
dotnet test | tail -c 2000

# NEVER — floods Monitor with raw output (defeats heartbeat model):
Start-Process … | Tee-Object -Variable out; $out

# NEVER — `cmd | tail` in bash (pipe breaks exit-code capture):
./run-tests.sh | tail -f
```

**Correct pattern:**

```powershell
# PowerShell — launch in background, Monitor streams heartbeats:
# Pass -Cmd <executable> then all its args positionally after it.
pwsh -File scripts/longrun.ps1 -Id jest-coverage -HeartbeatSec 15 -HangTimeoutSec 180 -Cmd npx jest --coverage
# (via run_in_background=True in the Bash tool call)
```

```bash
# Bash — same discipline:
bash scripts/longrun.sh -i jest-coverage -h 15 -t 180 -- npx jest --coverage
# (via run_in_background=True)
```

---

## Integration note

This rule extends section 4 of the existing contract ("Prefer terminal-state
tool outputs"). The anti-degeneration fingerprint `(tool, args_hash,
output_hash)` already guards repeat invocations; `SUCCESS/FAILED` markers
provide the output-hash signal that makes the fingerprint reliable for
long-running tool calls where prior invocations may have returned no output.
