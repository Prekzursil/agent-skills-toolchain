# Upstream Notes

- Upstream repo: `https://github.com/fosdickio/binary_ninja_mcp`
- Upstream installation order: install MCP client first, then install the Binary Ninja MCP plugin
- Upstream recommended bridge command: `npx -y binary-ninja-mcp --host localhost --port 9009`
- On Windows-first setups, prefer a `binaryninja.cmd` shim in `C:/Users/Prekzursil/.local/bin` if the real launcher lives at `binaryninja.exe`.
- The upstream project advertises auto-setup for Claude Desktop, Cursor, Claude Code, and other clients after plugin installation
- Do not mark local enablement complete unless Binary Ninja itself is installed and the plugin is present
