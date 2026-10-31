---
title: DEAD-COMMAND-PROMISES
type: note
permalink: dqverify-repo-20261013/docs/dead-command-promises
---

# Dead command promises — implement-or-retire register

A **published command** here is a `commands/*.md` the Claude Code client loads as a slash
command. A row below means: the command is still published, its documented entry point
resolves in no root that was searched, and the fix is a decision this register does not make.

**This file is enforced, not decorative.** `ci/tests/test_command_doc_promises.py` requires a
row for every token it classifies `DEAD` in `KNOWN_UNRESOLVED_INVOCATIONS`, requires each row
to name an owner and a settling action, and **fails when a row goes stale** — if the script
lands, the row must be deleted or the gate goes red. That last property is the point: a debt
list that can only grow is a mute button, and a register read as current after the debt is
paid is exactly the stale-doc defect this lane exists to catch. Same construction, and the
same reasoning, as `command-center/slop-report/published-commands-baseline.json`.

The gate runs on every push to `main` via `.github/workflows/quality.yml:1503`.

## Register

| token | published by | measured | owner | settling action |
|---|---|---|---|---|
| `scripts/claw.js` | `commands/claw.md:12` (`node scripts/claw.js`) and `:18` (`npm run claw`); mirrored at `agent-self/config/commands/claw.md`; repeated by `skills/nanoclaw-repl/SKILL.md:9`, `skills/source-command-claw/SKILL.md:19` and `skills/autonomous-loops/SKILL.md:130,133` | `git ls-files` basename search → 0 tracked; recursive search of `~/.claude`, `~/.agents`, `~/.codex` → 0 live; root `package.json` declares scripts `test` and `validate:skills` only, so `npm run claw` fails too (round 8, `docs/_lane_docs_r8_dead_invocations.py`) | owner — NanoClaw v2 is an unbuilt capability, not a docs defect | **Implement** `scripts/claw.js` (and an `npm run claw` entry), **or retire** `/claw` together with the three skills that repeat it. Then delete this row and the `DEAD` entry. |
| `scripts/harness-audit.js` | `commands/harness-audit.md:17` (`node scripts/harness-audit.js <scope> --format <text\|json>`), which then calls that script *"the source of truth for scoring and checks"*; mirrored at `agent-self/config/commands/harness-audit.md` | same two signals → 0 tracked, 0 live. **Independently recorded on 2026-07-13**, a month before round 8 rediscovered it: `docs/audit-design-2026-07-13/A5-doc-registry.json:535` (`document_id: gate/harness-audit-cmd`, `status: broken-canonical`), `A5-decision-ledger.json:49` (`D-015`, `implementation_status: BROKEN-PACKAGING`), and `docs/phase3-discovery-2026-07-13/reconcile-codex-findings.md:34` | owner — and see the note below, because a prior record already exists and did not move it | **Retire** is the better-evidenced half here: the 2026-07-13 ledger row already marks the claim `current_validity: invalid` and notes its advice conflicts with the Basic-Memory authority model. **Implement** only if that conflict is resolved first. Then delete this row and the `DEAD` entry. |

## Why a register at all, and what it does not claim

Round 8 measured both tokens and resolved them `ROUTE, not fix-doc` — weakening the doc would
make the document true and the estate no more capable. That verdict stands. What was missing is
that **route had no destination**: `DEAD` in the test file is an allowlist whose only effect is
to keep the ratchet green, and a debt nothing surfaces is indistinguishable from a debt nobody
found.

The `harness-audit` row is the evidence for that, and it is uncomfortable. The defect was
already written down on **2026-07-13** with a status, an owner field and a validity verdict —
in three separate files — and a month later the command is still published and still dead.
Nothing reads `A5-doc-registry.json`; no gate asserts anything about `status: broken-canonical`.
So the lesson is not *record it*; the estate had recorded it. The lesson is that **a register
no instrument reads routes nothing**, which is why this one is bound to a test that fails.

Measured limits of this file, stated rather than implied:

- It **does not pay the debt.** Both commands remain broken for anyone who types them today.
- Its scope is `scripts/…` invocations inside `commands/*.md`, the corpus the round-8 ratchet
  reads. A dead promise phrased another way is out of scope here.
- The repo's other dangling-command gate,
  `command-center/slop-report/check_published_commands.py`, cannot see either token: its
  matcher is `python <path>.py` only, verified two-state (it fires on a python invocation and
  returns 0 hits on a `node` one). Widening it to `node` was measured and **not done**: the
  same corpus publishes 22 node invocations of which **13** resolve to nothing, most in other
  lanes' trees (`dist/index.js`, `ovh-mcp/dist/index.js`, `scripts/postinstall.js`, …). That is
  a 13-row cross-lane change, not this lane's to make — recorded here with the number so the
  next reader does not have to re-derive it. Probe: `docs/_lane_docs_i2_register_census.py`.

  > **This file first published that number as 16. REFUTED by my own second signal, and kept
  > here rather than quietly edited.** The first resolver tried only the citing document's
  > immediate parent directory, so a skill pack or vendored plugin that ships its own tree —
  > `skills/ui-audit/…` naming `uicrit-pack/_test_pack.mjs`, `tools/editor/metaswarm/…` naming
  > `lib/sync-resources.js` — was reported as a dead promise it is not. That is the
  > root-anchoring error round 8 had **already documented** as R8-7, reproduced in the probe
  > written to check round 8. Caught by corroborating each token with a basename search, which
  > disagreed on 5 of 16; three were genuine false positives and two (`dist/index.js`,
  > `ovh-mcp/dist/index.js`) were noise from a generic basename where the resolver was right.
  > The resolver now walks every ancestor root, and a control asserts that walk is not inert.
  > The recommendation is unchanged: 13 rows is still a cross-lane change.