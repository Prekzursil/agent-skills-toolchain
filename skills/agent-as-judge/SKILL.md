---
name: agent-as-judge
description: Advisory, evidence-citing Agent-as-a-Judge. Use when you want a second opinion on whether a completion meets its Definition of Done AFTER the deterministic verification cluster (typed receipts, fail-first red-proof, execution-consensus, golden-journey oracle) has run — it decomposes the DoD into falsifiable YES/NO items, cites a ledger-event or evidence-hash per item (chain-of-custody), execute-to-confirms every would-be-blocking finding, and scores against the ICD-203 nine analytic standards. Its opinion NEVER gates or grants "done" (COUNCIL C3): only a re-run executable receipt could ever block and that path is deferred indefinitely, so it is 100% ADVISORY and ships in SHADOW mode (observe + log, never blocks, never nags). Imports passk-stats (F5) for kappa/e-value calibration vs the owner's claude-reflect corrections; stays advisory while kappa < 0.6 and auto-demotes on decay. NOT a done-gate, NOT terminal authority; a same-vendor judge shares the fixer's blind spots so prefer a cross-vendor Codex second judge on contested calls. Do NOT use to BLOCK a merge/completion, and do NOT use it in place of the deterministic gates.
---

# Agent-as-a-Judge (advisory, evidence-citing)

A tool-using LLM judge that annotates the **subjective residue** of a Definition of Done — the
items the deterministic gates cannot decide ("is the artifact actually correct?", "does this
match intent?"). It is **advisory this wave**: its opinion never gates, and it ships in SHADOW
mode. The subagent contract lives in `agents/agent-as-judge.md`; this skill is the operator guide
plus the reference implementation the judge runs.

**Evidence:** MASTER-DECISION-QUEUE A5 (`gem-hunt-2026-07-12`); COUNCIL-VERDICT C3
(*"opinion never gates, only a cited executed receipt can block — deferred indefinitely"*).
Research: Agent-as-a-Judge (arXiv 2410.10934); ICD-203 Analytic Standards; EvalGen (2404.12272);
JudgeBench (LLM judges ~chance) — the empirical basis for the advisory-until-calibrated stance.

## Where it sits in the pipeline (read this first)

```
   deterministic cluster (carries ALL blocking weight, no calibration needed)
   ┌─────────────┬──────────────┬────────────────────┬─────────────────────┐
   │ A1 typed    │ A3 fail-first│ A4 execution-      │ C4 golden-journey   │
   │ receipts    │ red-proof    │ consensus          │ oracle (keystone)   │
   └─────────────┴──────────────┴────────────────────┴─────────────────────┘
                                   │  green?
                                   ▼
              ┌─────────────────────────────────────────────┐
              │  Agent-as-a-Judge  (THIS)  — runs AFTER      │
              │  ADVISORY · SHADOW · annotates SUBJECTIVE DoD │
              │  opinion NEVER blocks/grants · cites+executes │
              └─────────────────────────────────────────────┘
```

If the deterministic cluster has not run green, the judge says so and **lowers its confidence** —
it does not substitute its opinion for the missing deterministic signal.

## When to use

- After a work-unit's deterministic gates pass and you want an evidence-cited second read on the
  *subjective* DoD items before (not instead of) an owner sign-off.
- To accrue a **calibration record** — every advisory verdict is logged so `passk-stats` (F5) can
  later measure the judge's agreement (kappa) with the owner's own corrections.
- To decide whether a completion is contested/irreversible enough to warrant a **cross-vendor
  Codex second judge**.

## When NOT to use

- To **block** or **clear** a merge/completion — it structurally cannot (COUNCIL C3). Use the
  deterministic cluster for the done-signal.
- As the primary verifier — it is one correlated-failure-prone vote, never terminal authority.
- On purely deterministic criteria the gates already cover — the judge only owns the residue.

## The contract in one screen

| Rule | Consequence |
|------|-------------|
| Bare opinion never gates/grants "done" | Output is 100% advisory this wave |
| Only a cited, re-run EXECUTED receipt could ever block | That veto path is **deferred indefinitely** |
| Runs AFTER the deterministic cluster | It owns only the subjective residue |
| Veto layer, never grant layer | May add scrutiny; may never clear |
| Same-vendor = correlated failure | Prefer a cross-vendor Codex second judge |
| Calibrate kappa >= 0.6 vs claude-reflect corpus, per-category, lower CI bound | Even then: license to SPEAK, not BLOCK |
| Honest prior kappa < 0.6 | Stays advisory; program loses nothing |
| Auto-demote on kappa decay; never self-promote | A good judge can rot |
| Read-only on source; writes only the shadow sink | Never edits project code |

## Protocol (four steps)

1. **Extract a YES/NO DoD checklist** from `ACCEPTANCE.md` / issue / plan / `active-plan.md`;
   split compound criteria; tag each `deterministic` (a gate covered it) or `subjective` (judge
   owns it). Opine only on `subjective` items.
2. **Cite evidence per item** — `ledger#seq<N>` (a real event in
   `~/.claude/event-ledger/<slug>/events.jsonl`) OR `sha256:<hex12>` of the exact artifact bytes /
   command output (chain-of-custody). Un-citable item -> `UNBACKED` -> advisory-forever.
3. **Execute-to-confirm** every would-be-blocking finding: re-run the cited receipt; record
   `reproduced` / `not-reproduced` (-> downgrade to note) / `unrunnable` (-> UNBACKED).
4. **Score ICD-203's nine standards** (sourcing, uncertainty, fact-vs-assumption, alternatives,
   relevance, logic, consistency, likelihood, presentation) PASS/PARTIAL/FAIL each.

