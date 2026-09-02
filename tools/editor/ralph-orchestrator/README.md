# Ralph Orchestrator

`tools/editor/ralph-orchestrator/` is the repo-owned Windows-first integration layer for the upstream `mikeyobrien/ralph-orchestrator` framework.

## Provenance
- **Curated upstream snapshot**: `mikeyobrien/ralph-orchestrator` version `2.8.1`, commit `9673d910e88fbe8ed41787f9a433cdd697e7ec3f`
  - Measured 2026-09-01 (`git describe --tags --contains 9673d91` in an upstream clone): that commit is `v2.9.0~1`, 39 commits past the `v2.8.1` tag. The tree carries `2.8.1` in `package.json`/`Cargo.toml` only because upstream's version bump is the very next commit; the code is the v2.9.0 release candidate (agent waves, `wave.rs`, `urgent_steer.rs`, `tool_preview.rs` are all present).
  - `diff -rq` against upstream at that commit: identical except `.agents/`, `.ralph/`, `prompts/`, `PROMPT.md` (deliberately not vendored) and the two deviations below.
- **Deliberate deviations from the upstream commit** (the only files under `vendor/` that are not byte-identical to upstream):
  - `vendor/package-lock.json` is patched in place for security: 83732eaa (2026-04-04, picomatch) and the 2026-09-01 `npm audit fix --package-lock-only` + `npm update tsx --package-lock-only` pass. The three `package.json` files are untouched, so every resolved version still sits inside the semver range upstream declared. This lockfile is scanned by the `gate-deps` CI job; see the runbook below.
  - `vendor/frontend/ralph-web/src/lib/utils.ts` is force-added (`git add -f`). Upstream tracks it, but the vendored copy of upstream's `.gitignore` has a Python-section `lib/` rule that dropped it at vendoring time, which left 28 dashboard modules importing `@/lib/utils` from a file that did not exist -- `vitest run` failed on every test file with `Failed to resolve import "@/lib/utils"` until it was restored (measured 2026-09-01). Re-add it with `-f` after any future re-vendor.
- **Repo-owned wrapper**: local install, MCP registration, cross-agent skill install, and validation helpers for Codex, Claude, and Gemini

## Lockfile security runbook (vendor/package-lock.json)
`gate-deps` reads this lockfile, so a newly published advisory turns that required check red on every branch; GitHub's dependency graph skips `vendor/` paths, so Dependabot will not open the fix. Do it by hand:

```bash
cd tools/editor/ralph-orchestrator/vendor
npm audit fix --package-lock-only        # never --force: it downgrades drizzle-kit 0.31 -> 0.18
npm audit --package-lock-only            # expect only the drizzle-kit -> @esbuild-kit chain (see osv-scanner.toml)
npm ci && npm test && npm run build      # backend 178 tests via tsx --test, dashboard 144 via vitest, tsc + vite build
git diff --stat -- package.json backend/*/package.json frontend/*/package.json   # must be empty
```

If `npm audit fix` cannot clear a finding without touching a `package.json`, that is a re-vendor decision, not a lockfile patch: record it and stop.

