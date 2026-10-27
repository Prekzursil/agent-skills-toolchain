#!/usr/bin/env python3
"""CNF-0167 probe1: inversion-fixture coherence under each kind's own rule - receipt-before-X
rows must have the receipt instant strictly before the cited instant; the event-log-order row
must carry a seq pair with two distinct instants; every classification must be defined by the
policy; naive-timestamp handling must be its own class. Emitted by shard8-w2 resume builder."""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0167.json")
    inv = d["inversions"]
    ck("five_fixture_rows", len(inv) == 5)
    pol = d["classification_policy"]
    ok_cls = True
    ok_rule = True
    for r in inv:
        ok_cls &= r.get("classification") in pol
        k = r.get("kind")
        if k == "receipt-before-cited-artifact":
            ok_rule &= iso(r["receipt_ts"]) < iso(r["artifact_mtime"])
        elif k == "receipt-before-git-commit":
            ok_rule &= iso(r["receipt_ts"]) < iso(r["git_commit_ts"])
        elif k == "receipt-before-dependency":
            dep = r.get("dependency_ts") or r.get("event_ts")
            ok_rule &= iso(r["receipt_ts"]) < iso(dep)
        elif k == "event-log-order-inversion":
            ok_rule &= (r["seq_earlier"] < r["seq_later"]) and (r["receipt_ts"] != r["event_ts"])
        else:
            ok_rule = False
    ck("rows_classified_within_policy", ok_cls)
    ck("rows_contradict_under_own_kind_rule", ok_rule)
    ck("policy_covers_all_three_verdicts",
       {"clock-artifact", "fabrication", "unorderable-naive"}.issubset(set(pol)))
    ck("unorderable_class_requires_offset", "offset" in pol["unorderable-naive"])
    ck("sentinel_in_artifact", "SUCCESS:CNF-0167" in (REPO / "command-center/receipts/CNF-0167.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0167")

if __name__ == "__main__":
    sys.exit(main())
