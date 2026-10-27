"""BUILD lane probe: extract the HEADLINE CLAIM of each review-only unit so it can be falsified."""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
IDS = [
    "AUD-0006",
    "AUD-0020",
    "AUD-0021",
    "AUD-0030",
    "AUD-0041",
    "AUD-0051",
    "CC-0002",
]
cat = json.loads(
    (ROOT / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by_id = {u["id"]: u for u in cat["work_units"]}

for uid in IDS:
    p = ROOT / by_id[uid]["output_path"]
    d = json.loads(p.read_text(encoding="utf-8"))
    print("=" * 100)
    print(f"{uid}  state={d.get('state')}  {p.name}")
    rep = d.get("report", {})
    if isinstance(rep, dict):
        print("  report keys:", list(rep.keys()))
        for k, v in rep.items():
            if isinstance(v, (int, float, bool)) or (
                isinstance(v, str) and len(v) < 400
            ):
                print(f"    {k} = {v!r}")
            elif isinstance(v, list):
                print(f"    {k} = list[{len(v)}]")
            elif isinstance(v, dict):
                print(f"    {k} = dict[{len(v)}] keys={list(v.keys())[:12]}")
    print("  -- evidence --")
    ev = d.get("evidence")
    print("   ", json.dumps(ev)[:900] if ev else None)
    print("  -- failure --")
    print("   ", json.dumps(d.get("failure"))[:700])
    print("  -- reviewer --")
    print("   ", json.dumps(d.get("reviewer"))[:700])
    print("  -- artifacts --")
    print("   ", json.dumps(d.get("artifacts"))[:500])
