---
name: skill-router
description: Use when starting work in any repository or when unsure which skills and quality tools apply - auto-detects repo stack, active CI gates, and invokes the correct combination of quality enforcement skills
---

# Skill router

## Overview

**Detect the repo. Pick the skills. No human memory required.** This skill reads project config files to determine the tech stack, identifies which CI quality gates are active, and loads the correct skill combination automatically.

## When to use

- Starting work in any repository (first message of a session)
- Switching between repos in the same session
- Unsure which quality gates apply to the current project
- After cloning or checking out a new branch

## Detection protocol

Run these checks IN ORDER. Stop reading a category once matched.

### Step 1 — Identify stack

| Check for | Stack | Primary language |
|-----------|-------|-----------------|
| `package.json` | Node.js / TypeScript | Check for `"type": "module"`, TSConfig |
| `pyproject.toml` OR `setup.py` OR `requirements.txt` | Python | Check Python version in config |
| `*.csproj` OR `*.sln` | C# / .NET | Check TargetFramework |
| `Cargo.toml` | Rust | Check edition |
| `tauri.conf.json` | Tauri (Rust + TS) | Multi-stack — apply both |

### Step 2 — Identify active gates

Scan these locations for gate configuration:

```
.github/workflows/*.yml    → CI pipeline (look for: codacy, sonar, semgrep, codecov, deepsource, qlty, sentry)
.codacy.yml                → Codacy config present
sonar-project.properties   → SonarCloud/SonarQube active
.semgrep.yml               → Semgrep rules
codecov.yml                → Codecov config
.deepsource.toml           → DeepSource active
.chromatic                 → Chromatic visual testing
applitools.config.js       → Applitools visual testing
.storybook/                → Storybook present (implies visual regression possible)
```

### Step 3 — Load skill combination

Based on detection results, invoke these skills:

**Always load:**
- `gate-zero-enforcer` — universal gate thresholds
- `verification-before-completion` — evidence before assertions

**Per-stack additions:**

| Stack | Additional skills | Why |
|-------|------------------|-----|
| Node.js / TS | `test-driven-development` | Jest/Vitest coverage enforcement |
| Python | `test-driven-development` | pytest-cov, Bandit, Lizard |
| C# / .NET | `test-driven-development` | xUnit, dotnet test coverage |
| Tauri | Both Node.js + Rust patterns | Multi-stack repo |

**Per-gate additions:**

| Gate detected | Load | Action |
|---------------|------|--------|
| Codacy | `gate-zero-enforcer` (Codacy section) | CCN ≤ 15, 0 issues, 100% diff coverage |
| SonarCloud | SonarSource MCP `get_guidelines` | Fetch project-specific rules before writing |
| Semgrep | `semgrep/skills` | Auto-scan generated files |
| DeepSource | `DeepSourceCorp/skills` | Autofix bot integration |
| Codecov | `gate-zero-enforcer` (Codecov section) | Patch coverage 100% |
| Sentry | Sentry MCP `find_issues` | Check for existing runtime errors |
| Chromatic/Applitools | `visual-regression-guard` | Story coverage for component changes |
| QLTY / DeepScan | `gate-zero-enforcer` (per-function limits) | Lizard thresholds |

### Step 4 — Report detection

After detection, output a brief summary:

```
Stack: [detected stack]
Gates: [list of active gates]
Skills loaded: [list]
Special notes: [any repo-specific quirks]
```

## Repo-specific knowledge

### Prekzursil repositories

| Repo | Stack | Special gates | Notes |
|------|-------|--------------|-------|
| Reframe | Python/FastAPI + TS/React + Tauri/Rust | All standard gates | Multi-stack, apply all patterns |
| WebCoder | Python | Standard gates | Backend focused |
| OmniAudit MCP | TypeScript | Standard gates | GitHub PR triage tool |
| SWFOC Trainer | C# / .NET / WPF | Standard gates | Desktop app, WPF-specific patterns |
| pbinfo-get-unsolved | Node.js 20 | ESLint 9 + Prettier 3 | Competitive programming — performance matters |
| quality-zero-platform | Meta (governance) | Controls OTHER repos' gates | Profile YAML validation, JSON Schema |

### Multi-stack repos (Reframe, Tauri apps)

When a repo contains BOTH `package.json` AND `pyproject.toml` (or `Cargo.toml`):
- Apply quality rules for EACH stack independently
- Python complexity thresholds apply to `.py` files only
- TypeScript/ESLint rules apply to `.ts`/`.tsx` files only
- Rust clippy warnings apply to `.rs` files only
- Coverage is measured per-stack (Python pytest-cov, JS jest/vitest, Rust tarpaulin)

## Common mistakes

| Mistake | Consequence |
|---------|------------|
| Applying Python rules to TypeScript files | False positives, wasted effort |
| Forgetting Chromatic on component repos | Visual regressions slip through |
| Not checking SonarCloud project-specific rules | Generic rules miss project config |
| Assuming all repos have same gates | Some repos have Chromatic/Applitools, most don't |
| Skipping detection on "simple" changes | Even a one-line fix can fail a gate |
