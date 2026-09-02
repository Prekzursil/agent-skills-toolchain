# W-offensive receipt — Sliver + Metasploit-run runtime wiring (Wave N)

**Wave:** W-offensive (parent-owned; Wave N) · **Branch:** `cursor/cyber-suite-full-program` · **Status:** DELIVERED — registry wired, parked companions added, control-plane green.

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

COVERAGE: all sections MEASURED unless marked PROPOSED. No UNKNOWN claims remain in the deliverables table.

## Owner steer (policy suspension for this wave only)

**Verbatim intent (2026-09-02):** POIYET OVERRIDES POICY — EXECUTION CONFIRMED. Wave N includes Sliver/Metasploit-run. Wire them **ENABLED**. G2 H1/H2 discovery slice and Cursor cyber hard-ban on live C2/payload-gen runtimes **suspended for this wave**. Focus: **config/wiring the runtimes**, not authoring exploit code.

**What that means in practice:**

| Still in force | Suspended for Wave N only |
|---|---|
| No in-repo exploit PoC / malware / kit authoring | Hard-ban on *registering* Sliver / Metasploit-*run* MCP entries |
| Owner-authorized / lab / estate-local targets when operators invoke tools (H1) | Treating registry wiring as a discovery-policy refusal |
| W-rails R1–R7 hooks (scope sidecar, security-action ledger) | — |
| `cve-mcp` remains metadata-only (`msf_check` reports module *existence*, does not run) | — |

This receipt records **parent SSOT changes only**. No new skills, no wrapper scripts, no daemon installs in-repo.

## Scope (paths this wave touched)

- `.agents/agents.json` — `mcp.servers.metasploit-run`, `mcp.servers.sliver-mcp`
- `.agents/mcp-cursor-parked-31.json` — parked companions for both
- `.agents/tests/test_mcp_control_plane_live.py` — attach-all count pins
- `.provenance/.agents/agents.json.md` — Wave N provenance block
- `docs/plans/2026-09-02-cyber-suite-build.md` — hard-ban strikethrough + override note
- `docs/plans/cyber-receipts/W-offensive.md` (this file)

Not touched: skills, hooks, `security-mcp-routing.md` (HexStrike still denies embedded `metasploit_run` until a separate routing update wave).

## Deliverables / claims

| Claim | Status |
|-------|--------|
| `metasploit-run` registered `enabled: true`, `targets: ["claude"]` | DONE |
| `sliver-mcp` registered `enabled: true`, `targets: ["claude"]` | DONE |
| Cursor parked companions (attach-all parity invariant) | DONE — 36 → 38 parked definitions |
| Provenance block in `.provenance/.agents/agents.json.md` | DONE |
| Control-plane test pins `attached=46`, `noncore_projected=40` | DONE |
| `validate_mcp_control_plane.py` green | DONE — 59 servers, 47 claude_targets |
| `.agents/tests` green | DONE — 109 passed, 8 skipped |
| Package existence verified on PyPI | DONE |
| Host runtime wiring on owner box | **NOT DONE** — checklist below; out of scope for this wave |
| `tools/list` captured live on owner host | **NOT DONE** — cloud VM lacks msfrpcd + Sliver; sliver-mcp blocked by `mcp` 2.x on Linux receipt box |

## Execution-plane placement (routing)

These MCPs are **new optional execution planes**, distinct from the existing stack:

```text
Intelligence (executor_owner=none):
  cve-mcp          → msf_check / nuclei_check (metadata only)
  osint-mcp-server → passive footprint
  darknet-mcp-server → CTI lookup (full 66-tool surface)

Bounded active (default plane today):
  hexstrike-ai     → nmap, reviewed nuclei, etc.; metasploit_run DENIED in routing doc

Wave N (new, registry-enabled, host-gated):
  metasploit-run   → full MSF RPC surface via metasploit-mcp 3.1.0
  sliver-mcp       → Sliver operator surface via hi-unc1e/sliver-mcp 1.0.1
```

**Coordinator rules (unchanged from `security-mcp-routing.md`):**

1. At most **one** non-`none` `executor_owner` per phase.
2. Do not run HexStrike `metasploit_run` **and** `metasploit-run` MCP in the same phase.
3. Do not overlap Sliver session execution with HexStrike network execution without a new authorized phase boundary.
4. `cve-mcp` `msf_check` output is still **candidate metadata** — it does not authorize a `run_exploit` call on `metasploit-run`.
5. W-rails `hooks/target-scope/` still gates tool-argument hosts/URLs/paths; `hooks/security-action/` still appends a redacted audit line. Wiring these MCPs does **not** disable hooks.

**Suggested `executor_owner` labels for future routing-doc update (PROPOSED, not merged):**

