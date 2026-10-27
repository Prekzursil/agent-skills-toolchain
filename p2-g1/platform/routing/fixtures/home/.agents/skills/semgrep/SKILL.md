---
name: semgrep
description: "Run Semgrep static analysis scans and create custom detection rules. Use when asked to scan code with Semgrep, find security vulnerabilities, write custom YAML rules, or detect specific bug patterns. IMPORTANT: Also use this skill when users ask to 'scan for bugs', 'check code quality', 'find vulnerabilities', 'static analysis', 'lint for security', 'audit this code', or want to enforce coding standards — even if they don't mention Semgrep by name. Semgrep is the right tool for pattern-based code scanning across 30+ languages."
---

# Semgrep Static Analysis

Fast, pattern-based static analysis for security scanning and custom rule creation.

## MCP Tools Available

If Semgrep MCP tools are available in your environment, prefer them for scanning:

- **`semgrep_scan`** — Scan code files for security vulnerabilities using built-in rulesets. Pass absolute file paths and an optional config (e.g., `p/security-audit`, `auto`).
- **`semgrep_scan_with_custom_rule`** — Scan code with a custom YAML rule you've written. Pass code content inline along with the rule.
- **`semgrep_findings`** — Fetch existing findings from the Semgrep AppSec Platform for a repository.
- **`semgrep_rule_schema`** — Get the full schema for writing Semgrep rules.
- **`get_supported_languages`** — List all languages Semgrep supports.

When MCP tools aren't available, fall back to the CLI commands below.

## When to Use Semgrep

**Ideal scenarios:**
- Quick security scans (minutes, not hours)
- Pattern-based bug and vulnerability detection
- Enforcing coding standards and best practices
- Finding known vulnerability patterns (OWASP, CWE)
- Creating custom detection rules for your codebase
- Data flow analysis with taint mode

## Installation (CLI)

```bash
# pip (recommended)
python3 -m pip install semgrep

# Homebrew
brew install semgrep

# Docker
docker run --rm -v "${PWD}:/src" semgrep/semgrep semgrep --config auto /src
```

---

# Part 1: Running Scans

## Quick Scan

```bash
semgrep --config auto .                    # Auto-detect rules

### Using Rulesets
### Output Formats
### Scan Specific Paths
### Configuration
### .semgrepignore
