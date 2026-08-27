# Upstream Notes

- Upstream repo: `https://github.com/dnakov/frida-mcp`
- Upstream quick install: `pip install frida-mcp`
- Upstream Claude Desktop config shape: `{"mcpServers":{"frida":{"command":"frida-mcp"}}}`
- Repo bundle helpers:
  - `py -3 tools/mcp/reverse-engineering-mcp-bundle/scripts/install_python_mcp.py --target-name frida-mcp --package frida-mcp --entrypoint frida-mcp`
  - `py -3 tools/mcp/reverse-engineering-mcp-bundle/scripts/register_mcp_server.py --client codex --manifest tools/mcp/reverse-engineering-mcp-bundle/manifests/frida-mcp.json`
