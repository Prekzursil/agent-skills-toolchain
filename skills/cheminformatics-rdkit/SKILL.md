---
name: cheminformatics-rdkit
description: Use to drive the standalone rdkit MCP server (tandemai-inc/rdkit-mcp-server,
  74 tools, MIT) for license-free chemistry - molecular descriptors, fingerprints,
  similarity, substructure search, and scaffold analysis on SMILES/structures. Covers
  the stdio registration and two install gotchas. Use when a chemistry question needs
  RDKit and does not need a Schrodinger license.
permalink: dqverify-repo-20261013/skills/cheminformatics-rdkit/skill
---

# Cheminformatics (RDKit MCP)

## Overview

The `rdkit` MCP server (tandemai-inc/rdkit-mcp-server, MIT) exposes 74 cheminformatics tools - a license-free, standalone alternative to the bundled-RDKit path inside the `schrodinger` server. Use it for molecular descriptors, fingerprints, similarity, substructure/scaffold work on SMILES or structures.

- Local checkout: `C:\Users\Prekzursil\source\repos\rdkit-mcp-server`
- Capability categories (call the server's tool list at runtime for exact names): molecular descriptors / physchem properties, fingerprints, similarity scoring, substructure search, and scaffold analysis.

## Registration (verified, stdio)

- command: `C:\Users\Prekzursil\source\repos\rdkit-mcp-server\.venv\Scripts\python.exe`
- args: `C:\Users\Prekzursil\source\repos\rdkit-mcp-server\run_server.py` `--transport` `stdio`
- env: none.
- Cross-platform: on POSIX, point command at `rdkit-mcp-server/.venv/bin/python` and keep `run_server.py --transport stdio`.

## Two Install Gotchas (load-bearing)

1. Dead RDKit pin: upstream pins `rdkit==2025.3.1`, which is unavailable. Install a working RDKit (here `rdkit 2026.3.3`) and then install the package WITHOUT re-resolving the dead pin: `pip install --no-deps .` inside the venv. Skipping `--no-deps` re-pulls the broken pin and the install fails.
2. Transport default: the server defaults to SSE on port 8000. You MUST pass `--transport stdio` in the args (as registered above) or the MCP client cannot connect over stdio.

## Quick Workflow

1. Confirm the `rdkit` MCP server is connected (`claude mcp get rdkit`).
2. List the server's tools to get exact names/signatures - do not assume tool names from the 74-tool set.
3. Run the chemistry operation (descriptors / fingerprint / similarity / substructure / scaffold) on your SMILES or structure input.

## When to Use vs the Schrodinger Server

- Use `cheminformatics-rdkit` for license-free RDKit cheminformatics (descriptors, fingerprints, similarity, scaffolds) - no Schrodinger token consumed.
- Use `schrodinger-maestro-driver` when you need suite-specific computation: LigPrep, Glide docking, QikProp ADMET, or `.mae` interchange. Note its `molecule_properties` and `smiles_to_3d` also use a bundled RDKit, so for pure descriptors either server works - prefer this one to avoid touching the licensed suite.

## Common Mistakes

- Forgetting `--transport stdio` and getting an SSE:8000 server the client cannot reach.
- Running a plain `pip install .` and failing on the dead `rdkit==2025.3.1` pin (use `--no-deps` with a separately installed working RDKit).
- Inventing tool names instead of listing the server's 74 tools at runtime.

## Related Skills

- `schrodinger-maestro-driver` - licensed suite tools (LigPrep/Glide/QikProp) and its own bundled-RDKit descriptor panel.
- `ddi-admet-research` - ToolUniverse biomedical knowledge front-end.