# Upstream sources

- GitHub repository: https://github.com/mikeyobrien/ralph-orchestrator
- Documentation home: https://mikeyobrien.github.io/ralph-orchestrator/
- Quick start: https://mikeyobrien.github.io/ralph-orchestrator/getting-started/quick-start/
- Backends guide: https://mikeyobrien.github.io/ralph-orchestrator/guide/backends/
- Configuration guide: https://mikeyobrien.github.io/ralph-orchestrator/guide/configuration/
- CLI reference: https://mikeyobrien.github.io/ralph-orchestrator/guide/cli-reference/
- Public skills package README: `vendor/skills/README.md`

Pinned upstream snapshot:
- version: `2.8.1` (nominal; the commit is `v2.9.0~1`, see `README.md` Provenance)
- commit: `9673d910e88fbe8ed41787f9a433cdd697e7ec3f`
- latest upstream release at last check (2026-09-01): `v2.10.1`, commit `407cb96b25a5705a779d598282d070e6f80f712c`, published 2026-06-23; `main` was at `edc2b326` (2026-08-25). Not re-vendored -- see the README re-vendor checklist for the measured reasons and the breaking changes to handle when it is.

Key upstream facts used by the local wrapper:
- Ralph supports `claude`, `gemini`, and `codex` as first-class backends.
- Upstream installation docs recommend npm first, but the current `@ralph-orchestrator/ralph-cli` package rejects `Windows_NT x64` and a direct Windows cargo build fails inside `ralph-adapters`; the Windows-first local wrapper therefore defaults to a WSL-backed Linux binary install.
- The v2.8.1 release publishes Linux tarballs (for example `ralph-cli-x86_64-unknown-linux-gnu.tar.xz`) that unpack to a `ralph` binary under the archive root. Releases from v2.9.3 onward publish `*-unknown-linux-musl.tar.xz` instead (gnu tarballs stop at v2.9.2), so the install script's hardcoded gnu name is only valid while `$Version` <= 2.9.2.
- `ralph mcp serve` is workspace-scoped and resolves workspace root in this order:
  1. `--workspace-root`
  2. `RALPH_API_WORKSPACE_ROOT`
  3. current working directory
- The public upstream skill package exposes `ralph-hats` and `ralph-loop`.
