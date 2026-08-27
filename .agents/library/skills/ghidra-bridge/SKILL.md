---
name: ghidra-bridge
description: Use when automating Ghidra from Python, driving analyses from an external REPL or script, or exchanging program state between Ghidra and other Python-based reverse-engineering workflows.
---

# Ghidra Bridge

## Overview

Use ghidra_bridge when you need Ghidra to participate in a Python-driven workflow. It is best for repeatable analysis, batch queries, and moving data between Ghidra and external Python tooling.

## Quick Workflow

1. Open Ghidra and load the target program.
2. Start the bridge server from Ghidra using the staged bridge scripts.
3. Connect from the external Python environment that has `ghidra_bridge` installed.
4. Script the smallest useful query first (current program, symbols, functions, comments, etc.), then expand once the connection is stable.
5. Keep long-lived automation separate from one-off Script Manager snippets.

## Common Mistakes

- Assuming the Python package alone is enough without starting the Ghidra-side server script.
- Re-running heavy automation before verifying the bridge can answer a trivial query.
- Forgetting that this is automation glue, not a replacement for normal Ghidra analysis setup.

## Reference Map

Read `references/upstream.md` for the upstream package and the local script staging path.
