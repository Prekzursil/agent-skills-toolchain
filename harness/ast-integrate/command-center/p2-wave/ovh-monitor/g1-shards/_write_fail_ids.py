import json
from pathlib import Path

p = Path(__file__).resolve().parent
doc = json.loads((p / "class-envelope.measure.json").read_text(encoding="utf-8"))
ids = [str(x) for x in (doc.get("fail_ids") or [])]
assigned: set[str] = set()
for name in ("class-sha.txt", "class-sentinel.txt", "class-output.txt", "class-other.txt"):
    f = p / name
    if f.is_file():
        assigned.update(ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip())
fail = [u for u in ids if u in assigned]
(p / "class-other.fail-ids.txt").write_text("\n".join(fail) + "\n", encoding="utf-8")
print("fail_ids", len(ids), "assigned_fail", len(fail), "assigned", len(assigned), "ok_assigned", len(assigned) - len(fail))
