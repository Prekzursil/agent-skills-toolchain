# Harness Audit Command

Run a deterministic repository harness audit and return a prioritized scorecard.

## Usage

`/harness-audit [scope] [--format text|json]`

- `scope` (optional): `repo` (default), `hooks`, `skills`, `commands`, `agents`
- `--format`: output style (`text` default, `json` for automation)

## Deterministic Engine

Always run:

```bash
node scripts/harness-audit.js <scope> --format <text|json>
```

This script is the source of truth for scoring and checks. Do not invent additional dimensions or ad-hoc points.

Rubric version: `2026-05-19`.

The script computes 12 fixed categories (`0-10` normalized each):

1. Tool Coverage
2. Context Efficiency
3. Quality Gates
4. Memory Persistence
5. Eval Coverage
6. Security Guardrails
7. Cost Efficiency
8. GitHub Integration
9. Vercel Integration
10. Netlify Integration
11. Cloudflare Integration
12. Fly Integration

Scores are derived from explicit file/rule checks and are reproducible for the same commit.
