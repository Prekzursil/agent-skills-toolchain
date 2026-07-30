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

The CLI JSON is authoritative for the *score*. Retain `recommended_tier` and
`model_id` verbatim in the handoff for auditability. Do not recreate the old prose
heuristic. Then apply the policy floor below before choosing the subagent `model`.

## Policy Floor — the router may not under-route substantive work

`rules/common/performance.md:23-35` is the governing owner policy and it is
unconditional: **every substantive subagent — coding, review, research,
orchestration — defaults to Opus**, and Haiku is explicitly "NOT for coding, review,
or any task where output quality matters". That rule states it "overrides any generic
cost-routing advice", which includes this router.

The router scores *code health*, not *task substance*, so it will return a cheaper
tier for a substantive unit. Measured at this commit with `lizard` present:

| `--files` | `recommended_tier` |
| --- | --- |
| `tools/triage-router/triage_router.py` | `sonnet` |
| `ci/emit_hook_manifest.py` | `haiku` |
| `hooks/_shared/hookrun.py` | `haiku` |

So the effective tier is **`max(recommended_tier, opus)` whenever the work unit is
substantive**, and the handoff must say the floor was applied. A tier below Opus may
be used ONLY for a trivial, mechanical, high-frequency step — throwaway lookup,
format/lint pass, log triage. `--budget` never lowers the floor (see Usage above).

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
