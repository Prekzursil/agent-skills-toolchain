# Cross-platform release layer for agent-skills-toolchain

## 1. Recovered Facts

### Confirmed facts from the current repo/docs
- The repo is a private, personal-account, Windows-first platform repo.
- The current live surfaces are `skills/`, `tools/mcp/`, `tools/editor/`, and `tools/web/`.
- `tools/mcp/` is the Codex-side orchestration lane; `tools/web/` is the PromptBridge/Agentify talk-only sidecar lane.
- `tools/editor/` is already first-class for editor-local deliverables such as Prompt Optimizer.
- The active Windows `CODEX_HOME` remains the canonical runtime root.
- `.codex-vscode` is migration/comparison input only, not a second writable home.
- Current bootstrap/runtime logic already contains platform-aware path handling under `tools/mcp/agent-lanes-codex/local-overrides/bootstrap.mjs`.
- The repo currently has no root `package.json`; that is consistent with keeping the root runtime/install graph clean.

### Likely implications / inferences
- Future Windows/Linux/macOS support should be a packaging layer around the existing surfaces, not a rewrite of the runtime model.
- PromptBridge/Agentify should remain a talk-only sidecar even when packaged on Linux/macOS.
- Editor-local packaging should stay visibly separate from MCP and web tooling.

### Still-open decisions
- The exact artifact type per platform had not already been fixed in the repo.
- Release CI/workflows do not exist yet and must be introduced as packaging-only infrastructure.

## 2. Decided Goal

Keep the repo Windows-first and execution-authoritative through Codex, while adding a future packaging layer that can ship platform-specific launcher/bundle artifacts for Windows, Linux, and macOS without changing the live runtime/install graph.

## 3. How It Should Work

- Keep `skills/`, `tools/mcp/`, `tools/editor/`, and `tools/web/` as the only live execution surfaces.
- Add a packaging-only `release/` workspace that assembles, describes, and validates platform bundles.
- Treat Windows as the canonical workstation reference. Linux and macOS bundles should coexist as supported alternative hosts, not the new default architecture.
- Keep PromptBridge/Agentify inside the talk-only boundary; release packaging must not turn it into an executor.

## 4. Proposed Cross-Platform Release Architecture

### Recommended direction
Release **multiple thin platform bundles**, not one monolithic cross-platform application.

### What gets released
- **Windows**: portable bootstrap bundle plus the Prompt Optimizer VSIX, config templates, and launch helpers.
- **Linux**: thin tarball with lane launchers, config templates, and docs for local `CODEX_HOME` resolution.
- **macOS**: thin tarball with lane launchers, config templates, and docs for local `CODEX_HOME` resolution.

### What remains source-only
- `skills/`
- `tools/mcp/*`
- `tools/editor/*`
- `tools/web/*`
- incubation docs and repo-level docs

### Packaging boundary
All packaging-only code and dependencies live under `release/` so the root runtime/install graph remains clean.

## 5. Repo / CI / Packaging Changes

### Repo additions
- `release/README.md`
- `release/package.json`
- `release/shared/README.md`
- `release/platforms/windows/README.md`
- `release/platforms/linux/README.md`
- `release/platforms/macos/README.md`
- `release/manifests/README.md`

### CI additions (proposed next step)
- `.github/workflows/release-bundle.yml`
- `.github/workflows/release-smoke.yml`

These should be isolated from normal repo validation and should only run for packaging or release concerns.

## 6. Validation Plan

### Repo-root validation
- skills validator
- live helper-script smoke tests
- lane-specific bundle validator(s)

### Release-layer smoke tests
- generated artifact shape per platform
- launcher/config integrity
- lane boundary checks proving MCP and web tooling remain separate
- `CODEX_HOME` detection on each platform

### Stop rules
- stop if packaging adds root runtime dependencies
- stop if PromptBridge/Agentify becomes the executor
- stop if Linux/macOS packaging changes Windows-first defaults in the base docs/runtime

## 7. Risks / Non-goals / Open Questions

### Non-goals
- flattening `tools/mcp/` and `tools/web/` into one generic product
- making PromptBridge/Agentify the executor
- turning `release/` into a fifth live runtime surface
- reintroducing WSL-first assumptions into the default workflow

### Risks
- platform bundles may drift from the canonical Windows bootstrap logic if they duplicate behavior instead of reusing manifests and templates
- packaging-only dependencies can creep into the root graph if release tasks are not isolated

### Open questions
- Windows installer vs portable zip should be deferred; portable bundles are the safer first step
- Signed macOS installer work should be deferred until portable tarballs and validation are stable

## 8. Step-by-step Implementation Plan

1. Keep the current runtime surfaces unchanged.
2. Add the `release/` workspace skeleton and document that it is packaging-only.
3. Add platform README placeholders that define artifact assumptions and lane boundaries.
4. Add release manifests/shared templates once the first bundle format is chosen.
5. Add release-only CI workflows after the workspace exists and a first artifact layout is agreed.
6. Add platform smoke tests that validate bundle integrity without changing runtime behavior.
7. Only after the packaging layer stabilizes, decide whether Windows/macOS/Linux need installer-based artifacts or can stay portable.
