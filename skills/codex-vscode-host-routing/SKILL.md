---
name: codex-vscode-host-routing
description: Use when VS Code launches Codex from the wrong host, WSL becomes the
  default unexpectedly, or you need Windows to remain the canonical Codex host while
  still allowing explicit Linux-side tools.
permalink: dqverify-repo-20261013/skills/codex-vscode-host-routing/skill
---

# Codex VS Code Host Routing

## Overview

Keep Codex host routing deliberate. Separate editor host routing from tool access: Windows can remain the canonical Codex host while Linux-side agents or tools stay available explicitly.

## Reference Map

- Read [references/windows-first-routing.md](references/windows-first-routing.md) for the default Windows-host configuration.
- Read [references/escape-hatches.md](references/escape-hatches.md) for Linux-side exceptions that should remain explicit.

## Required Discovery

1. Identify where VS Code currently launches Codex from.
2. Confirm the canonical `CODEX_HOME` and whether the extension honors it.
3. Check for WSL-only executable paths in user settings or skill config.
4. Decide whether the user wants Linux tools available through explicit commands only.

## Preferred Policy

- Default host: Windows.
- Canonical store: one Windows `CODEX_HOME` unless deliberately changed.
- Linux tools: opt-in and explicit, not the default launch path.
- WSL mirrors: archive or read-only unless a migration is active.

## Stop Rules

- Do not let extension host defaults repoint the canonical store silently.
- Do not hardcode WSL executables into the default Windows launch path.
- Do not assume Remote - WSL should own Codex just because the workspace is Linux-backed.

## Common Mistakes

- Treating editor workspace location as the same thing as Codex runtime ownership.
- Leaving stale WSL executable settings in user settings after migration.
- Forgetting to test both CLI and extension launch paths.