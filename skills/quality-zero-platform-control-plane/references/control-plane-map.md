---
title: control-plane-map
type: note
permalink: dqverify-repo-20261013/skills/quality-zero-platform-control-plane/references/control-plane-map
---

# Control Plane Map

Use this reference when a task needs the ownership map inside `Prekzursil/quality-zero-platform`.

## Core ownership

- `inventory/repos.yml`
  - enrolled repo list
  - repo slug to profile binding
  - rollout wave metadata
  - default branch contract
- `profiles/stacks/*.yml`
  - stack-wide defaults
  - common required contexts
  - common secret and variable expectations
  - shared Codex runner and auth contract
- `profiles/repos/*.yml`
  - repo-specific overrides
  - per-repo required-context differences
  - per-repo coverage command and vendor keys
- `templates/repo/.github/workflows/*`
  - thin wrapper workflows for governed repos
  - expected reusable workflow wiring
  - current controller ref pin behavior
- `templates/repo/AGENTS.md`
  - repo-local strict-zero contributor contract
- `templates/repo/scripts/verify`
  - placeholder only; governed repos must replace it with the real repo-specific verify flow

## Controller scripts

- `scripts/quality/control_plane.py`
  - profile resolution and ruleset payload logic
- `scripts/quality/export_profile.py`
  - workflow-facing profile export
- `scripts/quality/generate_ruleset_payload.py`
  - committed ruleset payload generation
- `scripts/quality/check_required_checks.py`
  - aggregate gate truth source
- `scripts/quality/render_codex_prompt.py`
  - remediation and backlog prompt rendering
- `scripts/quality/run_codex_exec.py`
  - trusted-runner Codex execution

## Live docs

- `README.md`
  - controller scope and governed repo list
- `ROLLOUT_PLAYBOOK.md`
  - wrapper contract and rollout order
- `docs/provider-browser-bootstrap.md`
  - provider-admin browser state outside repo trees
- `docs/codex-private-runner-auth.md`
  - persistent trusted-runner Codex auth contract