# Pre-registered experiments for agent-skills-toolchain

Written 2026-09-24. Each entry states the claim, the exact measurement, and the prediction; a prediction that fails is a finding, not a failure. Results go in `docs/results/` next to this file, one JSON per run, and never overwrite a previous run.

**Provenance caveat.** This file and the first E5 result artifacts are committed together, so there is no immutable pre-run record for E5: the E5 rows under "Results so far" are retrospective — the Linux runs validate the instrument, not the prediction — and are not independently pre-registered. The pre-registration guarantee holds only for the experiments still unrun when this file was committed — E1–E4, E6–E10, and the Windows arm of E5 (marked "not yet run" below) — whose predictions here genuinely precede their results. To preserve that guarantee for future work, commit each new experiment's prediction before its result artifact.

## Instrument 0: the golden task suite (prerequisite for everything below)

Ten to twenty tasks the owner actually runs, each with a mechanical pass/fail check. The rows below are CANDIDATES proposed from the repo's own surfaces. The suite is invalid until the owner has confirmed or replaced every row: a task nobody runs measures nothing, and a check that needs a judge measures the judge. Rules: no LLM-judged graders in the suite; every check is a command, a regex, or a file comparison; every fixture and answer key is committed next to the case.

| id | Task (real, recurring) | Mechanical pass check | Fixture / key to commit |
|---|---|---|---|
| G01 | Fix an injected regression in tools/mcp-manager | `pytest --cov=. --cov-branch --cov-fail-under=100 -q` exit 0 | the injected diff |
| G02 | Resolve a DOI to an open-access PDF via scholarly-access-mcp | output file begins with `%PDF`; DOI string present in extracted text | the DOI |
| G03 | Triage 5 abstracts with biomedical-paper-triage | output JSON validates against the skill's schema AND the top-2 ids equal `G03.key.json` | 5 abstracts + key |
| G04 | APA references for 3 known papers | each reference matches its regex in `G04.expected.txt` | expected strings |
| G05 | Add a PreToolUse hook that blocks `git push --force`, with a test, wired in project settings | test passes; a scripted `git push --force` is blocked in a real `claude -p` session (exit code and marker) | none |
| G06 | Run the MCP health gate on the canonical registry | exit 0 and report row count equals registry server count | none |
| G07 | Locate `<function>` in `fixtures/G07.bin` with the game-RE skills | reported address equals `G07.key` (single line) | fixture binary + key |
| G08 | Render a 15-second vertical short from `fixtures/G08.mp4` | ffprobe: duration 15±0.5 s, 1080x1920, one subtitle stream | fixture clip |
| G09 | Fix a seeded lint failure and open a PR | `ruff check` exit 0 on the branch; PR exists with the expected title prefix | seeded diff |
| G10 | Fix a seeded skill-description ratchet violation | `ci/check_skill_description_ratchet.py` exit 0 | seeded diff |
| G11 | Answer "what command runs the Python lint gate here?" | reply contains the exact string `ruff check .` and the pinned version string from AGENTS.md | none |
| G12 | Recover a deliberately broken MCP server entry | `claude mcp get <name>` output contains `Connected` | the broken config |

Each case runs 3 times per arm (the `claude plugin eval` default), pinned model, `--max-cost-usd` set. Suite score = mean with-plugin score; Δ = with minus without. Results are small JSON files under `docs/results/` on the one existing branch; no new branch, no new folder tree.

## Instrument 0b: main is green

Nothing below is interpretable while main's own quality workflow is red. Baseline taken 2026-09-24: red since 2026-09-19 (ruff: 11 errors, all under cyberstrike/; osv-scanner; gitleaks full-history). Precondition for E1: three consecutive green runs on main, and branch protection that blocks merging on red.

## Experiments and predictions

E1. Does the plugin help at all?
- Measurement: `claude plugin eval` two-arm (with-plugin vs no-plugin) over the golden suite.
- Prediction: mean Δ is within ±5 points. If Δ is strongly positive (>10), the "sprawl is the problem" thesis is weakened and the pruning plan should be reconsidered.

E2. Always-on rules.
- Measurement: E1 repeated with the 8 unscoped rule files removed (moved to path-scoped or deleted), `/context` recorded at session start in both conditions.
- Prediction: startup context drops by at least 15K tokens; suite score changes by less than 5 points. If the score drops by more than 5, the rules carry real signal and the cut must be selective, one failure per instruction (ETH recommendation).

E3. Skill exposure.
- Measurement: E1 repeated with only a curated core of 30 to 40 skills model-invocable (the rest `disable-model-invocation: true`); graders record which skill fired (`tool_used: Skill`) per case.
- Prediction: correct-skill-fired rate rises by at least 10 points and suite score does not fall. If the score falls, the core set is wrong, not the hypothesis; iterate on membership before rejecting.

E4. Skill usage over time.
- Measurement: 30 days of `claude_code.skill_activated` OTEL events (with invocation_trigger) exported to a file; `/skill-doctor` monthly.
- Prediction: at least 60 percent of currently exposed skills fire zero times in 30 days (the tool-registry-governance branch found 31 of 36 claude-only skills "reached nothing"; practitioner reports find 65 of 195 ever invoked).

E5. Hooks actually fire, per platform, per tool.
- Measurement: a smoke harness that starts a real session (`claude -p` with `--allowedTools` scoped; the Codex and cursor-agent equivalents) on the Windows box, triggers the hook events a single non-interactive turn can produce (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop), and asserts each hook's side effect (a marker file written by the hook). Wired event types a scripted echo turn cannot deterministically produce -- PreCompact, PostToolUseFailure, SessionEnd, Notification, Subagent*, PermissionRequest, WorktreeCreate -- are reported UNTESTED (`events_not_covered`), not asserted passing; closing that gap needs sessions that provoke each one.
- Prediction: at least one of the 41 wired hooks does not fire in at least one tool on Windows (the 2026 bug reports on Cursor's PowerShell-versus-bash execution and Codex's hook trust hashing make this likely). Any hook that fails the smoke test is either fixed or removed within the week, with a decision record.

