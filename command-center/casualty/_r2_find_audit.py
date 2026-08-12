"""Locate the round-1 adversarial audit of LANE CASUALTY in the workflow journals.

Two-signal identification (never a bare text match):
  S1: journal record whose serialized result contains the audit's self-declared lane string.
  S2: the record's own 'label'/'key' field naming an audit phase.
Prints candidates with sizes so the caller can pick, then dumps the chosen result.
"""
import json
import os
import sys

ROOT = os.path.expanduser(
    "~/.claude/projects/C--Users-Prekzursil/30bd50d4-5a72-4c19-8fd5-85b6430c7b7d/subagents/workflows"
)
NEEDLE = "LANE CASUALTY"
AUDIT_HINT = "independent audit"


def scan_journal(path):
    hits = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            blob = json.dumps(rec, ensure_ascii=False)
            if NEEDLE in blob:
                hits.append((lineno, rec, len(blob), AUDIT_HINT in blob))
    return hits


def main():
    wfs = sys.argv[1:] or ["wf_e58dfd3f-7b1", "wf_9cb1a66a-36f"]
    for wf in wfs:
        jp = os.path.join(ROOT, wf, "journal.jsonl")
        if not os.path.exists(jp):
            print(f"[MISS] {jp}")
            continue
        hits = scan_journal(jp)
        print(f"[{wf}] journal records mentioning {NEEDLE!r}: {len(hits)}")
        for lineno, rec, size, is_audit in hits:
            keys = sorted(rec.keys())
            label = rec.get("label") or rec.get("key") or "<none>"
            print(
                f"  line={lineno} size={size} audit_hint={is_audit} "
                f"label={str(label)[:70]!r} keys={keys}"
            )


if __name__ == "__main__":
    main()
