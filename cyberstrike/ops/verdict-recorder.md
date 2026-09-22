# ops: verdict-recorder — how CyberStrike engagements emit verdicts

SSOT module: `scripts/verdict_recorder.py` (G-13=C, garak-style JSONL recorder). Every
engagement / battery / lane test that produces a claim emits through it. This note is the
usage contract; the module docstring is the reference.

## Why (contract mapping)

- **S6 (immutable vocabulary):** only `SUCCESS` / `FAILED` / `INTERRUPTED` / `PENDING-OWNER`
  are writable — anything else raises `ValueError` at write time (fail-closed: an
  out-of-vocabulary status can never silently appear in a receipt).
- **Fail-closed completion:** a `SUCCESS` whose anchor file is missing on disk is DOWNGRADED
  to `FAILED` (`anchor_missing`) at record time. "Completion claims require disk artifacts."
  `INTERRUPTED`/`PENDING-OWNER` make no completion claim and keep their status.
- **S5 (artifact contract):** verdicts and findings are separate streams — `verdicts.jsonl`
  (one line per test attempt, per-test monotonic `attempt` counter) and `hits.jsonl`
  (individual detector findings; a dead server on the dead-list is a finding, not a test
  failure). Anchors are re-read from disk at record time and stored as sha8 + bytes.

## How to use in an engagement

```python
import sys; sys.path.insert(0, r"C:\Users\Prekzursil\.config\cyberstrike\scripts")
from verdict_recorder import VerdictRecorder, SUCCESS, FAILED, INTERRUPTED

with VerdictRecorder(run_id="engagement-<target>-<date>",
                     meta={"target": "<target>", "lane": "<lane>"}) as rec:
    rec.record("T-1", SUCCESS,
               details={"what": "..."},
               anchors=[r"path\to\artifact.json", {"path": r"path\to\receipt.md"}])
    rec.hit("T-1", "dead_front", server="semgrep", port=31119)   # finding, not a failure
# close() auto-writes run_summary.json (per-status counts + sha256 of both JSONLs)
```

CLI self-test (proves the vocabulary gate, the anchor downgrade, and the seal hashes):

```powershell
C:\Python314\python.exe C:\Users\Prekzursil\.config\cyberstrike\scripts\verdict_recorder.py
# EXPECT: SELFTEST-PASS {"SUCCESS": 1, "FAILED": 1, "INTERRUPTED": 0, "PENDING-OWNER": 0}
```

## Output location

Default: `D:\bolt\admin-crack-2026-09-19\raw\cs-audit\phase2-5\battery\<run_id>\`.
Override per-run with `out_dir=` or env `CS_BATTERY_OUT` (engagement trees under the active
project receipts dir — never HOME). `close()` seals `run_summary.json` including
`verdicts_sha256` / `hits_sha256` so post-hoc edits are detectable, with provenance
`disk-verified` (the seal re-hashes the files it summarizes).

## Discipline rules for callers

1. One `VerdictRecorder` per run id; never reuse a run id for a second execution (mint a
   `-v2` run instead; supersede, don't rewrite).
2. Never hand-edit the JSONL afterwards — a correction is a NEW `record()` call (the file is
   append-only by contract).
3. Exceptions inside the `with` block auto-emit `battery.harness INTERRUPTED` with the error
   string before sealing — let them propagate.
4. No credential values ever enter `details`/`hit` fields; anchors and shapes only (sha8 form
   for anything secret-shaped).