E6. Duplicates are free to remove.
- Measurement: E1 repeated after step 2 of the sequence in section 9.5 (dead references, duplicate trees, one owner per capability), nothing else changed.
- Prediction: suite score unchanged (±3). If it drops, a "duplicate" was live; the diff identifies which.

E7. MCP surface.
- Measurement: E1 repeated with at most 10 servers active per project and the rest deferred; `/context` at start.
- Prediction: startup context drops by at least 20K tokens; tool-selection errors (graded by `tool_used`) drop; suite score does not fall.

E8. Model-release rot.
- Measurement: on the next Claude or Codex model release, E1 with and without all always-on files, before any config change.
- Prediction: the no-config arm is within 5 points of the with-config arm, or better, on the new model (Anthropic's own prompt cuts and the "scaffolding rots" reports).

E9. Decision permanence.
- Measurement: count of decisions in the decision-record directory with a review-by date; CI check that fails on expired decisions; count of "REFUTED"/"retire"/"reunite" commits per month after adoption.
- Prediction: within 60 days, reconcile/retire/refute commits fall by at least half relative to July to September 2026 (48 reconcile, 23 retire, 17 refute across about 870 commits), because decisions stop being re-litigated ad hoc.

E10. Lane convergence.
- Measurement: number of unmerged branches with no PR and no archive tag, sampled weekly; number of parallel lineages of the same lane.
- Prediction: after the policy "PR or archive tag within 48 hours; one lineage per lane" plus the retirement of the P2 stack, the count falls from 149 to under 20 within 30 days and stays there. If it climbs back, the policy has no mechanism and needs a CI gate (a workflow that fails on stale unmerged refs).

E11. PostToolUse output visibility (proposed by blind agent B).
- Measurement: a PostToolUse hook that prints a marker string and exits 0; one Read tool call; inspect the transcript and `claude --debug`. Then the JSON `additionalContext` variant, and the exit-2 variant.
- Prediction: the plain-text variant appears only in the debug log and never in the model's context; the JSON and exit-2 variants do. Consequence: every hook in the estate that "informs" via plain stdout has been informing nobody.

E12. Dead check in the fail-open dispatcher (proposed by blind agent B).
- Measurement: insert `raise RuntimeError` (then `time.sleep(60)`) at the top of one manifest-listed check in hooks/_dispatch, deploy, run one session.
- Prediction: exit 0, no transcript signal, at most a stderr attestation in debug output; the event ledger shows the event as handled. A dead check is indistinguishable from a passing one.

E13. Live versus repo hook tree (proposed by blind agent B).
- Measurement: `diff -r ~/.claude/hooks <repo>/hooks` (excluding _fleet-backups) plus a JSON diff of the hooks arrays in ~/.claude/settings.json and hooks/hooks.json.
- Prediction: at least one live-only directory or script absent from git; at least ten hook commands present in one manifest and not the other.

E14. Review is a formality (proposed by blind agent A).
- Measurement: for the 291 merged PRs, median minutes from creation to merge and share with at least one non-author review.
- Prediction: median under 30 minutes; well under 10 percent with a non-author review.

E15. Platform behaviour versus configuration (proposed by blind agent B).
- Measurement: freeze hooks, skills and CLAUDE.md; replay a fixed 20-prompt set monthly across Claude Code releases (and once on a pinned older version), logging compliance and skill activation.
- Prediction: compliance or activation varies by at least 15 points across versions with byte-identical configuration.

E16. Retired components still run (proposed by blind agent B, from PR #311's measurement).
- Measurement: PowerShell process table: any `bridge-server` or `agentbridge` process; count of parentless `cursor-agent` or `node` trees; available RAM.
- Prediction: at least one AgentBridge process present despite retirement; at least three parentless agent trees; available RAM under 15 percent of 31.6 GB.

## Results so far (appended, never edited)

- 2026-09-24T02:24Z, E5 mechanism, Linux, Claude Code 2.1.281, `hooksmoke.py --tool claude`: 5 of 5 event hooks fired (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop) in one real `claude -p` session, 5.7 s, each hook received stdin JSON (353 to 729 bytes). Prediction E5 concerns the Windows arm and is NOT tested by this run; this run establishes that the instrument itself works and that the failure class, when it appears on Windows, is platform- or tool-specific rather than a property of the hook shape. File: docs/results/E5-claude-linux-20260924T022422Z.json.
- 2026-09-24T02:24Z, E5 live dry-run, Linux, against the tracked snapshot agent-self/config/settings.json: 0 of 41 hook commands can start off the Windows box (every command embeds `C:/Users/Prekzursil/...`). Consequence: the tracked configuration cannot be exercised in a real session by any Linux CI, so the repo's CI could never have detected a hook that stopped firing. File: docs/results/E5-live-linux-20260924T022422Z.json.
- Windows arm of E5 (the prediction that matters): not yet run; requires the owner's workstation. Command (from the repo root): `python scripts/hooksmoke.py --tool claude` then `python scripts/hooksmoke.py --live "$env:USERPROFILE\.claude\settings.json"`, then the same throwaway project under cursor-agent and Codex.

## Rules of the game

- Predictions are written before the run; after the run, the result file records pass/fail against the prediction and nothing is edited retroactively.
- One variable per experiment; the golden suite is the constant.
- Any change to the suite is a new suite version; scores across versions are not compared.
- A model's opinion of these results is not a result.
