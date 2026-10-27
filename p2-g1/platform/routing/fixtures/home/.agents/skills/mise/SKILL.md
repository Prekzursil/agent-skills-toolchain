---
name: mise
description: "Use when managing dev tool and language runtime versions with mise (mise-en-place) — the asdf/nvm/pyenv/rbenv replacement: pinning global vs per-project versions via mise.toml or .tool-versions, per-directory environment variables, the task runner, installing non-language CLIs (npm/cargo/pipx/ubi/aqua/go backends), or setting up mise on Windows PowerShell (shims vs activate, mise trust)."
---

# mise (mise-en-place)

## Overview

mise is **three tools in one**: a polyglot **version manager** (asdf/nvm/pyenv/rbenv replacement), a per-directory **environment-variable** manager (direnv replacement), and a **task runner** (make/just replacement). Core mental model: **mise owns the tools you hand it and ignores the rest** — it installs its own managed copies under its data dir and prepends them to `PATH`; tools you don't declare keep resolving from the normal `PATH`.

## When to Use

- Pin or switch runtime/CLI versions per project or globally (`node`, `python`, `go`, `rust`, `terraform`, `jq`, `ripgrep`, …).
- Replace a pile of `nvm`/`pyenv`/`asdf`/`scoop`-pinned tools with one config.
- Load per-directory env vars or `.env` files automatically.
- Run repeatable project tasks (`mise run build`).
- Install release-only binaries from GitHub/registries (`ubi:`, `aqua:`, `cargo:`, `npm:`, `pipx:`, `go:`).

**Not for:** Python app dependency isolation (use a real venv / `uv` / `poetry`; mise manages the *python interpreter version*, not your project packages). System OS packages (use the OS package manager).

## Quick Reference

| Goal | Command |
|---|---|
| Install + pin in **current dir** | `mise use node@22` (writes nearest `mise.toml`) |
| Install + pin **globally** | `mise use -g node@22` (writes `~/.config/mise/config.toml`) |
| Remove a pin | `mise unuse node` / `mise unuse -g node` |
| Install everything from config | `mise install` |
| List installed / active | `mise ls` |

### Tool Versions: Global vs Local (the precedence rule)
### Config File: mise.toml (env + tasks)
### Backends (install from beyond languages)
### Activation: shims vs activate
### one-time: create the profile if missing, then append the dynamic activation hook
### mise trust (security)
### Common Mistakes
### References
