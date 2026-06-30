# CI auto-fix & auto-merge automation

Three tiers keep this repo at zero-red with the least possible cost/effort.
Each tier only acts on a **failure** or a **trusted Dependabot PR**, and nothing
ever force-merges a red PR.

## Tier 1 — Dependabot auto-merge (free, native)
`.github/workflows/dependabot-auto-merge.yml`

On a Dependabot PR it enables GitHub **auto-merge (squash)**. The merge only
completes once the required `quality` status checks pass, enforced by:
- the repo **"Allow auto-merge"** setting (enabled), and
- the **branch ruleset** on `main` that lists the 7 `quality` jobs as
  `required_status_checks` (admins bypass so direct owner pushes still work).

If any check is red the PR stays open — no force-merge.

## Tier 2 — GitHub Models autofix (free, in-Actions, PRIMARY auto-fix)
`.github/workflows/autofix-models.yml`

When `quality` fails on a **push to `main`**, this calls the free GitHub Models
inference API (model `openai/gpt-4o-mini`, built-in `GITHUB_TOKEN`, no secrets)
with the failing logs, asks for a unified diff, applies it if it is clean, and
opens a PR labelled **`autofix`**. It is **never auto-merged** — the normal
quality gate plus a human review it. It is bounded: only on a failed main run,
only opens a PR when the model's patch applies.

## Tier 3 — Copilot coding agent (student sub — JUDICIOUS escalation)
**Not wired to fire automatically** (premium Copilot requests are finite).

Escalate manually **only when the free Tier-2 Models autofix cannot resolve a
stuck failing check**:

1. Open (or reuse) an issue describing the failing check, link the red run, and
   paste the relevant failing log lines.
2. Assign the issue to **`@copilot`** (GitHub Copilot coding agent). It will open
   a PR with a proposed fix.
3. Review + let the `quality` gate verify it; merge only when green.

Use this sparingly — prefer a real local fix or the Tier-2 Models autofix first.
