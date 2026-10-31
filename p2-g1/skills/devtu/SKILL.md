---
name: devtu
description: "ToolUniverse (mims-harvard/ToolUniverse) development toolkit - one skill, eight sub-command modes. Use when working on ToolUniverse tools: create a new scientific/API tool, fix a failing tool, optimize tool JSON descriptions, optimize research skills, auto-discover life-science APIs and generate integration PRs, run the debug-test loop, or push and fix CI. Each mode's playbook is under modes/."
---

# DevTU — ToolUniverse Development Toolkit

One consolidated skill for the entire ToolUniverse (`mims-harvard/ToolUniverse`) development
lifecycle. Read the **mode** from the user's intent and open that mode's playbook under
`modes/<mode>/README.md` (progressive disclosure — the full former per-skill content, references,
and templates are preserved there unchanged).

## Sub-command modes

| Mode | Use when | Playbook |
|------|----------|----------|
| **self-evolve** | "run the self-improvement loop", "do a debug/test round", evolve ToolUniverse end-to-end (orchestrates the other modes) | [modes/self-evolve/README.md](modes/self-evolve/README.md) |
| **auto-discover-apis** | expand coverage — gap analysis, web-search for life-science APIs, batch discover + create + validate + PR | [modes/auto-discover-apis/README.md](modes/auto-discover-apis/README.md) |
| **create-tool** | add a new tool: Python tool class + JSON config + registration + real test examples | [modes/create-tool/README.md](modes/create-tool/README.md) |
| **fix-tool** | a tool fails tests / returns errors / has schema-validation issues — diagnose root cause, fix, validate | [modes/fix-tool/README.md](modes/fix-tool/README.md) |
| **code-optimization** | writing/refactoring tool Python: reusable code patterns, per-API bug fixes, schema/pre-commit checklist | [modes/code-optimization/README.md](modes/code-optimization/README.md) |
| **optimize-descriptions** | make tool JSON descriptions clear (prerequisites, abbreviations, required-vs-optional params, usage) | [modes/optimize-descriptions/README.md](modes/optimize-descriptions/README.md) |
| **optimize-skills** | improve research-skill quality: tool verification, evidence grading (T1-T4), completeness, synthesis | [modes/optimize-skills/README.md](modes/optimize-skills/README.md) |
| **github** | push code safely, activate pre-commit hooks, clean staged files, fix CI | [modes/github/README.md](modes/github/README.md) |

## The cycle (self-evolve orchestration)

```
Discover → Create → Test → Fix → Optimize → Ship → Repeat
```

- **Discover** → `auto-discover-apis` — gap analysis + API search + scoring
- **Create** → `create-tool` — tool class + JSON config + test examples
- **Test** → `self-evolve` — launch researcher-persona agents to find issues (verify EVERY report via CLI first — 50%+ are false positives)
- **Fix** → `fix-tool` (code-level patterns in `code-optimization`)
- **Optimize** → `optimize-descriptions` + `optimize-skills`
- **Ship** → `github`

## Shared rules (all modes) — CRITICAL

- **Verify before fixing:** `python3 -m tooluniverse.cli run <ToolName> '<json_args>'` — many agent-reported bugs are MCP-interface false positives.
- **Tool contract:** `return_schema` MUST have `oneOf` (success + error); `test_examples` MUST use real IDs (no TEST/DUMMY/PLACEHOLDER); tool name at most 55 chars; NEVER raise in `run()` (return an error dict); set a 30s timeout on all HTTP.
- **Registration (most-missed):** class `@register_tool` + entry in `default_config.py` + wrapper generation on `tu.load_tools()`.
- **Code hygiene:** always run `Skill(skill="simplify")` after writing or modifying code; `ruff check` before commit.
- **Git:** never push to `main`; never keep multiple open fix PRs; always `git fetch origin && git rebase origin/main` before push; commit messages use "Feature"/"Fix" (never "Bug"); no AI attribution; repo is `mims-harvard/ToolUniverse` (confirm with `git remote -v`).

> Consolidation note: this skill supersedes the former eight `devtu-*` micro-skills
> (`devtu-auto-discover-apis`, `devtu-code-optimization`, `devtu-create-tool`, `devtu-fix-tool`,
> `devtu-github`, `devtu-optimize-descriptions`, `devtu-optimize-skills`, `devtu-self-evolve`).
> Their complete bodies, reference files, and templates are preserved verbatim under
> `modes/<mode>/`. Any older `Skill(skill="devtu-<mode>")` invocation is now this skill in that mode.
