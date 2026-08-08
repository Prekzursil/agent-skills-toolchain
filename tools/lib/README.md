# `tools/lib` — shared generic utilities for `tools/`

## Why this tree exists

`tools/` had 36 top-level entries and **no generic-utility tree**. Every helper lived inside the
one tool that first needed it, so when a tool was retired its reusable parts were retired with it.
This directory is the convention created to stop that: a home for small, dependency-free helpers
that are useful to more than one tool.

It was created as the **salvage destination for the ChatGPT-web retirement** — the removal of
`tools/web/agentify-desktop/`, `tools/web/promptbridge-talk-lane/`,
`tools/web/agent-lanes-chatgpt-web/`, `tools/mcp/codex-orchestrator/` and
`tools/mcp/agent-lanes-codex/`. Six extracts survived that retirement on the grounds that nothing
in them knew about a browser, an Electron shell, or the promptbridge transport. They are here;
everything else went.

## What belongs here

A module qualifies if **all** of these hold:

1. **Generic.** It is useful to more than one tool, or would be if another tool existed. No
   knowledge of a specific product, transport, or vendor UI.
2. **Dependency-free.** Node builtins only. No `dependencies` block, ever. `tools/lib` must never
   become a reason to run `npm install`, and must never appear in a vulnerability scan.
3. **Tested.** Every module has a suite under `tests/`. An untested helper here is worse than a
   private one, because the blast radius of a bug is now every consumer.
4. **Provenance-carrying.** If the code was moved from somewhere, the file header names the origin
   path and says why it survived. Salvaged code with no provenance is indistinguishable from code
   nobody can account for.

## What does NOT belong here

- Anything tool-specific — it belongs in that tool's own directory.
- Anything needing a third-party package (rule 2).
- A second implementation of something a tool already owns. Import it or move it; do not fork it.
- Python. This tree is Node/ESM only.

## Contents

| Module | Salvage id | Origin | Why it survived |
|---|---|---|---|
| `security.mjs` | K4 | `tools/web/agentify-desktop/orchestrator/security.mjs` | Path containment for any tool writing under an allowed root. **Two shipped defects fixed** — see below. |
| `workspace.mjs` | K2 | `tools/web/agentify-desktop/orchestrator/workspace.mjs` | Repo-root / package-manager / test-command detection. Pure filesystem. |
| `git-diff.mjs` | K1 | `tools/web/agentify-desktop/orchestrator/git-diff.mjs` | Priority-ranked, char-budgeted diff packet for **any** reviewer. |
| `handled-ledger.mjs` | K3 | `tools/web/agentify-desktop/orchestrator/storage.mjs` (partial) | Idempotency ledger + atomic JSON write. Exactly what a fan-out needs to avoid double-dispatch. |
| `net-allowlist.mjs` | K5 | `tools/web/agentify-desktop/http-api.mjs:6-29` | Loopback + opt-in private-network allowlist for any local server. |
| `codex-invocation.mjs` | K7 | `tools/mcp/codex-orchestrator/src/orchestrator/codex.mjs:32-64` | Windows Codex-binary resolution. **Two shipped defects fixed** — see below. |

`K6` (`defaultStateDir`) was deliberately **dropped**: its only consumer was
`codex-orchestrator/src/codex-orchestration.mjs`, which the retirement deletes, so it is moot.

## Defects fixed during salvage (not carried forward)

These were live in the retired code. They are fixed here, each with a regression test that
includes a control reproducing the original wrong behaviour.

**`security.mjs` — containment was bypassable on Windows.**
`path.relative('C:\\allowed\\root', 'D:\\x')` returns the absolute `D:\x`, which neither starts
with `..\` nor equals `..`, so the original predicate returned `true` for **any path on another
volume** and for **any UNC path**. A UNC target additionally coerces an outbound SMB/NTLM
authentication. The original test suite passed because it never tried a second volume. Fixed by
comparing `path.parse().root` (case-insensitively, since `path.win32` preserves a lowercase drive
letter) and rejecting UNC outright.

**`codex-invocation.mjs` — the two cross-vendor-dispatch blockers.**

- *Prompt passed as argv.* Windows `CreateProcess` caps the command line at 32,767 characters;
  this failed in production at `payload_len=34472` → `os error 206`. The prompt is now written to
  a **file** and streamed to the child's stdin, with argv carrying only the literal `-`.
  Note: `codex` has **no `--prompt-file` flag** — that belongs to a different local wrapper.
  Verified against `codex exec --help` (codex-cli 0.145.0): *"If not provided as an argument (or if
  `-` is used), instructions are read from stdin."*
- *`--ignore-user-config` absent.* It appeared nowhere in the repo. It is the documented #1
  execution blocker for non-interactive dispatch — without it the active MCP inventory is loaded
  into the invocation, which is what blows the arg limit above. Now emitted **by default**.

## Testing

```bash
cd tools/lib
npm test              # node --test tests/*.test.mjs  — no install required
```

Zero dependencies, so there is no `node_modules` step. Windows path semantics are exercised via an
injectable `pathImpl` (`path.win32`), so the containment tests assert identically on a Windows dev
box and a Linux CI runner — a suite that only ran the host's semantics would be silent about the
very defect it exists to catch.

Each suite carries at least one **control** that reproduces the known-bad behaviour and requires it
to fail. If a control goes red, the corresponding assertions have stopped discriminating and their
green means nothing.

## Not yet wired into CI

`tools/lib` is **not** in the root `package.json` `workspaces` array and has no
`gate-tests-coverage` step in `.github/workflows/quality.yml`. That was left out on purpose: the
same `workspaces` array still lists two directories the retirement deletes, so editing it belongs
to the de-registration commit rather than to the salvage. Until that lands, `npm test` here is
run directly.
