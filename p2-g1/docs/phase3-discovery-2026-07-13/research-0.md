# SOTA: Single-Source-of-Truth, Portable Config Architecture — Findings + Recommendations for THIS Workspace

## TL;DR verdict (confidence: HIGH)
**Adopt `chezmoi` as the single-source-of-truth engine, backed by ONE private git repo, with `age` encryption for secrets and Go-template per-machine differentiation.** It is the only mainstream tool that is simultaneously: first-class on Windows, copy-based (no symlink dependency), templated per-OS/host, and secrets-aware. GNU Stow is disqualified on Windows (symlink-only). yadm/bare-git is viable but weaker on Windows and templating. Nix home-manager is the most powerful but is a non-starter on native Windows.

**The bigger finding for your box specifically:** the hard problem here is NOT "which tool" — it is that `~/.claude` (34.7 GB), `~/.codex` (3.4 GB), and `~/.agents` (418 MB) are **90%+ runtime state, caches, sessions, sqlite/WAL DBs, and live secrets** — not config. Any architecture MUST split *declarative config* (tracked) from *runtime state* (machine-local, gitignored). Whatever tool you pick, the win comes from a **curated allowlist**, never "track the whole dir."

---

## What the local audit found (confidence: HIGH — direct inspection)
- **No dotfile manager installed** (`chezmoi`/`stow`/`yadm` all absent); `git` present at `C:\Program Files\Git\cmd\git.exe`.
- **None of `~/.claude`, `~/.agents`, `~/.codex` is a git repo**; no `~/.dotfiles`. `~/.mcp.json` exists.
- **Dir sizes:** `.claude` = **34,771 MB**, `.codex` = **3,429 MB**, `.agents` = **418 MB**. Dominated by `codex-sqlite/`, `*.sqlite`+`-wal`+`-shm`, `sessions/`, `archived_sessions/`, `cache/`, `backups/`, `shell_snapshots/`, and dozens of `local.json.<uuid>.tmp` files.
- **Live secrets sit in-tree:** `~/.codex/auth.json`, `~/.claude/.credentials.json`, `~/.codex/secrets/` — all present. These MUST be gitignored/encrypted; a whole-dir track would leak them (ties to your AGENTS.md §9 / §9b blast-radius rule).
- **Partial config-as-code already exists:** `~/source/agent-skills-toolchain` (skills VCS) and `~/.local/opt` (pinned `mcp_agent_mail`). Your memory notes `~/.agents/harness` is "canonical, edit-in-place, NOT git." So you have **fragmented sources of truth today** — the real deliverable is *unifying* them under one deploy engine.

---

## Tool comparison (graded)

| Tool | Windows | Deploy model | Per-machine/OS | Secrets | Verdict |
|---|---|---|---|---|---|
| **chezmoi** | First-class (`winget install twpayne.chezmoi`) | **Copy** (regenerates real files; can also manage symlinks) | Go templates: `chezmoi.os/arch/hostname`, `.chezmoiignore` is itself a template | age/gpg at-rest + live pull from 1Password/Bitwarden/Vault/pass/Keychain | **RECOMMENDED** |
| GNU Stow | Poor (symlink-only; needs Dev Mode/admin) | Symlink | None (dir-per-package convention only) | None | Reject on Windows |
| yadm | OK-ish (bash dependency) | In-place bare-git, no symlinks | `##os.*` alt-files, templates | git-crypt/gpg/transcrypt | Viable fallback |
| bare git (`--git-dir`) | OK | In-place | Manual | Manual | Simplest, most manual |
| Nix home-manager | **No native Windows** (WSL only) | Symlink farm (declarative) | Full (Nix lang) | sops-nix/agenix | Overkill + WSL-only here |

