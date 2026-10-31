---
title: efficiency
type: note
permalink: dqverify-repo-20261013/skills/azure-upgrade/references/languages/java/rules/efficiency
---

# Efficiency

- **Targeted reads**: Use `grep` over full file reads; read sections, not entire files.
- **Quiet commands**: Use `-q`, `--quiet` for build/test when appropriate.
- **Progressive writes**: Update `plan.md` and `progress.md` incrementally, not at end.