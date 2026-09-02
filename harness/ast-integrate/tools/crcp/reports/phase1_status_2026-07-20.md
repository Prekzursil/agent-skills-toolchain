# Phase 1 Status — 20.07.2026

## Delivered

| Component | Path | Smoke |
|-----------|------|-------|
| Auth vault CLI | `python -m crcp auth status` | GREEN |
| Unified health | `python -m crcp health` | GREEN |
| wfmon snippet | `reports/wfmon_crcp_health.json` | written |
| ChatGPT list | `python -m crcp chatgpt list` | 4 conversations |
| ChatGPT fetch | `python -m crcp chatgpt fetch --latest 1` | packed `6a5d2b66-…` |
| Outbox pack | `outbox/chatgpt_conv_6a5d2b66-*.json` (~2.1MB) | 75 msgs, 1.47M text chars |
| Envelope | `outbox/envelope_6a5d2b66-*.json` | crcp.envelope.v1 |

## Verified live

- Conversation id from earlier export family is **live on backend-api**: `6a5d2b66-a160-8327-9b06-baca0caf1584`
- Bridge is **token consumer only** (no refresh write)
- Secrets not printed

## Package layout

```
tools/crcp/
  crcp/           # Python package
  bin/crcp.ps1
  outbox/
  inbox/chatgpt/
  fixtures/…      # Phase 0
  reports/
  README.md
```

## Usage

```powershell
$env:PYTHONPATH = "$HOME\source\agent-skills-toolchain\tools\crcp"
python -m crcp health
python -m crcp auth status
python -m crcp chatgpt fetch --id 6a5d2b66-a160-8327-9b06-baca0caf1584
```

## Residual

- `codex_cli` path probe may show UNKNOWN if npm shim not resolvable from subprocess; `codex_auth` remains the load-bearing signal
- MCP Python streamable client still flaky; bus proof uses raw JSON-RPC HTTP
- Phase 2: drop-folder watcher, agent-mail publish of envelopes, wfmon live panel
