---
name: schrodinger-maestro-driver
description: Use when driving the local schrodinger MCP server for structure-based drug discovery on a Schrodinger Suite install - SMILES to 3D, LigPrep ligand preparation, Protein Preparation Wizard, Glide grid generation, Glide docking, Prime MM-GBSA binding free energy, QikProp ADMET, structure format conversion, RDKit descriptors, or the run_schrodinger_python escape hatch. Covers the SCHRODINGER environment setup and the license-token-free vs token-consuming tool split for the full receptor-prep to docked-and-rescored pipeline.
---

# Schrodinger / Maestro Driver

## Overview

The `schrodinger` MCP server is a thin, security-conscious wrapper over a local Schrodinger Suite install. It NEVER imports the `schrodinger` package in-process; every tool builds an argv list and hands it to a single internal `_exec()` chokepoint that runs WITHOUT a shell. Client-supplied paths are validated by `_safe_path()` (rejects empty/flag-like values, normalizes to absolute) before reaching any argv, so there is no shell or argument injection. The `run_schrodinger_python` tool is an intentional arbitrary-code escape hatch - this server is for local, single-user use only.

- Source: `C:\Users\agentuser\source\repos\schrodinger-mcp\server.py` (+ `_sch_helper.py`, which runs INSIDE the Schrodinger interpreter where both `schrodinger` and a bundled `rdkit` are importable).
- Verified install: Schrodinger 2022-4, build 79134, at `D:\Program Files\Schrodinger 2022-4`.

## Environment Setup

The server reads `SCHRODINGER` from the environment; it defaults to the Windows path `D:\Program Files\Schrodinger 2022-4` and on POSIX you must set it.

- MCP registration (verified, stdio):
  - command: `C:\Users\agentuser\source\repos\schrodinger-mcp\.venv\Scripts\python.exe`
  - args: `C:\Users\agentuser\source\repos\schrodinger-mcp\server.py`
  - env: `SCHRODINGER` = `D:\Program Files\Schrodinger 2022-4`
- Cross-platform note: the server resolves `run.exe`/driver `.exe` on Windows and falls back to the extension-less `run`/driver names on POSIX. On POSIX, export `SCHRODINGER` to your suite root (e.g. `/opt/schrodinger/suites/2022-4`).

### The 12 Tools (grouped by license cost)
### Typical Workflow (end-to-end structure-based screening)
### Full pipeline is now in-server (receptor prep -> grid -> dock -> rescore)
### Common Mistakes
### Related Skills
