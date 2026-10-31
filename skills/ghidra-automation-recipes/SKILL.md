---
name: ghidra-automation-recipes
description: Use when automating Ghidra analysis with Script Manager scripts, ghidra_bridge,
  or repeatable Python-driven recipes, especially for batch queries, symbol harvesting,
  structure extraction, or cross-tool analysis handoffs.
permalink: dqverify-repo-20261013/skills/ghidra-automation-recipes/skill
---

# Ghidra Automation Recipes

## Overview

Use this skill when Ghidra should participate as an automation endpoint instead of a purely manual UI. Favor small reproducible scripts and bridge queries over one-off manual clicking when you expect to repeat the analysis.

## Workflow

1. Open Ghidra and load the program you want to analyze.
2. Decide whether the task is better as a Script Manager action or an external Python session through `$ghidra-bridge`.
3. Prove the smallest useful query first: current program, a symbol list, a function lookup, or a comment extraction.
4. Expand to the batch or recipe you actually need only after the minimal query works.
5. Preserve outputs in notes or exported artifacts so the automation can be rerun later without reconstructing intent.

## Common Mistakes

- Writing large automation before proving the bridge or script environment works.
- Using Ghidra automation for a one-off question that would be faster in the UI.
- Forgetting to pin the exact script or bridge entrypoint used for the result.

## Reference Map

Read `references/recipes.md` for the local bridge staging and the preferred split between in-Ghidra scripts and external Python.