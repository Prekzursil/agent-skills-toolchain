---
paths:
  - "**/*.__never_load__"
---
# Rules
## Structure

Rules are organized into a **common** layer plus **language-specific** directories:

```
rules/
├── common/          # Language-agnostic principles (always install)
│   ├── coding-style.md
│   ├── git-workflow.md
│   ├── testing.md
│   ├── performance.md
│   ├── patterns.md
│   ├── hooks.md
│   ├── agents.md
│   └── security.md
├── typescript/      # TypeScript/JavaScript specific
├── python/          # Python specific
├── golang/          # Go specific
├── swift/           # Swift specific
└── php/             # PHP specific
```

- **common/** contains universal principles — no language-specific code examples.
- **Language directories** extend the common rules with framework-specific patterns, tools, and code examples. Each file references its common counterpart.

## Installation

### Option 1: Install Script (Recommended)

```bash
# Install common + one or more language-specific rule sets
./install.sh typescript
./install.sh python
./install.sh golang
./install.sh swift
./install.sh php

# Install multiple languages at once
./install.sh typescript python
```

### Option 2: Manual Installation

> **Important:** Copy entire directories — do NOT flatten with `/*`.
> Common and language-specific directories contain files with the same names.
> Flattening them into one directory causes language-specific files to overwrite
> common rules, and breaks the relative `../common/` references used by
> language-specific files.

```bash
# Install common rules (required for all projects)
cp -r rules/common ~/.claude/rules/common

# Install language-specific rules based on your project's tech stack
cp -r rules/typescript ~/.claude/rules/typescript
cp -r rules/python ~/.claude/rules/python
cp -r rules/golang ~/.claude/rules/golang
cp -r rules/swift ~/.claude/rules/swift
cp -r rules/php ~/.claude/rules/php

# Attention ! ! ! Configure according to your actual project requirements; the configuration here is for reference only.
```

### Codex CLI

Both install routes above target `~/.claude/rules/` only, which **Codex CLI never
reads** — it discovers its own instruction files under `$CODEX_HOME` (default
`~/.codex`). So a rule that calls itself cross-tool (for example
[`common/windows-shell.md`](common/windows-shell.md)) is NOT in Codex's instruction
chain until you add a pointer yourself:

```bash
# Point Codex at the installed rules (Codex does not read ~/.claude/rules).
cp -r rules/common "${CODEX_HOME:-$HOME/.codex}/rules/common"
# ...then reference them from $CODEX_HOME/AGENTS.md, e.g.
#   Read ~/.codex/rules/common/windows-shell.md before any shell op.
```

> **Re-apply this after every Codex bootstrap.** `cli.mjs install` / `cli.mjs update`
> **replaces `$CODEX_HOME/AGENTS.md` wholesale** with the generated PromptBridge
> contract — `writeManagedFile(files.agentsPath, rendered.agents)` at
> `tools/mcp/codex-orchestrator/integrations/codex/bootstrap.mjs:704`, whose rendered
> body (`:326`) contains no rules pointer. It backs the old file up first, but the
> pointer is gone from the live file until you put it back. Note the asymmetry:
> `config.toml` next to it IS merged via a managed block (`:667-668`); only
> `AGENTS.md` is clobbered.
>
> UNVERIFIED: whether a sibling `AGENTS.override.md` would survive that overwrite and
> still be discovered — it is not written by `applyBootstrapToHome`
> (`bootstrap.mjs:649-655`), so it plausibly would, but nothing in this repo
> documents Codex's discovery order. Settle it by running `cli.mjs install` against a
> throwaway `CODEX_HOME` containing both files and checking which survives and which
> Codex actually loads. Until then, treat `$CODEX_HOME/AGENTS.md` as the only route
> and re-apply after each bootstrap.

Note `agent-self/config/codex/config.toml` is **not** an install source for this — it
is an inbound, redacted snapshot of the live config written *into* the repo by
`scripts/build-codespace-mirror.py:187-198`, and nothing deploys it back out
(`agent-self/bootstrap.ps1:28` copies `config/*` to `~/.claude` only). Editing it
changes no Codex behaviour and is overwritten on the next mirror run.

## Rules vs Skills

- **Rules** define standards, conventions, and checklists that apply broadly (e.g., "test coverage meets `.coverage-thresholds.json`", "no hardcoded secrets").
- **Skills** (`skills/` directory) provide deep, actionable reference material for specific tasks (e.g., `python-patterns`, `golang-testing`).

Language-specific rule files reference relevant skills where appropriate. Rules tell you *what* to do; skills tell you *how* to do it.

## Adding a New Language

To add support for a new language (e.g., `rust/`):

1. Create a `rules/rust/` directory
2. Add files that extend the common rules:
   - `coding-style.md` — formatting tools, idioms, error handling patterns
   - `testing.md` — test framework, coverage tools, test organization
   - `patterns.md` — language-specific design patterns
   - `hooks.md` — PostToolUse hooks for formatters, linters, type checkers
   - `security.md` — secret management, security scanning tools
3. Each file should start with:
   ```
   > This file extends [common/xxx.md](../common/xxx.md) with <Language> specific content.
   ```
4. Reference existing skills if available, or create new ones under `skills/`.

## Rule Priority

When language-specific rules and common rules conflict, **language-specific rules take precedence** (specific overrides general). This follows the standard layered configuration pattern (similar to CSS specificity or `.gitignore` precedence).

- `rules/common/` defines universal defaults applicable to all projects.
- `rules/golang/`, `rules/python/`, `rules/swift/`, `rules/php/`, `rules/typescript/`, etc. override those defaults where language idioms differ.

### Example

`common/coding-style.md` recommends immutability as a default principle.
[`golang/coding-style.md`](golang/coding-style.md) overrides it for Go. That file carries
the note below verbatim — the `../common/` prefix is correct **from `rules/golang/`**, which
is why it is shown here as a snippet rather than as a link rendered from this README:

```
> **Language note**: this section overrides the "Immutability (CRITICAL)" rule in
> [common/coding-style.md](../common/coding-style.md) for Go.
```

An override is only real when the language-specific file actually states it. A README example
is not an override — `ci/tests/test_rules_integrity.py` fails if a language override named here
is missing from the file it names.

### Common rules with override notes

Rules in `rules/common/` that may be overridden by language-specific files are marked with:

> **Language note**: This rule may be overridden by language-specific rules for languages where this pattern is not idiomatic.

**This marker is the only precedence signal that actually loads.** This README is scoped to
`**/*.__never_load__` (see the frontmatter), so the "Rule Priority" section above is
documentation for humans and never enters a model's context. The common rule does load — for
every extension in its own `paths:` list — so the override must be recorded *in the common
rule*, next to the text it qualifies, or the conflict is unresolvable at the point of use.