Then emit the terminal-state verdict (schema in `agents/agent-as-judge.md`) and append one shadow
line. **Zero findings block — that is by design.**

## Calibration harness (passk-stats / F5)

- **Label source:** owner's claude-reflect corrections `~/.claude/learnings-queue.json` +
  `--supersedes` chains in the ledger. This is a *caught-error* corpus — blind to *escaped*
  defects — so it can license the judge to SPEAK, never to BLOCK on opinion (C3 hard constraint).
- **Statistic:** Cohen's kappa (>= 0.6 substantial) + anytime-valid e-values / paired CI via
  `passk-stats`, over >= 30-50 labeled items, gated on the LOWER CI bound, per-DoD-category.
- **F5 not built yet?** `probe_passk_stats()` returns absent -> `CALIBRATION: UNAVAILABLE` ->
  advisory. Never fabricate kappa; a missing calibrator can never flip the judge toward gating.

## Shadow-mode logging (COUNCIL C5)

One JSON line per run to a **separate, bounded, auto-rotating** sink — never the main ledger:

- Default sink: `~/.claude/shadow-sinks/agent-as-judge.jsonl` (override `$AGENT_AS_JUDGE_SHADOW_SINK`).
- Rotates at ~2 MB to `<sink>.1`. Records verdict + would-have-fired findings + citations +
  calibration status so F1 (gem-fitness scorer) can measure precision against external truth.
- SHADOW = observe/log only. It NEVER blocks and NEVER nags. There is no ENFORCE promotion this
  wave; promotion is an owner decision gated on external calibration.

## Reference implementation

Stdlib-only, fail-open, Windows/POSIX-safe. The judge runs this via Bash — do not re-implement it
from memory. Save as needed or run inline. Modes: `--selftest` (runs against the live ledger +
label corpus and prints a demo verdict) and library use (`import` the functions).

