---
title: rollback-and-ownership
type: note
permalink: dqverify-repo-20261013/skills/wsl-vmware-cutover/references/rollback-and-ownership
---

# Rollback And Ownership

## Rollback assets

Keep the original VM source, exported archives, and guest pre-import home rename until the destination survives a clean reboot and workload validation.

## Codex ownership

If Windows remains the canonical Codex host, keep `.codex` canonical on Windows and treat Linux copies as mirrors or archives only. Do not silently repoint VS Code or CLI back into Linux during migration.