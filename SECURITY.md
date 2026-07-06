# Security Policy

## Supported Versions

Security fixes are applied to the `main` branch. This repository is a personal
agent-harness toolchain (agent hooks, skills, and MCP tools); it is not versioned
for downstream redistribution, so only `main` is supported.

| Version | Supported |
| --- | --- |
| `main` | :white_check_mark: |
| Other branches/tags | :x: |

## Reporting a Vulnerability

Please do **not** open public GitHub issues for undisclosed security findings.

Use GitHub Private Vulnerability Reporting for this repository:
<https://github.com/Prekzursil/agent-skills-toolchain/security/advisories/new>

If private advisory reporting is unavailable, contact the maintainer privately on GitHub
(`@Prekzursil`).

When reporting, include:

- the affected component, file, workflow, MCP tool, hook, or dependency
- the exact commit, branch, or release if known
- clear reproduction or proof-of-concept steps
- impact details covering confidentiality, integrity, or availability
- any suggested mitigation if known

## Scope

In scope:

- first-party code in `hooks/`, `skills/`, `tools/` (MCP servers, editor/CLI tooling),
  and `agent-self/`
- the CI/quality workflows under `.github/workflows/`
- the committed dependency lockfiles

Out of scope (report upstream instead):

- vendored third-party code (e.g. `tools/editor/ralph-orchestrator/vendor/**`, the vendored
  `tools/editor/metaswarm/**` framework copy) — report to the upstream project
- findings that require already-compromised local credentials or an already-root host
- the intentionally committed private-env token store documented in `.gitleaks.toml`
  (owner-intentional; tracked separately for rotation)

## Disclosure Expectations

- Initial acknowledgment: best effort within 3 business days.
- Triage update: best effort within 7 business days.
- Coordinated disclosure is expected; please allow time to investigate and patch before
  public disclosure.

## Security Gates

Every change to `main` passes the lean `quality` gate (see [`QUALITY-CHARTER.md`](QUALITY-CHARTER.md)),
which includes SAST (opengrep, curated in-repo ruleset), secret scanning (gitleaks), and a
known-CVE dependency scan (osv-scanner). Secrets must never be hardcoded; use environment
variables and validate their presence at startup.