Sources: [chezmoi comparison table](https://www.chezmoi.io/comparison-table/), [Stow or Chezmoi](https://spondicious.com/blog/stoworchezmoi/), [YADM vs Chezmoi vs Nix (BigGo)](https://biggo.com/news/202412191324_dotfile-management-tools-comparison), [chezmoi what-does-it-do](https://www.chezmoi.io/what-does-chezmoi-do/).

### Why copy beats symlink on THIS box (confidence: HIGH)
Windows symlinks are a persistent footgun: creation historically needed elevation; only Developer Mode (Win10 1703+) lets normal users create them, and **Git for Windows disables symlinks by default (`core.symlinks=false`)** — a committed symlink can check out as a *real* link on one machine and as a *plaintext file containing the target path* on another. Stow and Nix both lean on symlink farms; chezmoi's default copy model sidesteps this entirely and stays portable across your Win11 + WSL2 + any Linux fleet box. Sources: [Git for Windows: symbolic links](https://gitforwindows.org/symbolic-links.html), [git-for-windows symlink docs](https://github.com/git-for-windows/git-for-windows.github.io/blob/main/content/symbolic-links.md).

---

## What best-in-class setups actually do (SOTA patterns)

1. **One private git repo = the source of truth**, deployed with an idempotent `apply` (chezmoi `apply`, run repeatedly, converges). Not a pile of copy scripts. ([What does chezmoi do](https://www.chezmoi.io/what-does-chezmoi-do/))
2. **Templates for the 5% that differs per machine**, identical bytes for the 95% that doesn't. `chezmoi.hostname/os/arch` variables branch behavior; `.chezmoiignore` (itself templated) excludes files per-machine. This is the exact pain point that pushes people off Stow/yadm onto chezmoi. ([DeployHQ chezmoi guide](https://www.deployhq.com/guides/chezmoi))
3. **Secrets are NEVER plaintext in git.** Two accepted patterns: (a) **age/SOPS encrypt-at-rest** — commit ciphertext, decrypt on `apply`; add machines by adding public keys, no cloud needed (backup the private key or you're locked out); or (b) **live-pull from a manager at apply time** (1Password/Bitwarden CLI) so secrets never hit disk. Enforce with a **pre-commit secret-scan** (gitleaks — you already run it). Sources: [Secret Management Best Practices](https://dotfiles.io/en/guides/secret-management/), [SOPS+age+Bitwarden](https://mrdvince.me/secure-secret-management-with-sops-age-and-bitwarden-day-26/), [chezmoi age](https://www.chezmoi.io/user-guide/encryption/age/).
4. **Idempotent bootstrap scripts, version-pinned + arch-aware.** chezmoi's `run_once_`/`run_onchange_`/`run_before_`/`run_after_` hooks in `.chezmoiscripts/` install tools and register MCP servers on a fresh machine; a thin shell wrapper handles the pre-`apply` chicken-and-egg (install chezmoi itself). ([chezmoi scripts](https://www.chezmoi.io/user-guide/use-scripts-to-perform-actions/))
5. **Strict state/config separation.** The repo tracks *declarative* config only; runtime state, caches, DBs, sessions, logs are gitignored and regenerated. This is what makes it portable AND keeps the repo small.
6. **CI validation** of the config repo: lint templates (`chezmoi execute-template`), `chezmoi apply --dry-run` on a clean container, run gitleaks, and (for you) `quick_validate.py`-style schema checks on `settings.json`/`.mcp.json`/`config.toml`.

---

## Concrete recommendation for THIS workspace

**Architecture: one private repo `agent-config` (or fold into `agent-skills-toolchain`), chezmoi-deployed, age-encrypted secrets, gitignore-first.**

### Phase 0 — Fix-first (before any tracking) — HIGH confidence, do this regardless of tool
- Author a **strict allowlist**, not a denylist. Track only durable declarative config; everything else stays local.
- **Gitignore/exclude the state & secrets** proven present: `**/*.sqlite*`, `**/*-wal`, `**/*-shm`, `sessions/`, `archived_sessions/`, `cache/`, `backups/`, `shell_snapshots/`, `*.tmp`, `local.json.*.tmp`, `auth.json`, `.credentials.json`, `secrets/`, `history.jsonl`, `memory*.jsonl`. (These are why `.claude` is 34 GB.)

### Files that SHOULD be the tracked source of truth (curated)
- `~/.claude/`: `settings.json`, `CLAUDE.md`, `AGENTS.md`, `rules/`, `commands/` (the curated set), `skills.daily` manifest, `keybindings.json`, hook scripts. **NOT** `cache/`, `backups/`, `event-ledger/`, `agent-memory/`.
- `~/.codex/`: `config.toml`, `AGENTS.md`, `hooks.json`, `rules/`, `mcp-configs/` (sanitized), profile `.toml`s. **NOT** `auth.json`, `*.sqlite*`, `sessions/`, `memories*`.
- `~/.agents/`: `agents.json`, `agent-roles/`, `subagent-profiles.md`, `harness/` (this makes the "canonical, not git" harness finally version-controlled — closes a real gap), `workflows/`. **NOT** `local.json.*.tmp`, `state/`, `generated/`, caches.
- `~/.mcp.json` **canonical** (you already treat it as canonical via `promote-mcp-userscope.ps1`) — track it, keep secrets as `{{ }}` template refs, not literals.

### Phase 1 — Stand up chezmoi
```
winget install twpayne.chezmoi
chezmoi init            # creates ~/.local/share/chezmoi (the repo)
age-keygen -o ~/.config/chezmoi/key.txt   # secrets key — BACK IT UP off-box
```
Add the allowlisted files with `chezmoi add` (and `--encrypt` for anything sensitive), templatize the per-machine bits (`{{ .chezmoi.os }}`, `{{ .chezmoi.hostname }}`), and put runtime junk in `.chezmoiignore`.

### Phase 2 — Per-machine differentiation you'll actually need
Your Win11 box vs a Linux fleet box differ on: paths (`C:\Users\...` vs `/home/...`), the PowerShell-vs-bash split, MCP server commands, and which heavy Python MCPs are enabled (`.mcp-disabled-defaults.json`). Model these as template conditionals keyed on `.chezmoi.os`, not as forked files.

### Phase 3 — Secrets
- Encrypt `auth.json`, `.credentials.json`, any token-bearing `config.toml` fragments with **age** at rest, OR (cleaner) pull them live from a manager. Given you already juggle many API keys, a manager (Bitwarden CLI — you're cost-conscious, it's open-source) as single source for keys is worth it: change once, `apply` everywhere. Keep gitleaks as the pre-commit backstop.

### Phase 4 — Bootstrap + CI
- One `install.ps1` / `install.sh` that installs chezmoi then `chezmoi init --apply <repo>` — new machine to fully-configured in one command.
- `.chezmoiscripts/run_onchange_*` to (re)register MCP servers (`claude mcp add ...`), run `promote-mcp-userscope.ps1`, and re-symlink `skills.daily`.
- CI: `chezmoi execute-template` lint + `apply --dry-run` in a clean container + gitleaks + your JSON/TOML schema validators.

---

## Windows-specific non-negotiables (ties to your rules/common/windows-shell.md)
- **Prefer chezmoi's copy model**; if you ever manage a symlink, know it needs Developer Mode + `git config core.symlinks true`, and will silently degrade to a text file elsewhere.
- **`.gitattributes` with `*.sh eol=lf` and `*.ps1 eol=crlf`** in the config repo — your ledger already recorded CRLF breaking `.sh` under real WSL. chezmoi honors this on regeneration.
- Do the initial `chezmoi add` of device/secret files in **PowerShell**, not Git-Bash, to avoid the MSYS `/…` path-conversion truncation trap.

---

## Confidence + post-cutoff flags
- **HIGH:** local audit facts (direct inspection); chezmoi Windows/copy/template/secrets capabilities; Stow symlink disqualifier; Windows Git symlink degradation; state/config split necessity.
- **MEDIUM:** exact allowlist boundaries per dir (I inferred durable-vs-state from dir names + sizes; confirm a few ambiguous ones like `~/.claude/ecc/`, `anti-degen/`, `calibrated-silence/` before deciding track-vs-ignore).
- **Post-cutoff flag (my knowledge cutoff Jan 2026):** several cited pages are dated 2026 ([recca0120 chezmoi guide 2026-04](https://recca0120.github.io/en/2026/04/13/chezmoi-dotfiles-management/), [Lorenzo Bettini bootstrap 2026-06](https://www.lorenzobettini.it/2026/06/bootstrapping-chezmoi_modify_manager-before-chezmoi-apply/), [DEV "Top 6 secrets tools 2026"](https://dev.to/thedailyagent/top-6-secrets-management-tools-for-devs-in-2026-4ahe)) — treat their specific version/pricing claims as unverified-current; the *architecture* they describe is stable and matches pre-cutoff SOTA. Perplexity deep-research could not run (session token not authenticated) — findings rest on WebSearch + direct inspection, which was sufficient.

## Sources
- [chezmoi comparison table](https://www.chezmoi.io/comparison-table/) · [what does chezmoi do](https://www.chezmoi.io/what-does-chezmoi-do/) · [chezmoi age encryption](https://www.chezmoi.io/user-guide/encryption/age/) · [chezmoi scripts](https://www.chezmoi.io/user-guide/use-scripts-to-perform-actions/) · [.chezmoiignore](https://www.chezmoi.io/reference/special-files/chezmoiignore/)
- [Stow or Chezmoi](https://spondicious.com/blog/stoworchezmoi/) · [YADM vs Chezmoi vs Nix (BigGo)](https://biggo.com/news/202412191324_dotfile-management-tools-comparison) · [Migrating Stow→chezmoi](https://rednafi.com/misc/chezmoi/)
- [DeployHQ chezmoi guide](https://www.deployhq.com/guides/chezmoi) · [chezmoi across macOS/Linux/Windows](https://dev.to/recca0120/chezmoi-one-dotfiles-repo-across-macos-linux-and-windows-2o3)
- [Git for Windows: symbolic links](https://gitforwindows.org/symbolic-links.html) · [git-for-windows symlink docs](https://github.com/git-for-windows/git-for-windows.github.io/blob/main/content/symbolic-links.md)
- [Secret Management Best Practices (dotfiles.io)](https://dotfiles.io/en/guides/secret-management/) · [SOPS+age+Bitwarden](https://mrdvince.me/secure-secret-management-with-sops-age-and-bitwarden-day-26/) · [SOPS+age+1Password](https://paulocurado.com/blog/managing-secrets-with-sops-age-and-1password/)
