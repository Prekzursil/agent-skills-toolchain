# Quality Charter — Lean Deterministic Gate Model

This repository runs a **closed set of 6 deterministic, local-first quality gates** behind
**one** CI workflow named `quality`. Every gate is a tool that runs the same way locally and
in CI, with **pinned versions** and an **in-repo config**. There is no SaaS quality platform,
no baseline file, and no auto-fetched ruleset.

This is the `agent-skills-toolchain` adoption of the QZT lean-gate model
([Prekzursil/quality-zero-platform](https://github.com/Prekzursil/quality-zero-platform) —
`reusable-quality.yml`) as proven in [Prekzursil/reframe](https://github.com/Prekzursil/reframe).
It is a **multi-package monorepo** (agent hooks, skills, and MCP tools) whose *tested surface*
is two shipped Python packages — `tools/mcp-manager` and `tools/scholarly-access-mcp` — plus the
node workspaces; the hundreds of skill/hook helper scripts are linted, format-checked, and
SAST/secret-scanned, but are not a 100%-coverage target.

## The closed gate list

<!-- BEGIN GATES (keep this table in sync with .quality/charter.yml and .github/workflows/quality.yml) -->

| # | Gate | Tool(s) (pinned) | What it enforces |
|---|------|------------------|------------------|
| 1 | lint-format | ruff 0.15.17 | Lint + format + security-lint across Python (`ruff check` + `ruff format --check`), honoring `ruff.toml`. Auto-fixers: `ruff check --fix`; `ruff format`. |
| 2 | types | basedpyright 1.39.8 | `basedpyright` (standard mode) over the SOURCE of the two shipped packages — `tools/mcp-manager` (`core`, `ui`, `app.py`) and `tools/scholarly-access-mcp` (`scholarly_access`) — each checked from its own root with deps installed. |
| 3 | tests-coverage | pytest + pytest-cov (branch, `--cov-fail-under=100`) · node `--test` | Strict 100% line+branch coverage for the two Python packages, plus the node workspace tests (root + `tools/web/agentify-desktop`). Reasoned `# pragma: no cover -- <reason>` only. |
| 4 | sast | opengrep 1.23.0 (CI) / semgrep CE 1.166.0 (local) | Static security analysis using the curated in-repo ruleset under `.quality/opengrep/` (NOT `--config auto`). Clean-zero lock: 0 findings, no baseline. |
| 5 | secrets | gitleaks | Secret scanning with the committed `.gitleaks.toml` allowlist (owner-intentional private-env store + reasoned doc/fixture placeholders). Gate on 0. |
| 6 | deps | osv-scanner 2.x | Known-CVE scan of the committed npm lockfiles (root + `agentify-desktop`). Reasoned per-CVE ignores only in `osv-scanner.toml`; no baseline. Gate on 0. |

<!-- END GATES -->

Dependency freshness is additionally automated via **Dependabot** (`.github/dependabot.yml`)
and `dependabot-auto-merge.yml`; that is supply-chain hygiene, **not** part of the 6-gate set.

## Rules of the charter

1. **One CI workflow.** All gates run inside the single `quality` workflow in
   `.github/workflows/quality.yml` (one job per gate, all under that workflow).
2. **One-in / one-out.** The gate list is closed. Adding a gate requires removing one (or an
   explicit charter amendment). Changing a tool requires updating its pinned version here, in
   `.quality/charter.yml`, and in `quality.yml` together.
3. **Determinism.** Every tool is version-pinned and configured from an in-repo file. No
   `--config auto`, no registry login, no network-fetched rule packs in the gate.
4. **Clean-zero, no baselines.** Gates reach zero by fixing the finding or by a **reasoned,
   greppable** suppression (`# pragma: no cover -- …`, `# noqa: <rule> -- …`,
   `# nosemgrep: <rule-id> -- …`, a `.gitleaks.toml` allowlist entry, or a dated per-vuln ignore
   in `osv-scanner.toml`). We do not carry baseline / "accepted findings" files.
5. **Charter ↔ workflow sync.** `.quality/charter_check.sh` parses `.quality/charter.yml` and the
   `gate-<slug>` markers in `quality.yml` and fails CI if they diverge.

## Notes on specific decisions

- **Inline gates, not a thin `uses:` caller of `reusable-quality.yml`.** The QZT reusable
  workflow auto-detects a tree and runs **one whole-repo** Python coverage lane
  (`pytest --cov --cov-fail-under=100`) and **one whole-repo** basedpyright lane. This monorepo
  has hundreds of untested skill/hook scripts beside the two 100%-covered packages, and
  basedpyright needs each package's deps installed from its own root — so a whole-repo coverage
  or type lane cannot pass. We adopt the lean **model** inline (same pinned tools, same curated
  SAST ruleset, same charter) with the per-package lanes the monorepo needs. If the reusable
  workflow gains per-package inputs, `quality.yml` can become a thin caller.
- **SAST = curated in-repo ruleset, not `--config auto`.** `--config auto` fetched 1074 drifting
  community rules (non-deterministic) and produced registry false-positives (e.g.
  `python36-compatibility` on a 3.11+ codebase). Gate 4 uses the curated
  `.quality/opengrep/` set (the reframe rules: injection / unsafe-deserialization /
  unsafe-subprocess / weak-crypto / XSS / insecure-DOM / insecure-randomness / hardcoded-secret).
  Supply-chain *freshness* advisories (uv cooldown, npm min-release-age) are covered by the
  osv-scanner gate + Dependabot, not the SAST gate.
- **Actions are SHA-pinned** in `quality.yml` for supply-chain hardening (bump the SHA and the
  `# vX` comment together).
- **basedpyright mode = `standard`** (not `strict`) so "literal zero" stays achievable on
  partly-untyped utility code and untyped third-party libraries.
