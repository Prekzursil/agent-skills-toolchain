# Upstream Notes

- Upstream repo: `https://github.com/LaurieWired/GhidraMCP`
- Upstream prerequisites: Ghidra, Python 3, MCP Python SDK
- Upstream client snippet shape: `python /ABSOLUTE_PATH_TO/bridge_mcp_ghidra.py --ghidra-server http://127.0.0.1:8080/`
- Windows-first local runtime recommendation: install `requests` and `mcp` into `C:/Users/Prekzursil/.local/opt/ghidra-mcp/.venv`, then point the client at that venv Python instead of a generic `python` on PATH.
- Repo bundle manifest: `tools/mcp/reverse-engineering-mcp-bundle/manifests/ghidra-mcp.json`
- On Windows-first setups, prefer a `ghidraRun.cmd` shim in `C:/Users/Prekzursil/.local/bin` if the real launcher is `pyghidraRun.bat`.
- When registering from the manifest, provide both `--var GHIDRA_MCP_BRIDGE_PATH=<absolute-path>` and `--var GHIDRA_MCP_URL=http://127.0.0.1:<port>/`.
