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
| List installable versions | `mise ls-remote node` |
| Where is the active binary | `mise which node` / `mise where node` |
| One-off with a version | `mise exec node@20 -- node script.js` |
| Session-only version | `mise shell node@20` |
| Show / upgrade outdated | `mise outdated` / `mise upgrade` |
| Run a task | `mise run <task>` (alias `mise r`) |
| Rebuild shims after install | `mise reshim` |
| Update mise itself | `mise self-update` |

Run `mise <cmd> --help` for flags rather than memorizing them.

## Tool Versions: Global vs Local (the precedence rule)

Two "global" senses, two answers:

1. **Global default versions — fully supported.** `mise use -g <tool>@<ver>` writes `~/.config/mise/config.toml`, which applies in *every* directory. Per-directory config (`mise.toml` / `.mise.toml` / `.tool-versions`) **overrides** global when present (nearest config wins; a parent dir's config can also apply — `mise use` may write a parent file, so check the path it reports).

2. **Adopting tools already installed elsewhere (scoop, system Python) — partial, by design.** mise does **not** scan and absorb existing installs; it shadows them with its own managed copies. To make mise *defer to* an existing binary:
   - **Don't declare it** — anything not in mise config keeps resolving from your normal `PATH` (scoop, system installer) untouched. This is the simplest "leave my global tools alone."
   - **`path:` runtime (reliable, all backends):** point mise at a specific binary, e.g. in `.tool-versions`: `shfmt path:./bin/shfmt` or an absolute path.
   - **`tool@system` (use with care):** e.g. `python@system` means "use whatever's on `PATH`." This is **not a documented mise version scope** — only some legacy asdf-style plugins honor it. Prefer `path:` for reliable, cross-backend behavior.

Global config (`~/.config/mise/config.toml`) example:

```toml
[tools]
node = 'lts'
python = ['3.11', '3.12']   # multiple versions; first is default

[settings]
idiomatic_version_file_enable_tools = ['node']   # read .nvmrc etc.
```

## Config File: mise.toml (env + tasks)

```toml
[tools]
node = '22'

[env]
DATABASE_URL = 'postgres://localhost/dev'
_.file = '.env'             # also load a dotenv file

[tasks.build]
run = 'npm run build'

[tasks.test]
depends = ['build']
run = 'npm test'
```

`mise.toml` (committed) vs `mise.local.toml` (gitignored, machine overrides). `.tool-versions` (asdf format) is also read for tool versions only. Run tasks with `mise run test` (auto-runs its `build` dependency first); list them with `mise tasks`. **mise won't load `[env]` or `[tasks]` until you `mise trust` the directory** (see below).

## Backends (install from beyond languages)

| Prefix | Source | Example |
|---|---|---|
| (core) | built-in languages | `mise use node@22` |
| `ubi:` | any GitHub release binary | `mise use ubi:BurntSushi/ripgrep` |
| `aqua:` | aqua registry | `mise use aqua:cli/cli` |
| `cargo:` | crates.io (builds) | `mise use cargo:ripgrep` |
| `npm:` | npm | `mise use npm:prettier@3` |
| `pipx:` | PyPI apps | `mise use pipx:black` |
| `go:` | Go modules | `mise use go:github.com/...` |

## Activation: shims vs activate

- **Shims (default, works everywhere incl. non-interactive shells & editors):** mise's shims dir is on `PATH`; shim exes resolve the right version on call. No shell hook needed. Check with `mise doctor` → `shims_on_path: yes`.
- **`activate` (faster, enables `[env]`/auto-switching on `cd`):** add a shell hook. If `mise doctor` shows `shell: (unknown)`, activate is **not** set up — you're shims-only.

PowerShell setup (add to `$PROFILE`):

```powershell
# one-time: create the profile if missing, then append the dynamic activation hook
if (-not (Test-Path $PROFILE)) { New-Item -ItemType File -Path $PROFILE -Force }
Add-Content $PROFILE 'mise activate pwsh | Out-String | Invoke-Expression'
. $PROFILE   # reload current session
```

The `mise activate pwsh | Out-String | Invoke-Expression` form re-runs on every shell start, so it always reflects the installed mise (verified working on pwsh 7). `Out-String | Invoke-Expression` is the PowerShell equivalent of bash's `eval "$(...)"`.

bash/zsh: `echo 'eval "$(mise activate bash)"' >> ~/.bashrc` (or `zsh`). After installs that add new binaries, run `mise reshim` if a new bin isn't found.

## mise trust (security)

mise will **not** load `[env]`/`[tasks]` from a directory's config until you trust it (prevents a cloned repo from running arbitrary env/tasks). `mise trust` marks the current config trusted; `mise untrust` reverses it; `trusted_config_paths` in global settings pre-trusts a directory tree.

## CI

```yaml
- uses: jdx/mise-action@v4   # installs tools from mise.toml/.tool-versions, with caching
- run: node -v
```

## Common Mistakes

- **Expecting mise to manage app packages.** It manages the *interpreter/tool version*, not your project's pip/npm deps.
- **Editing the wrong config.** `mise use` writes the *nearest* `mise.toml`, which may be a parent dir. Use `-g` for global or `--path` for an explicit file; confirm the path it prints.
- **Assuming `@system` always works.** It doesn't across all backends — use `path:` when you must reuse an existing binary.
- **`[env]`/tasks "not loading."** The dir isn't trusted yet → `mise trust`.
- **New binary not found after install** → `mise reshim` (shims mode) or reopen the shell (activate mode).

## References

- Docs: https://mise.jdx.dev (`/jdx/mise` on Context7) — configuration, dev-tools, env, tasks.
- `mise doctor` for a full diagnostic of config files, backends, and activation state.
