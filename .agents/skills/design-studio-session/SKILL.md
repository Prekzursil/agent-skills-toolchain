---
name: design-studio-session
description: The interactive-modify capability behind `design-studio session` mode. Use when the owner wants to point at a LIVE element in a running app (Reframe, momentstudio, WebCoder, bilbo) and iteratively restyle it with Claude and Codex — preview candidates as injected style overlays FIRST, resolve the clicked element back to its source file:line, apply ONE scoped micro-commit, incrementally re-audit only the changed screen, and auto-decide KEEP or REVERT through the SAME revert-gate as the batch design-review loop. Do NOT use for a whole-app batch audit (use design-studio / ui-audit) or for driving the app without modifying it (use ui-drive).
---

# design-studio session — interactive-modify (gem N.2)

The **interactive twin** of the batch `design-studio`. Where the batch loop audits a
whole flow G0→G7, `session` runs ONE tight modify cycle per element, with the owner in the
loop and Claude + Codex as rival suggesters. It is deliberately a **consolidation, not a new
runtime**: it reuses the **same revert-gate**, the **same ui-audit summary shape**, and the
**same `loop-state.json` scope** as the batch loop, so it kills the overlap instead of
re-creating it (UIUX N.2 §89).

> Routed to by the `design-studio` meta-skill's `session` mode. Standalone entry:
> `node session.mjs <subcommand>`. No new deps, no new runtime.

## The cycle (UIUX N.2 §2.2)

```
DRIVE (ui-drive) → AUDIT baseline (ui-audit, cached)
  → PICK      owner clicks a live element → element→source picker resolves {selector, file:line, rect, computedStyle}
  → SUGGEST   Claude + Codex register N candidates, each a LIVE injected-style overlay FIRST (by:claude|codex)
  → OVERLAY   preview every candidate BEFORE any source edit (reload = gone → reversible by construction)
  → SELECT    Artifact side-by-side gallery + one AskUserQuestion → owner picks (or "keep as-is")
  → APPLY     ONE scoped micro-commit on a design/live-<id> branch — the picked file ONLY
  → REAUDIT   incremental: changed screen only → delta from the ui-audit summary
  → REVERT-GATE  shared revertDecision(): KEEP or REVERT → loop
  → batch Figma-mirror every K accepts (hand off to design-studio mirror)
```

**Why overlay-first:** each candidate is an injected `style` tag (`data-candidate`) on the
running app **before any source edit** — instant (<1s vs edit+HMR) and reversible-by-reload, so
the revert-gate only ever arbitrates changes the owner already **accepted** (UIUX N.2 §91).

**Why element→source, not vision:** the picker rebuilds the react-dev-inspector /
code-inspector-plugin pattern thin on `evaluate_script` — a click resolves the React fiber's
`_debugSource` (or `data-insp-path` attrs) to a real `file:line`. Deterministic; beats VLM
Set-of-Mark guessing (the Cursor-2.0 / stagewise pattern; UIUX N.2 §90).

**Why external audit at all:** LLMs cannot reliably self-correct without external feedback
(ICLR-2024) — the incremental re-audit is what makes model-suggested edits trustworthy.

## Dual-agent mingle (UIUX N.2 §92)

| Role | Agent | Contract |
|---|---|---|
| **driver / applier** | **Claude** | holds the `mcp_agent_mail` file-lease on the picked source; the ONLY writer of the apply-back micro-commit |
| **rival-suggester + independent re-auditor** | **Codex** | posts candidates (`by:codex`) and its own KEEP/REVERT verdict; **never edits the leased file** |

Candidate pools merge **attributed**; agreement across vendors is the signal (independent
failures); disagreement **escalates to the owner** — never auto-resolves to consensus. Emit the
lease/role card with `node session.mjs mingle`.

## Subcommands

| cmd | does |
|---|---|
| `start --app <n> --flow </path> --url <url> [--repo <path>]` | open a session; **inherits scope from `loop-state.json`** if present; records the `design/live-<id>` branch |
| `pick --selector <sel> --file <path:line>` | record the picked element→source target. `pick --emit-script` prints the browser picker JS for `evaluate_script` |
| `suggest --cid <id> --selector <sel> --css "<decls>" --by <claude\|codex> [--dims "contrast:+1"]` | register a candidate + print its overlay markup |
| `overlay --cid <id>` | print the injectable style tag + the `evaluate_script` inject snippet (preview) |
| `gallery` | write `gallery.json` (before + N candidates + predicted deltas) for an Artifact + one AskUserQuestion |
| `select --cid <id\|keep>` | owner's choice (`keep` = no change; the cycle still closes clean) |
| `apply [--commit --repo <path>]` | scoped micro-commit. **Default = SHADOW plan** (prints the exact scoped `git add <file>` — never `git add -A`); `--commit` executes a single-file commit |
| `reaudit --before <audit.json> --after <audit.json>` | incremental delta from the ui-audit `summary` → `delta.json` |
| `revert [--enforce --repo <path>]` | the **shared** G6 revert-gate over the delta. **SHADOW by default**: logs the decision + emits the scoped rollback command, never mutates the repo |
| `mingle` / `status` | print the mingle card / the session ledger |

## Safety / SHADOW (council C5)

- The **revert-gate is SHADOW by default** — it decides + logs + emits the recommended scoped
  rollback but **never mutates the repo**. Enforcement is opt-in (`revert --enforce`) and only
  ever runs a scoped `git revert --no-edit <sha>` on the candidate commit.
- `apply` is scoped to the **picked file only** (execFile array args, no shell) — it can never
  `git add -A`. Every apply-back is one reversible commit; the revert-gate arbitrates it.
- Overlay previews touch only the DOM of the running app (a `data-candidate` style tag) — they
  never write to disk and vanish on reload.

## Consolidation ledger (what it reuses, not rebuilds)

- **revert-gate:** dynamically imports `revertDecision()` from the sibling
  `design-studio` `gates.mjs`; a byte-identical `inlineRevert`
  fallback keeps it standalone. Same KEEP/REVERT law as the batch loop.
- **audit summary:** `scoreSummary()` reads ui-audit's `run_audit.mjs` `aggregate().summary`
  (pageErrors, clickErrors, deadControls, axe, spacing, affordance, motion) — no new metric.
- **state:** `session-state.json` carries `loopStateRef` and inherits `app/flow/sourceOfTruth`
  from `loop-state.json`; the session is the interactive specialization of the batch G5↔G6.

Evidence: MASTER §N.2 · UIUX-CONSOLIDATION-DECISION-QUEUE §2.2, §89–95, N.2, K.5.
