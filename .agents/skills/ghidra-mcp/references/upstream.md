# Upstream Notes

- Upstream repo: `https://github.com/LaurieWired/GhidraMCP`
- Upstream prerequisites: Ghidra, Python 3, MCP Python SDK
- Upstream client snippet shape: `python /ABSOLUTE_PATH_TO/bridge_mcp_ghidra.py --ghidra-server http://127.0.0.1:8080/`
- Repo bundle manifest: `tools/mcp/reverse-engineering-mcp-bundle/manifests/ghidra-mcp.json`
- When registering from the manifest, provide `--var GHIDRA_MCP_BRIDGE_PATH=<absolute-path>`