| MCP | Proposed owner token | Notes |
|-----|---------------------|-------|
| `metasploit-run` | `metasploit` | MSF RPC executor |
| `sliver-mcp` | `sliver` | C2 post-ex session executor |

Until routing.md is updated, treat both as **high-risk executors** requiring the same scope packet + human approval gate as HexStrike authorized engagement.

## Registry entries (as merged)

### `metasploit-run`

```json
"metasploit-run": {
  "label": "metasploit-run",
  "enabled": true,
  "transport": "stdio",
  "command": "C:\\Users\\Prekzursil\\.local\\bin\\uvx.exe",
  "args": ["metasploit-mcp==3.1.0", "--transport", "stdio"],
  "env": {
    "MSF_PASSWORD": "${MSF_PASSWORD}",
    "MSF_SERVER": "${MSF_SERVER}",
    "MSF_PORT": "${MSF_PORT}",
    "MSF_RPC_PROTOCOL": "${MSF_RPC_PROTOCOL}",
    "PAYLOAD_SAVE_DIR": "${PAYLOAD_SAVE_DIR}",
    "MSF_MCP_ALLOW_DANGEROUS": "${MSF_MCP_ALLOW_DANGEROUS}"
  },
  "requiredEnv": ["MSF_PASSWORD"],
  "credentialNames": ["MSF_PASSWORD"],
  "x_codex": { "startup_timeout_sec": 30 }
}
```

### `sliver-mcp`

```json
"sliver-mcp": {
  "label": "sliver-mcp",
  "enabled": true,
  "transport": "stdio",
  "command": "C:\\Users\\Prekzursil\\.local\\bin\\uvx.exe",
  "args": [
    "--with",
    "mcp<2",
    "sliver-mcp==1.0.1",
    "--config",
    "C:\\Users\\Prekzursil\\.local\\opt\\sliver-mcp\\operator.cfg"
  ],
  "x_codex": { "startup_timeout_sec": 30 }
}
```

Parked Cursor bodies mirror the same `command`/`args`/`env` with `"disabled": true` and `${env:NAME}` env syntax.

## Package receipts (2026-09-02, cloud VM)

### `metasploit-mcp` → registry key `metasploit-run`

