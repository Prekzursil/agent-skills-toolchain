# Model Route Command

Route a file-backed implementation work unit through the checked-in model policy.

## Usage

`/model-route [task-description] [--budget low|med|high]`

The task description must identify one or more existing target files. `--budget` is
reporting context only: it never weakens the minimum tier selected by policy.

## Required Execution

Resolve the target files to absolute paths. Then, from the
`agent-skills-toolchain` checkout root, run:

~~~bash
python tools/triage-router/triage_router.py --files <file> [<file> ...] --pretty
~~~

Outside that checkout, resolve the canonical source without changing the target
project's working directory:

~~~bash
TOOLCHAIN_ROOT="${AGENT_SKILLS_TOOLCHAIN_ROOT:-$HOME/source/agent-skills-toolchain}"
python "$TOOLCHAIN_ROOT/tools/triage-router/triage_router.py" --files <absolute-file> [<absolute-file> ...] --pretty
~~~

For a retry after validation fails, run the same command with the tier that just
failed:

~~~bash
python tools/triage-router/triage_router.py --files <file> [<file> ...] --escalate <current-tier> --pretty
~~~

The CLI JSON is authoritative. Use `recommended_tier` (`haiku`, `sonnet`, or
`opus`) as the Claude subagent `model` selector and retain `model_id` in the
handoff for auditability. Do not recreate the old prose heuristic.

If no target file can be resolved, the checkout or router is unavailable, the
command exits nonzero, or the JSON lacks either required field, fail up to
`recommended_tier: opus` and `model_id: claude-opus-4-8`.

## Required Output

- `recommended_tier`
- `model_id`
- confidence level
- router rationale and signal source
- whether this was an initial route, escalation, or fail-safe

## Arguments

$ARGUMENTS:
- `[task-description]` optional free-text
- `--budget low|med|high` optional
