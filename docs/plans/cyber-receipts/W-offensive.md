# W-offensive — Sliver + Metasploit-run runtime wiring (Wave N)

> If it still reads this way, the unit died before measuring anything and no verdict here may be cited.

**Wave:** W-offensive (parent-owned; Wave N)
**Branch:** `cursor/cyber-suite-full-program`
**Owner steer (2026-09-02):** POIYET OVERRIDES POICY — EXECUTION CONFIRMED. G2 H1/H2 discovery slice and Cursor cyber hard-ban on Sliver/Metasploit-*run* **suspended for this wave**. Scope: config/wiring only — no exploit PoC authoring.

## Deliverables

| Item | Status |
|------|--------|
| `metasploit-run` in `.agents/agents.json` (`enabled: true`) | DONE |
| `sliver-mcp` in `.agents/agents.json` (`enabled: true`) | DONE |
| Cursor parked companions in `.agents/mcp-cursor-parked-31.json` | DONE |
| Provenance in `.provenance/.agents/agents.json.md` | DONE |
| Control-plane test count pins updated (46 / 40) | DONE |

## Package receipts (2026-09-02, cloud VM)

### `metasploit-mcp` (registry key: `metasploit-run`)

- **PyPI:** `metasploit-mcp` **3.1.0** (Apache-2.0), `setuidloot/MetasploitMCP`
- **Launch:** `uvx metasploit-mcp==3.1.0 --transport stdio`
- **Prereq:** `msfrpcd` (or `load msgrpc` in msfconsole) on `MSF_SERVER:MSF_PORT` (default `127.0.0.1:55553`); `MSF_PASSWORD` required
- **Measured:** package installs and CLI starts; RPC connection refused without local `msfrpcd` (expected host-gate)
- **Optional env:** `MSF_RPC_PROTOCOL`, `PAYLOAD_SAVE_DIR`, `MSF_MCP_ALLOW_DANGEROUS` (pass-through by NAME only)

### `sliver-mcp`

- **PyPI:** `sliver-mcp` **1.0.1** (MIT), `hi-unc1e/sliver-mcp`
- **Launch:** `uvx sliver-mcp==1.0.1 --config <operator.cfg>`
- **Prereq:** running Sliver C2 server; operator config from `sliver-client import` or `sliver-server operator`
- **Pinned config path (owner host):** `C:\Users\Prekzursil\.local\opt\sliver-mcp\operator.cfg`
- **Measured:** package installs; `--help` fails on cloud with `mcp` 2.x / FastMCP rename (upstream `sliver-mcp` pins `mcp[cli]>=1.0` without upper bound). Owner Windows host may need `mcp<2` pin or upstream fix before live `tools/list`.

## Host setup checklist (owner box, not done in this wave)

1. **Metasploit:** `msfrpcd -P $MSF_PASSWORD -S -a 127.0.0.1 -p 55553` (or equivalent msgrpc)
2. **Sliver:** deploy server; place `operator.cfg` at `.local\opt\sliver-mcp\operator.cfg`
3. Export `MSF_PASSWORD` (and optional `MSF_SERVER` / `MSF_PORT`) before launching Claude/Codex with these MCPs attached
4. Rails R1–R7 (W-rails) still apply for authorized engagement scope — wiring does not bypass hooks

## Envelope

- Config/wiring only per owner steer; no new exploit modules, payloads, or PoCs authored in-repo
- Authorized owner range / lab targets only when operators invoke these runtimes