| Field | Value |
|-------|-------|
| PyPI | `metasploit-mcp` **3.1.0** (also 3.0.1) |
| Upstream | [setuidloot/MetasploitMCP](https://github.com/setuidloot/MetasploitMCP) (fork of GH05TCREW/MetasploitMCP) |
| License | Apache-2.0 |
| Transport | stdio (registered) or HTTP (`--transport http`) |
| Backend | `msfrpcd` / msgrpc via `pymetasploit3` |
| Measured | `uvx metasploit-mcp==3.1.0` installs; process starts; RPC to `127.0.0.1:55553` **refused** without local `msfrpcd` (expected host-gate) |

**Tool surface (24 tools, from upstream `docs/MCP_API.md`):**

| Category | Tools | Default gate |
|----------|-------|--------------|
| Discovery | `list_exploits`, `list_payloads`, `describe_module`, `get_module_documentation` | read-only |
| DB intel | `list_hosts`, `list_services`, `list_vulnerabilities`, `list_notes`, `list_credentials`, `list_loot` | read-only |
| Assessment | `check_vulnerability`, `get_module_results` | read-only |
| Execution | `run_exploit`, `run_auxiliary_module`, `run_post_module`, `generate_payload` | destructive (on by default) |
| Session/listener | `send_session_command`, `terminate_session`, `start_listener`, `stop_job`, `kill_all_handler_jobs` | destructive |
| Status | `list_active_sessions`, `list_listeners`, `health_check` | read-only |

**Safety controls (package-native, not registry):**

| Control | CLI | Env | Default |
|---------|-----|-----|---------|
| Safe mode (read-only tools) | `--safe-mode` | `MSF_MCP_ALLOW_DANGEROUS=false` | dangerous **enabled** |
| Rate limit | `--rate-limit N` | `MSF_MCP_RATE_LIMIT` | off |
| Destructive confirm | `--confirm-dangerous` | `MSF_MCP_CONFIRM_DANGEROUS` | off |

To harden: set `MSF_MCP_ALLOW_DANGEROUS=false` in the owner environment **or** add `--safe-mode` to `args` in a follow-up parent commit (not done here — owner chose full surface).

### `sliver-mcp`

| Field | Value |
|-------|-------|
| PyPI | `sliver-mcp` **1.0.1** (also 1.0.0) |
| Upstream | [hi-unc1e/sliver-mcp](https://pypi.org/project/sliver-mcp/) |
| License | MIT |
| Backend | `sliver-py` gRPC → Sliver server (mTLS operator config) |
| Measured | unpinned `uvx sliver-mcp==1.0.1` fails on mcp 2.x FastMCP rename; `uvx --with mcp<2 sliver-mcp==1.0.1 --help` succeeds (2026-09-02 remeasure) |

**Tool surface (17 tools, from PyPI README):**

| Category | Tools |
|----------|-------|
| Server | `server_version` |
| Sessions | `list_sessions`, `session_info`, `kill_session` |
| Execute | `execute` (shell/cmd/powershell/sh) |
| Files | `list_files`, `change_directory`, `working_directory`, `make_directory`, `remove_path`, `download_file`, `upload_file` |
| Recon | `list_processes`, `network_interfaces`, `network_connections`, `get_environment`, `screenshot` |

**Alternatives considered (not registered):**

| Option | Why not chosen |
|--------|----------------|
| BishopFox built-in `sliver-client mcp` | Filesystem-only (~11 tools); hi-unc1e package covers full operator workflow per owner steer |
| v0idravl/sliver-mcp | Not on PyPI; would require git pin + local venv path |
| x746b/sliver-mcp | Larger surface (~74 tools) but not the PyPI package verified here |
| HexStrike embedded `metasploit_run` | Denied by routing doc; separate MCP gives schema-hash TOFU + explicit executor boundary |
| Rapid7 official Metasploit MCP | Not packaged on PyPI under `metasploit-mcp`; setuidloot fork is what `pip install metasploit-mcp` resolves to |

## Environment variables

| Name | Server | Required | Default / notes |
|------|--------|----------|-----------------|
| `MSF_PASSWORD` | metasploit-run | **yes** | msfrpcd / msgrpc password |
| `MSF_SERVER` | metasploit-run | no | `127.0.0.1` |
| `MSF_PORT` | metasploit-run | no | `55553` |
| `MSF_RPC_PROTOCOL` | metasploit-run | no | `msgpack` or `jsonrpc` |
| `PAYLOAD_SAVE_DIR` | metasploit-run | no | server-side payload output dir |
| `MSF_MCP_ALLOW_DANGEROUS` | metasploit-run | no | set `false` for safe mode |
| `MSF_MCP_RATE_LIMIT` | metasploit-run | no | requests/min when set |
| `MSF_MCP_CONFIRM_DANGEROUS` | metasploit-run | no | elicitation gate |
| *(none)* | sliver-mcp | — | operator creds live inside `operator.cfg` |

Secrets are passed by **env NAME only** in the registry; never commit live values.

## Host setup checklist (owner Windows box)

### A. Metasploit RPC + `metasploit-run`

1. Install Metasploit Framework (owner host already has MSF for HexStrike AD trident).
2. Start RPC bound to localhost:

   ```powershell
   msfrpcd -P $env:MSF_PASSWORD -S -a 127.0.0.1 -p 55553
   ```

   Or from `msfconsole`:

   ```text
   load msgrpc ServerHost=127.0.0.1 ServerPort=55553 User=msf Pass=<password>
   ```

3. Export credentials for Claude/Codex sessions:

   ```powershell
   $env:MSF_PASSWORD = '<redacted>'
   $env:MSF_SERVER = '127.0.0.1'
   $env:MSF_PORT = '55553'
   ```

4. Preflight (owner box):

   ```powershell
   C:\Users\Prekzursil\.local\bin\uvx.exe metasploit-mcp==3.1.0 --transport stdio
   # expect: connects to RPC; then Ctrl+C
   ```

5. Capture `tools/list` + schema hash for routing-doc TOFU (recommended follow-up).

### B. Sliver server + `sliver-mcp`

1. Install/run Sliver server (owner range/lab).
2. Generate operator config:

   ```bash
   sliver-server operator --name mcp-operator --lhost <server> --save operator.cfg
   ```

3. Place config at pinned path:

   ```text
   C:\Users\Prekzursil\.local\opt\sliver-mcp\operator.cfg
   ```

   Create the directory if missing.

4. **Dependency fix (if `mcp` 2.x breaks launch):** install in a pinned venv:

   ```powershell
   uv venv C:\Users\Prekzursil\.local\opt\sliver-mcp\.venv
   uv pip install --python C:\Users\Prekzursil\.local\opt\sliver-mcp\.venv "sliver-mcp==1.0.1" "mcp[cli]<2"
   ```

   Then point `agents.json` `command` at that venv's `sliver-mcp.exe` instead of bare `uvx` (PROPOSED follow-up — not in current registry).

5. Preflight:

   ```powershell
   C:\Users\Prekzursil\.local\bin\uvx.exe --with mcp<2 sliver-mcp==1.0.1 --config C:\Users\Prekzursil\.local\opt\sliver-mcp\operator.cfg
   ```

### C. Scope hooks (W-rails)

Before any offensive tool call:

```powershell
python hooks/target-scope/set_scope.py write --session <id> --allow "lab.example.com" "**"
```

The security-action audit hook labels allow/block and appends redacted JSONL regardless of MCP server.

### D. Cursor attach

Enabled Claude-target servers require parked entries. After pull:

```powershell
python .agents/scripts/merge_generated_cursor_mcp.py --attach-all-safe --check `
  --approvals-file <workspace>\mcp-approvals.json
```

Expect `attached=46`, `noncore_projected=40`.

## Verification commands run (parent merge commit)

```text
export PATH="$HOME/.local/bin:$PATH"
pip index versions metasploit-mcp          # 3.1.0, 3.0.1
pip index versions sliver-mcp              # 1.0.1, 1.0.0
uvx metasploit-mcp==3.1.0                  # starts; RPC connection refused (no msfrpcd)
uvx sliver-mcp==1.0.1 --help               # ModuleNotFoundError: mcp.server.fastmcp (mcp 2.x)
uvx --with 'mcp<2' sliver-mcp==1.0.1 --help  # usage: sliver-mcp [-h] --config PATH ...
python3 .agents/scripts/validate_mcp_control_plane.py --agents-config .agents/agents.json
  # SUCCESS servers=59 claude_targets=47
python3 -m pytest -q .agents/tests
  # 109 passed, 8 skipped
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `metasploit-run` MCP fails immediately | `msfrpcd` not running | Start RPC; verify `MSF_PASSWORD` |
| `Connection refused 127.0.0.1:55553` | wrong host/port | Set `MSF_SERVER` / `MSF_PORT` |
| `MSF_PASSWORD` validation error | missing env | Export before launching IDE |
| `sliver-mcp` import / FastMCP error | `mcp` 2.x pulled by uvx | Pin `mcp<2` in dedicated venv; update registry command |
| `sliver-mcp` gRPC error | server down or bad `operator.cfg` | Regenerate operator; check mTLS paths |
| Tool call blocked exit 2 | target-scope hook | `set_scope.py write` for authorized targets |
| HexStrike + MSF double execution | two executors one phase | Pick one plane; new phase for the other |

## Relationship to sibling waves

| Wave | Interaction |
|------|-------------|
| **W-rails** | Scope + audit hooks apply to these MCP tool calls |
| **W-routing** | `cve-mcp` `msf_check` stays metadata; routing doc still denies HexStrike `metasploit_run` — **follow-up wave** should add `metasploit` / `sliver` executor tokens |
| **W-purple** | CALDERA/ART/Stratus stay separate; Sliver is live C2, not purple emulation catalog |
| **W-cti** | darknet/osint/cve remain intelligence-only; do not conflate with execution |
| **W-cloud** | prowler/trivy stay DEFAULT-OFF posture tools; orthogonal |

## Envelope (post-wiring operator discipline)

- Registry wiring ≠ authorization to attack third parties (H1 still applies to operators).
- No exploit modules, payloads, or PoCs added to this repo in Wave N.
- Destructive MSF tools are **on by default** in upstream `metasploit-mcp`; harden with `MSF_MCP_ALLOW_DANGEROUS=false` on shared networks.
- Sliver listener/implant generation is upstream tool surface — invoke only on owner range with scope sidecar populated.

## Rollback

1. Delete `metasploit-run` and `sliver-mcp` from `.agents/agents.json`.
2. Delete both entries from `.agents/mcp-cursor-parked-31.json`.
3. Restore test pins: `attached=44`, `noncore_projected=38`; parked comment **36 definitions**.
4. Re-run validator + `.agents/tests`.

## Commit

Implementation commit: **`09013ab3`** — `Wire Sliver and Metasploit-run MCPs enabled (Wave N owner override)` on `cursor/cyber-suite-full-program`.

## Follow-ups

| Item | Status |
|------|--------|
| Update `security-mcp-routing.md` with `metasploit` / `sliver` executor_owner tokens | DONE — W-routing follow-up on this branch (triple-write + SKILL.md) |
| Pin `sliver-mcp` uvx with `mcp<2` | DONE — `args` now `--with mcp<2 sliver-mcp==1.0.1` (parked companion matched) |
| Live `tools/list` + schema-hash TOFU on owner host | OPEN — needs msfrpcd + Sliver on the Windows box |
| Optional `--safe-mode` on `metasploit-run` args | OPEN — owner chose full surface; set `MSF_MCP_ALLOW_DANGEROUS=false` if hardening |
| Skill wrap documenting plane choice | OPEN — HexStrike skill still the engagement gate; no new skill this wave |