## Re-vendor checklist (measured 2026-09-01 against upstream v2.10.1, the latest release)
Re-vendoring is a framework upgrade, not a security fix: upstream's own `v2.10.1` lockfile audits at **22** npm findings (1 critical, 13 high) versus **17** here before the patch, and upstream `main` @ `edc2b326` (2026-08-25) audits the same 22. Whoever re-vendors must therefore run the runbook above afterwards anyway, and must also handle these breaking changes found in the `9673d91..v2.10.1` delta (50 commits, 219 files, +21,401/-1,365 lines excluding upstream's own `.agents`/`.ralph`/`prompts`/`specs`/`tasks`):
- **Release artifact rename (v2.9.3):** Linux targets switched from `*-unknown-linux-gnu` to `*-unknown-linux-musl` (upstream `Cargo.toml` `[workspace.metadata.dist] targets`). `scripts/install-ralph-orchestrator.ps1` hardcodes `ralph-cli-x86_64-unknown-linux-gnu` on five lines (download path, release URL, WSL archive path, extracted directory, symlink target); bumping its `$Version` default past `2.9.2` without renaming those 404s the `wsl-release` install.
- **Claude backend default (v2.9.3):** child sessions now pass `--setting-sources project,local`, so user-level `~/.claude/settings.json` hooks, plugins and MCP servers no longer flow into Ralph runs. Opt back in with `cli.args: ["--setting-sources", "user,project,local"]` if the local workflow relied on that.
- **Hats surface (v2.9.3, v2.10.0):** presets unified under `-H <name>` (YAML and TOML), and each entry under `hats:` may now carry a per-hat `import: <local file path>` resolved in preflight (upstream commit 25afeb0; remote, embedded and preset-dir import sources are rejected). The top-level hats keys the `.agents/skills/ralph-hats` skill allows (`name`, `description`, `events`, `event_loop`, `hats`) are unchanged, so the skill stays correct; add the per-hat `import` field to its `references/schema.md` when the snapshot moves.
- **Rust toolchain:** the workspace is `edition = "2024"` at both commits, which needs Rust >= 1.85 (`cargo +1.83.0 metadata --no-deps` fails to parse `crates/ralph-proto/Cargo.toml`, exit 101); the release-bump skill and the `cargo install ralph-cli` path assume a current stable.
- **Version pins to move together:** `scripts/install-ralph-orchestrator.ps1` `$Version`, this README, `references/upstream-sources.md`, and the `Provenance` commit above; then re-apply the two deviations listed there.

## Why this exists
Ralph is a host-local orchestration framework with:
- a local CLI (`ralph`)
- a workspace-scoped MCP server (`ralph mcp serve`)
- a public skill package (`ralph-hats`, `ralph-loop`)

This repo vendors the upstream snapshot so the framework shape is inspectable and pinned, while the local wrapper keeps workstation install, MCP registration, and skill rollout deterministic.

## Local install shape
- vendored snapshot: `tools/editor/ralph-orchestrator/vendor/`
- default CLI install on this Windows workstation: WSL-backed prebuilt Linux binary unpacked under `~/.local/opt/ralph-orchestrator/` with `~/.local/bin/ralph` symlinked to the extracted binary
- the install helper also writes WSL-visible `claude` and `gemini` wrappers under `~/.local/bin/` so `ralph doctor` can see the Windows-hosted backends from inside WSL
- npm registry install remains available for non-Windows targets, but the current upstream npm package does not ship a Windows x64 artifact
- current Windows host execution path: `C:/Windows/System32/wsl.exe -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; /home/prekzursil/.local/bin/ralph mcp serve'`
- Codex MCP entry: `mcp_servers."ralph-orchestrator"` in the canonical `config.toml`
- Claude MCP entry: user-scoped `claude mcp` registration for `ralph-orchestrator`
- Gemini MCP entry: `"ralph-orchestrator"` in `C:/Users/Prekzursil/.gemini/settings.json`
- mirrored skills:
  - canonical repo-published copies under `.agents/skills/`
  - compatibility copies under `skills/`

## Operator flow
1. Run `scripts/install-ralph-orchestrator.ps1`
2. Run `scripts/validate-ralph-orchestrator.ps1`
3. Confirm `ralph --version` and `ralph doctor` succeed locally
4. Confirm the three MCP registrations point at `ralph mcp serve`
5. Confirm `ralph-hats`, `ralph-loop`, and `ralph-orchestrator-setup` are installed for Codex, Claude, and Gemini

## Stop rules
- Keep the global MCP registration workspace-agnostic; do not hardcode `--workspace-root` into the user-level server entry unless the user explicitly wants one-repo-only behavior.
- Treat the Ralph CLI, its MCP server, and the mirrored skills as separate verification surfaces. Do not claim the integration is healthy unless all three are checked.
- If `ralph doctor` or any client-specific MCP health check fails, report the exact blocked state instead of downgrading silently.
- Do not edit files inside `vendor/` unless you are intentionally refreshing the upstream snapshot. The one standing exception is the lockfile security runbook above, which changes `vendor/package-lock.json` only and never a `package.json`.
