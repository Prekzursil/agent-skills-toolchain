"""C11 lane probe: every artifact the producer's fail-closed walk will trip on.

unit_manifest.py derives from receipt-shaped JSON under command-center/receipts,
adversarial/, audit/ (unit_id + non-empty artifacts[]). Its derive() raises on the
FIRST absent artifact; this probe enumerates ALL of them so the repair is complete,
not whack-a-mole. Also reports, per receipt, the manifest_registration state so the
migration set is known in the same pass.
"""

from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIRS = ("receipts", "adversarial", "audit")
OLD = "command-center/ARTIFACT-MANIFEST.json"
NEW = "command-center/UNIT-ARTIFACT-MANIFEST.json"

missing_rows: list[dict] = []
corpus: list[dict] = []
for dirname in DIRS:
    base = ROOT / "command-center" / dirname
    if not base.is_dir():
        continue
    for p in sorted(base.rglob("*.json")):
        rel = p.relative_to(ROOT).as_posix()
        if any(
            part.startswith("_")
            for part in p.relative_to(ROOT / "command-center").parts
        ):
            continue
        if p.name in {"ARTIFACT-MANIFEST.json", "UNIT-ARTIFACT-MANIFEST.json"}:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(d, dict):
            continue
        uid = d.get("unit_id")
        arts = d.get("artifacts")
        if not (
            isinstance(uid, str) and uid.strip() and isinstance(arts, list) and arts
        ):
            continue
        mr = d.get("manifest_registration")
        mp = mr.get("manifest_path") if isinstance(mr, dict) else None
        reg = mr.get("registered") if isinstance(mr, dict) else None
        miss = []
        for a in arts:
            if isinstance(a, dict) and isinstance(a.get("path"), str):
                if not (ROOT / a["path"].replace("\\", "/")).is_file():
                    miss.append(a["path"])
        corpus.append(
            {"receipt": rel, "unit_id": uid, "manifest_path": mp, "registered": reg}
        )
        if miss:
            missing_rows.append({"receipt": rel, "unit_id": uid, "missing": miss})

print(f"producer corpus (receipt-shaped in receipts/adversarial/audit): {len(corpus)}")
from collections import Counter  # noqa: E402

print("manifest_path histogram:", dict(Counter(r["manifest_path"] for r in corpus)))
old_rows = [r for r in corpus if r["manifest_path"] == OLD]
print(f"OLD charter-manifest rows in producer corpus: {len(old_rows)}")
for r in old_rows:
    print(f"   {r['receipt']} ({r['unit_id']}) registered={r['registered']}")
print(f"\nreceipts with MISSING declared artifacts: {len(missing_rows)}")
for r in missing_rows:
    print(f"   {r['receipt']} ({r['unit_id']})")
    for m in r["missing"]:
        print(f"      missing: {m}")

out = ROOT / "command-center/p2-next/C11-MISSING-ARTIFACTS.json"
out.write_text(
    json.dumps({"corpus": corpus, "missing_rows": missing_rows}, indent=2) + "\n",
    encoding="utf-8",
    newline="\n",
)
print(f"\nSUCCESS:c11-missing-artifacts -> {out.relative_to(ROOT)}")
