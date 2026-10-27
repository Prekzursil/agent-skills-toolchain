#!/usr/bin/env python3
"""RES-0091 property battery, both states (known-good passes, known-broken fires).
Recreated 2026-10-25 (wave-2 shard 17) after the original probe tree was lost;
role follows the artifact: properties assert decidable shape, never the model's
opinion; untestable properties stay named."""
from __future__ import annotations
import json, random, re, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _shard17_lib as L

UID = "RES-0091"
SK = "sk-" + "a" * 40

def p1_schema_valid(doc):
    return (isinstance(doc, dict) and isinstance(doc.get("unit_id"), str)
            and isinstance(doc.get("state"), str) and isinstance(doc.get("sentinel"), str))

def p2_idempotent_across_reruns(loader):
    """Canonical bytes must be stable across independent re-runs of the
    load+canonicalize pipeline (a regenerating volatile field breaks it)."""
    a = json.dumps(loader(), sort_keys=True, separators=(",", ":"))
    b = json.dumps(loader(), sort_keys=True, separators=(",", ":"))
    return a == b

def p3_no_credentials(text):
    return not L.scan_credentials(text)

def p4_counter_monotonic(counters):
    return all(b >= a for a, b in zip(counters, counters[1:]))

def main() -> int:
    c = []
    p, doc, text = L.load_artifact(UID)
    good = json.loads((L.REPO / "command-center/receipts/IMP-0167.json").read_text(encoding="utf-8"))
    good_text = json.dumps(good)
    c.append(("P1 schema-validity: known-good receipt passes", p1_schema_valid(good), "IMP-0167"))
    c.append(("P2 rerun-idempotence: canonical bytes stable",
              p2_idempotent_across_reruns(lambda: json.loads(json.dumps(good))), "IMP-0167"))
    c.append(("P3 credential-absence: receipt clean", p3_no_credentials(good_text), "IMP-0167"))
    c.append(("P4 counter-monotonicity: monotone counter passes", p4_counter_monotonic([0, 1, 3, 6, 6, 7, 9, 12]),
              "[0,1,3,6,6,7,9,12]"))
    b1 = dict(good); b1.pop("unit_id", None)
    def broken_loader():
        d = json.loads(json.dumps(good))
        d["_regenerated_at_run"] = random.random()  # volatile field, new per run
        return d
    b3 = dict(good); b3["notes"] = good_text[:10] + " " + SK
    c.append(("P1 fires on known-broken (unit_id missing)", not p1_schema_valid(b1), "broken"))
    c.append(("P2 fires on known-broken (volatile field regenerated per run)",
              not p2_idempotent_across_reruns(broken_loader), "broken"))
    c.append(("P3 fires on known-broken (planted sk- token)", not p3_no_credentials(json.dumps(b3)), "broken"))
    c.append(("P4 fires on known-broken (decreasing counter)", not p4_counter_monotonic([0, -1, 3, 6, 6, 7, 9, 12]),
              "[0,-1,3,...]"))
    unt = doc.get("untestable_properties") or []
    c.append(("control: >=2 untestable properties named with reasons",
              len(unt) >= 2 and all(str(u.get("why") or "").strip() for u in unt),
              f"{[u.get('id') for u in unt]}"))
    return L.finish(UID, "probe1", c)

if __name__ == "__main__":
    raise SystemExit(main())
