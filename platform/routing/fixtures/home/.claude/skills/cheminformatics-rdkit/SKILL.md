---
name: cheminformatics-rdkit
description: Use to drive the standalone rdkit MCP server (tandemai-inc/rdkit-mcp-server, 74 cheminformatics tools, MIT) for license-free chemistry - molecular descriptors, fingerprints, similarity, substructure search, and scaffold analysis on SMILES/structures. Covers the stdio registration and the two install gotchas. Use when a chemistry question needs RDKit cheminformatics and does not require a Schrodinger license.
---

# Cheminformatics (RDKit MCP)

## Overview

The `rdkit` MCP server (tandemai-inc/rdkit-mcp-server, MIT) exposes 74 cheminformatics tools - a license-free, standalone alternative to the bundled-RDKit path inside the `schrodinger` server. Use it for molecular descriptors, fingerprints, similarity, substructure/scaffold work on SMILES or structures.

- Local checkout: `C:\Users\agentuser\source\repos\rdkit-mcp-server`
- Capability categories (call the server's tool list at runtime for exact names): molecular descriptors / physchem properties, fingerprints, similarity scoring, substructure search, and scaffold analysis.

## Registration (verified, stdio)

- command: `C:\Users\agentuser\source\repos\rdkit-mcp-server\.venv\Scripts\python.exe`
- args: `C:\Users\agentuser\source\repos\rdkit-mcp-server\run_server.py` `--transport` `stdio`
- env: none.
- Cross-platform: on POSIX, point command at `rdkit-mcp-server/.venv/bin/python` and keep `run_server.py --transport stdio`.

## Two Install Gotchas (load-bearing)

1. Dead RDKit pin: upstream pins `rdkit==2025.3.1`, which is unavailable. Install a working RDKit (here `rdkit 2026.3.3`) and then install the package WITHOUT re-resolving the dead pin: `pip install --no-deps .` inside the venv. Skipping `--no-deps` re-pulls the broken pin and the install fails.
2. Transport default: the server defaults to SSE on port 8000. You MUST pass `--transport stdio` in the args (as registered above) or the MCP client cannot connect over stdio.

## Quick Workflow

### When to Use vs the Schrodinger Server
### Common Mistakes
### Related Skills
