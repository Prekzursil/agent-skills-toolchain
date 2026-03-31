# Reverse Engineering MCP Bundle

Shared manifests and helper scripts for wiring reverse-engineering MCP servers into Codex, Claude Code, and Gemini CLI.

## Contents

- `manifests/` - per-server stdio definitions used by the registration helper
- `scripts/register_mcp_server.py` - patch Codex, Claude, or Gemini config with a manifest entry
- `scripts/install_python_mcp.py` - create a dedicated venv under `~/.local/opt/<name>` and install a Python MCP package
- `scripts/install_windows_host_shims.ps1` - publish stable Windows launch shims into `~/.local/bin` for host apps whose actual launcher names differ from what agents expect
- `scripts/sync_hexstrike_wrapper.py` - copy the canonical HexStrike bridge wrapper into the local HexStrike install root
- `wrappers/hexstrike_mcp_launcher.py` - canonical Content-Length bridge for HexStrike
- `tests/test_register_mcp_server.py` - unit coverage for manifest expansion and config patching

## Windows-first workflow

### Repomix

```powershell
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client codex --manifest .\tools\mcp\reverse-engineering-mcp-bundle\manifests\repomix.json
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client claude --manifest .\tools\mcp\reverse-engineering-mcp-bundle\manifests\repomix.json
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client gemini --manifest .\tools\mcp\reverse-engineering-mcp-bundle\manifests\repomix.json
```

### Frida MCP

```powershell
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\install_python_mcp.py --target-name frida-mcp --package frida-mcp --entrypoint frida-mcp
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client codex --manifest .\tools\mcp\reverse-engineering-mcp-bundle\manifests\frida-mcp.json
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client claude --manifest .\tools\mcp\reverse-engineering-mcp-bundle\manifests\frida-mcp.json
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\register_mcp_server.py --client gemini --manifest .\tools\mcp\reverse-engineering-mcp-bundle\manifests\frida-mcp.json
```

### HexStrike AI

```powershell
py -3 .\tools\mcp\reverse-engineering-mcp-bundle\scripts\sync_hexstrike_wrapper.py
```

### Host-app shims

```powershell
pwsh -File .\tools\mcp\reverse-engineering-mcp-bundle\scripts\install_windows_host_shims.ps1
```

Use the existing local client entries that point at `~/.local/opt/hexstrike-ai/hexstrike_mcp_launcher.py`, or re-register from `manifests/hexstrike-ai.json` if you need to rebuild them.

## Host-gated servers

These manifests are published for repeatability, but local enablement still depends on the host application already being installed:

- `ida-pro-mcp.json` needs a working IDA Pro installation and plugin bootstrap
- `ghidra-mcp.json` needs the Ghidra extension installed plus both `--var GHIDRA_MCP_BRIDGE_PATH=...` and `--var GHIDRA_MCP_URL=http://127.0.0.1:<port>/`
- `binary-ninja-mcp.json` needs Binary Ninja plus the Binary Ninja MCP plugin/runtime

## Validation

```powershell
py -3 -m unittest .\tools\mcp\reverse-engineering-mcp-bundle\tests\test_register_mcp_server.py
```
