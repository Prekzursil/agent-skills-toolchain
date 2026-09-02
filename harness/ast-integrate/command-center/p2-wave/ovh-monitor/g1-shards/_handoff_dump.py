import hashlib
import json
from pathlib import Path

SH = Path(__file__).resolve().parent

def ids(name):
    p = SH / name
    if not p.is_file():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]

assigned = []
seen = set()
print("=== SHARD FILES ===")
for name in ("class-other.txt", "class-sha.txt", "class-sentinel.txt", "class-output.txt"):
    xs = ids(name)
    print(f"{name}: n={len(xs)} first={xs[:3]} last={xs[-3:] if xs else []}")
    for u in xs:
        if u not in seen:
            seen.add(u)
            assigned.append(u)
print(f"ASSIGNED_UNIQUE={len(assigned)}")

print("\n=== PASS1 JSONL SUCCESS last-lines (assigned only) ===")
p1 = {}
for ln in (SH / "class-envelope.measure.jsonl").read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    p1[rec["id"]] = rec
ok1 = []
for u in assigned:
    rec = p1.get(u) or {}
    if rec.get("line") == f"SUCCESS:delivered {u}" and rec.get("ok"):
        ok1.append(u)
        print(f"P1 {u} | {rec.get('line')}")
print(f"P1_ASSIGNED_SUCCESS={len(ok1)}")

print("\n=== PASS2 JSONL every last-line SUCCESS ===")
p2 = {}
for ln in (SH / "class-envelope.pass2.jsonl").read_text(encoding="utf-8").splitlines():
    rec = json.loads(ln)
    p2[rec["id"]] = rec
    if rec.get("line", "").startswith("SUCCESS:delivered"):
        print(f"P2 {rec['id']} ok={rec.get('ok')} | {rec.get('line')}")
print(f"P2_LINES={len(p2)} P2_OK={sum(1 for r in p2.values() if r.get('ok'))} P2_FAIL={sum(1 for r in p2.values() if not r.get('ok'))}")

print("\n=== REMAINING FILE ===")
rem_path = SH / "class-other.remaining.txt"
raw = rem_path.read_bytes()
text = rem_path.read_text(encoding="utf-8")
lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
fp = hashlib.sha256(text.encode("utf-8")).hexdigest()
print(f"bytes={len(raw)} lines={len(lines)} sha256={fp}")
print(f"first5={lines[:5]}")
print(f"last5={lines[-5:]}")

print("\n=== RESULT JSON COUNTS ===")
res = json.loads((SH / "class-other.txt.result.json").read_text(encoding="utf-8"))
print("attempted", res["attempted"], "ok", res["ok"], "fail", res["fail"], "verified", res["verified"])
print("remaining_fp", res["remaining_fp"])
print("fp_match", res["remaining_fp"] == fp)
print("ok_ids_n", len(res["ok_ids"]), "fail_ids_n", len(res["fail_ids"]))
