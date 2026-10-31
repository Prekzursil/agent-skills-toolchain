---
title: recipes
type: note
permalink: dqverify-repo-20261013/skills/ghidra-automation-recipes/references/recipes
---

# Ghidra Automation Recipes

## Local automation surfaces

- Ghidra Script Manager with the staged bridge scripts in `%APPDATA%\ghidra\ghidra_12.0.3_PUBLIC\ghidra_scripts`
- `$ghidra-bridge` external Python client in `%USERPROFILE%\.local\opt\ghidra-bridge\.venv`

## Rule of thumb

- Use Script Manager when the task is local to Ghidra and self-contained
- Use ghidra_bridge when the task must coordinate with external Python tooling or needs to pipe results into another workflow

## Good starter tasks

- symbol / function enumeration
- extracting comments or annotations
- batch renaming support data
- harvesting addresses or structures for follow-on signature work