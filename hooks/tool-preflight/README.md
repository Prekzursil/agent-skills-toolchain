# tool-preflight

SessionStart hook that catches dead/missing MCP servers and project CLIs **before** the
agent tries to use them — so failures surface at session open rather than mid-task.

## What it checks

| Check | Method |
|---|---|
| stdio MCP server command | `os.path.isfile` (absolute) or `shutil.which` (bare name) |
| `cmd /c <prog> …` servers | `shutil.which(<prog>)` on the delegate (npx, node, …) |
| `url`-based remote MCP servers | **skipped** — nothing local to check |
| Project CLIs (`qlty`, `rg`, `gh`, …) | `shutil.which` |

**Existence-only scope** — no server spawns, no pings, no auth checks.
Deep checks (liveness, auth, tool listing) belong in `/external-tools-health`.

## Digest format

Emitted to stdout **only when something is missing** (completely silent on all-OK):

```
## Tool preflight — 3 issue(s):
- MCP 'schrodinger': interpreter missing ('C:\..\.venv\Scripts\python.exe') → venv broken / rebuild it
- MCP 'rdkit': interpreter missing ('C:\..\.venv\Scripts\python.exe') → venv broken / rebuild it
- CLI 'qlty': not on PATH → install or add to PATH

_Run `/external-tools-health` for deep ping/auth checks. This preflight is existence-only._
```

## Performance

Pure filesystem + PATH lookups — no subprocesses. Completes in well under 2 s on any
normal machine regardless of the number of configured servers.

## Opt-out

- **Per-machine:** create `C:\Users\Prekzursil\.claude\hooks\tool-preflight\.disabled`
- **Per-session:** set env var `PREFLIGHT=off`

## Editing the CLI list

Open `preflight.py` and edit the `PROJECT_CLIS` constant near the top.

## settings.json registration

Add the following block inside the `"SessionStart"` array in
`~/.claude/settings.json` (after the existing hooks):

```json
{
  "matcher": "*",
  "hooks": [
    {
      "type": "command",
      "command": "python C:/Users/Prekzursil/.claude/hooks/tool-preflight/preflight.py",
      "timeout": 10,
      "statusMessage": "MCP + CLI tool preflight (existence check)"
    }
  ]
}
```
