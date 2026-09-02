# RUNBOOK

Everything you can do to this command center, and the one-liner that does it. All paths are
repo-relative; run from the checkout root.

```workflow
{
  "id": "wf.runbook.list-open",
  "description": "List open command-center items without executing side effects.",
  "tools": ["Read"],
  "stop_rule": {"max_stages": 1, "on_error": "halt"},
  "stages": [
    {
      "id": "list-open",
      "type": "task",
      "tools": ["Read"],
      "inputs": ["command-center/STATUS.md"],
      "outputs": ["command-center/receipts/TST-0254-list.json"]
    }
  ]
}
```


## Read

```bash
python tools/command-center/close.py --list --only-open                 # every open item
python tools/command-center/close.py --list --program MONITOR           # one program
python tools/command-center/validate.py                                 # is the set complete?
python tools/command-center/validate.py --json                          # machine-readable report
```

`STATUS.md` is the human view and is generated — read it, never edit it.

## Move an item

```bash
# close (evidence is REQUIRED and a blank one is refused)
python tools/command-center/close.py R-M01 --evidence "monitors.toml:14 [cockpit]; monitorcore.unified --help exit 0"

# defer: stays OPEN, stops being surfaced, returns by itself
python tools/command-center/close.py R-M14 --defer "owner flagged highest-risk" --days 30

# supersede
python tools/command-center/close.py R-M03 --superseded-by R-M01 --evidence "R-M01 subsumes it"

# drop, only with a recorded owner decision
python tools/command-center/close.py R-A14 --dropped "owner decision <file:line>"

# progress note, no state change
python tools/command-center/close.py R-A02 --note "ledger half landed in PR #NNN" --action "residual: clean-room baseline"

# open a new one
python tools/command-center/close.py --open "wire the cockpit health probe" --program MONITOR \
  --action "add the probe" --effort S --depends-on R-M01
```

Add `--dry-run` to any of them to see the verdict without writing.

Every mutation rewrites `DEPENDENCY-GRAPH.json` and appends one line to
`events/EVENTS.jsonl`. You never edit either by hand.

## Re-render the derived files

```bash
python tools/command-center/render.py            # rewrite STATUS.md, OWNER-DECISIONS.md, ARTIFACT-MANIFEST.json
python tools/command-center/render.py --check    # CI form: fail on drift, write nothing
```

## Answer an owner question

Flip the question's `state` from `OPEN` to `ANSWERED` in `WORK-UNIT-CATALOG.json`
(`owner_questions`), record the answer text, then re-render. Every item that named that
question as a gate immediately stops counting it as a live blocker — so if such an item has no
next smallest action, `REACH-3` will report it as a dead end on the next validate. That is
intended: answering a question converts a blocked item into an actionable one, and something
has to say what the action now is.

## Re-seed from the register (destructive)

```bash
python tools/command-center/seed.py --force
```

Discards all close/defer history. Only correct when the register snapshot itself is replaced.
Update `sources/REGISTER.md` first, or REACH-6 will fail on the sha256 mismatch.

## Verify the whole thing

```bash
python -m pytest tools/command-center/tests -q
python -m pytest agent-self/harness/tests/test_register_gate.py -q
```

## The register gate (the resurfacing half)

The gate lives as the `register_gate` module inside `agent-self/harness/modules.py` and rides
the dispatcher wire that `settings.json` already runs for `UserPromptSubmit`. It ships in
**SHADOW**: it computes a verdict, writes it to the sampled shadow sink, and injects nothing.

```bash
# see what it would have said, without promoting it
python -m pytest agent-self/harness/tests/test_register_gate.py -q

# force a mode for one session (never needed in normal operation)
HARNESS_GATE_MODE__register_gate=advise   # surface the injection
HARNESS_REGISTER=off                      # hard off
```

Promotion criteria and the rollback line are in `RELEASE-CHECKLIST.md` and
`ROLLBACK-MANIFEST.md`. There is no `enforce` rung: the verdict is an inject, so `enforce`
would be identical and the rung is not offered.
