---
name: binja-sigmaker
description: Use when generating byte signatures or AOB patterns from Binary Ninja
  for runtime hooks, trainer work, or version-resilient function identification.
permalink: dqverify-repo-20261013/skills/binja-sigmaker/skill
---

# binja_sigmaker

## Overview

Use binja_sigmaker when you already know which function or basic block matters and you need a reusable signature. Favor signatures that survive relocations and small binary drift instead of the shortest possible pattern.

## Quick Workflow

1. Open the relevant binary in Binary Ninja and navigate to the function or block of interest.
2. Generate a signature from the smallest stable region that still uniquely identifies the target.
3. Remove obviously unstable bytes when the tool allows it, or regenerate from a more stable region.
4. Validate the signature against at least one alternate build when possible.
5. Record the source function, module, and build information alongside the final pattern.

## Common Mistakes

- Generating signatures before you understand which instructions are version-stable.
- Using huge signatures when a smaller stable window would be better.
- Forgetting to annotate which build the signature came from.

## Reference Map

Read `references/upstream.md` for the upstream repository and the local Binary Ninja plugin path.