```python
#!/usr/bin/env python
"""agent-as-judge helper — evidence citation, evidence hashing, label-corpus read,
passk-stats (F5) probe, and bounded rotating shadow-log. Stdlib only; fail-open.

CONTRACT: advisory-only. Nothing here blocks, gates, or grants 'done'. It records and cites.
"""
from __future__ import annotations
import hashlib, json, os, sys, time
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
LEDGER_MOD_DIR = HOME / ".claude" / "hooks" / "event-ledger"
LABEL_CORPUS = HOME / ".claude" / "learnings-queue.json"          # claude-reflect corrections
DEFAULT_SINK = HOME / ".claude" / "shadow-sinks" / "agent-as-judge.jsonl"
SINK = Path(os.environ.get("AGENT_AS_JUDGE_SHADOW_SINK", str(DEFAULT_SINK)))
SINK_ROTATE_BYTES = 2 * 1024 * 1024
KAPPA_BAR = 0.6                    # Landis-Koch "substantial"
MIN_LABELED = 30                   # C3: >= 30-50 labeled items before kappa is even meaningful


def _load_ledger():
    """Best-effort import of the real event-ledger module. Fail-open -> None."""
    try:
        if str(LEDGER_MOD_DIR) not in sys.path:
            sys.path.insert(0, str(LEDGER_MOD_DIR))
        import ledger  # noqa: PLC0415
        return ledger
    except Exception:
        return None


def cite_ledger(project_path: str, n: int = 40) -> list[dict]:
    """Return recent ledger events (oldest->newest) for citation as ledger#seq<N>."""
    led = _load_ledger()
    if led is None:
        return []
    try:
        return led.replay(project_path or os.getcwd(), n=n)
    except Exception:
        return []


def ledger_citation(ev: dict) -> str:
    """Format a real event as a chain-of-custody citation."""
    return f"ledger#seq{ev.get('seq')}({ev.get('kind')}@{ev.get('ts')})"


def hash_evidence(source, is_path: bool | None = None) -> str:
    """sha256:<hex12> of artifact BYTES (path) or command-output TEXT. Pins what you saw."""
    try:
        if is_path is None:
            is_path = isinstance(source, (str, Path)) and Path(str(source)).exists()
        if is_path:
            data = Path(str(source)).read_bytes()
        else:
            data = str(source).encode("utf-8", "replace")
        return "sha256:" + hashlib.sha256(data).hexdigest()[:12]
    except Exception:
        return "sha256:UNREADABLE"


def read_label_corpus() -> dict:
    """Read the owner's claude-reflect corrections queue = kappa ground-truth labels.
    Caught-error corpus (blind to escaped defects) -> licenses SPEAK, never BLOCK (C3)."""
    if not LABEL_CORPUS.exists():
        return {"present": False, "n": 0, "reason": "learnings-queue.json absent (no corrections captured yet)"}
    try:
        items = json.loads(LABEL_CORPUS.read_text(encoding="utf-8"))
        corrections = [it for it in items if isinstance(it, dict)
                       and (it.get("sentiment") == "correction" or it.get("type") in ("auto", "explicit", "guardrail"))]
        return {"present": True, "n": len(corrections), "total": len(items)}
    except Exception as e:
        return {"present": False, "n": 0, "reason": f"unreadable: {e!r}"}


def probe_passk_stats() -> dict:
    """Detect the F5 pass^k / e-value / kappa calibrator. Absent -> advisory, never fabricate."""
    # F5 may ship as a skill dir, a module, or an artifact. Probe the known shapes.
    candidates = [
        HOME / ".claude" / "skills" / "passk-stats" / "SKILL.md",
        HOME / ".claude" / "skills" / "pass-k-stats" / "SKILL.md",
        HOME / ".claude" / "hooks" / "passk_stats.py",
    ]
    for c in candidates:
        if c.exists():
            return {"present": True, "path": str(c)}
    try:
        import passk_stats  # noqa: F401,PLC0415
        return {"present": True, "path": "module:passk_stats"}
    except Exception:
        return {"present": False}


def calibration_status(labels: dict, passk: dict) -> str:
    """The honest, non-fabricating calibration verdict. Never returns a made-up kappa."""
    if not passk.get("present"):
        return "CALIBRATION: UNAVAILABLE (passk-stats/F5 not present) -> advisory"
    if not labels.get("present") or labels.get("n", 0) < MIN_LABELED:
        return (f"CALIBRATION: INSUFFICIENT LABELS (n={labels.get('n', 0)} < {MIN_LABELED}) "
                f"-> advisory (honest prior kappa < {KAPPA_BAR})")
    # F5 present AND enough labels: hand off to passk-stats to compute per-category kappa + e-value.
    # This helper does NOT compute kappa itself (that is F5's job); it reports the handoff.
    return (f"CALIBRATION: DELEGATE to passk-stats over {labels['n']} labels "
            f"(per-category kappa, lower-CI-bound gate, bar={KAPPA_BAR}); stays advisory until owner promotes")


def shadow_log(record: dict) -> str:
    """Append ONE JSON line to the bounded, rotating shadow sink. Never the main ledger."""
    try:
        SINK.parent.mkdir(parents=True, exist_ok=True)
        if SINK.exists() and SINK.stat().st_size > SINK_ROTATE_BYTES:
            rotated = SINK.with_suffix(SINK.suffix + ".1")
            try:
                if rotated.exists():
                    rotated.unlink()
                SINK.rename(rotated)
            except Exception:
                pass
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "mode": "SHADOW/ADVISE",
                  "blocks": False, **record}
        with SINK.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return str(SINK)
    except Exception as e:
        return f"SHADOW-LOG-FAILED: {e!r}"


def selftest() -> int:
    """Run against the LIVE ledger + label corpus; emit a demo advisory verdict. Blocks nothing."""
    project = os.environ.get("CLAUDE_CWD", os.getcwd())
    events = cite_ledger(project, n=10)
    labels = read_label_corpus()
    passk = probe_passk_stats()
    cal = calibration_status(labels, passk)

    # Demo DoD item cited two legal ways (ledger event if any exist, else an evidence hash).
    if events:
        item_cite = ledger_citation(events[-1])
        cite_kind = "ledger-event"
    else:
        item_cite = hash_evidence("DEMO: no ledger events yet for this project", is_path=False)
        cite_kind = "evidence-hash (no ledger events -> hashed the observation)"

    verdict = {
        "verdict": "ADVISORY (does not gate)",
        "ran_after_deterministic_cluster": "unknown (selftest)",
        "checklist_demo": [{
            "item": "DoD item extracted (demo)", "type": "subjective", "opinion": "YES",
            "citation": item_cite, "citation_kind": cite_kind, "receipt": "unrunnable (demo)",
        }],
        "icd203": "9-standard rubric applied per item (see agents/agent-as-judge.md)",
        "calibration": cal,
        "ledger_events_available_for_citation": len(events),
        "label_corpus": labels,
        "passk_stats": passk,
        "blocking_findings": 0,
    }
    sink = shadow_log({"event": "selftest", "verdict": verdict})
    print("=== Agent-as-a-Judge selftest (ADVISORY — blocks nothing) ===")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    print(f"SHADOW-LOG -> {sink}")
    print("SUCCESS:agent-as-judge selftest — advisory verdict emitted, 0 blocking findings")
    return 0


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else selftest())
```

## Honest limits

- **Not a done-signal.** By council law it cannot block or clear; the deterministic cluster owns
  the done-signal. If someone wires this into a blocking path, that violates C3.
- **Correlated failure.** A same-vendor judge shares the fixer's blind spots; a cross-vendor Codex
  second judge is the independent check for contested/irreversible completions.
- **Calibration corpus is caught-error-only.** kappa vs claude-reflect corrections optimizes for
  re-catching *known* error classes; it is blind to escaped defects, so it can never license
  opinion-gating (only a fresh prospective held-out set the judge never saw could — deferred).
- **F5 dependency.** kappa/e-value calibration requires `passk-stats`; until it exists the judge is
  advisory with `CALIBRATION: UNAVAILABLE`. That is the correct, safe default — not a bug.
