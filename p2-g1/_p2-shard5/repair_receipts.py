#!/usr/bin/env python3
"""Shard5 repair: promote reviewer-extras from notes-strings to direct fields,
set test-row pass booleans from a live recomputation, refresh manifest rows.

Nothing is invented: every merged value is (a) already recorded in the receipt
itself and (b) re-derived live from the unit's own extractor modules.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
sys.path.insert(0, str(REPO / "command-center/p2-wave/probes/CNF-0188"))
import extractors as E18  # noqa: E402

def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)

def merge_extras(reviewer: dict) -> dict:
    """Promote the reviewer-extras JSON embedded in notes into direct fields."""
    notes = str(reviewer.get("notes") or "")
    marker = "reviewer-extras:"
    if marker not in notes:
        return reviewer
    blob = notes.split(marker, 1)[1].strip()
    try:
        extras = json.loads(blob)
    except json.JSONDecodeError:
        return reviewer
    if not isinstance(extras, dict):
        return reviewer
    merged = dict(reviewer)
    for k, v in extras.items():
        merged.setdefault(k, v)
    return merged

def refresh_manifests(receipt_rel: str, uid: str) -> None:
    """Update the sha256 row for receipt_rel in every manifest that lists it."""
    rec_path = REPO / receipt_rel
    sha, size = digest(rec_path)
    targets = [
        REPO / "command-center/p2-wave/probes" / uid / "UNIT-ARTIFACT-MANIFEST.json",
        REPO / "command-center/ARTIFACT-MANIFEST.json",
    ]
    for man in targets:
        if not man.is_file():
            continue
        data = json.loads(man.read_text(encoding="utf-8"))
        changed = False
        rows = data.get("artifacts") or []
        for row in rows:
            if (
                isinstance(row, dict)
                and str(row.get("path") or "").replace("\\", "/") == receipt_rel
            ):
                if row.get("sha256") != sha or row.get("bytes") != size:
                    row["sha256"] = sha
                    row["bytes"] = size
                    row["present"] = True
                    changed = True
        if changed:
            man.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"manifest-updated {man.name} row {receipt_rel} sha={sha[:16]} bytes={size}")

def fix_cnf0188() -> None:
    rel = "command-center/receipts/CNF-0188.json"
    path = REPO / rel
    d = json.loads(path.read_text(encoding="utf-8"))
    # reviewer: regenerate via the module that authored it (live derivation)
    live_rev = E18.reviewer_third_extractor(d["floors"])
    recorded = merge_extras(d.get("reviewer") or {})
    for k, v in live_rev.items():
        if k in recorded and recorded[k] != v:
            raise SystemExit(f"FAILED:shard5 CNF-0188 reviewer field drift {k}: {recorded[k]!r} vs live {v!r}")
    d["reviewer"] = live_rev
    # tests: set pass from a fresh live recomputation
    council = E18.council_fixture_extract()
    disagree = E18.disagreement_fixture_extract()
    live_tests = {t["id"]: t for t in E18.detector_tests(council, disagree)}
    for row in d.get("tests") or []:
        tid = row.get("id")
        live = live_tests.get(tid)
        if live is None:
            raise SystemExit(f"FAILED:shard5 CNF-0188 test {tid} not in live set")
        if not live.get("pass"):
            raise SystemExit(f"FAILED:shard5 CNF-0188 live test {tid} not pass")
        row["pass"] = True
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"receipt-repaired {rel} (reviewer direct fields + 7 test pass flags)")
    refresh_manifests(rel, "CNF-0188")

def fix_cnf0177() -> None:
    rel = "command-center/receipts/CNF-0177.json"
    path = REPO / rel
    d = json.loads(path.read_text(encoding="utf-8"))
    reviewer = merge_extras(d.get("reviewer") or {})
    if int(reviewer.get("n_tasks") or 0) != 10:
        raise SystemExit("FAILED:shard5 CNF-0177 reviewer-extras n_tasks not 10")
    tasks_path = reviewer.get("tasks_path") or ""
    if tasks_path:
        p = REPO / tasks_path
        if not p.is_file():
            raise SystemExit(f"FAILED:shard5 CNF-0177 tasks_path missing {tasks_path}")
        tasks = json.loads(p.read_text(encoding="utf-8")).get("tasks") or []
        if len(tasks) != 10:
            raise SystemExit(f"FAILED:shard5 CNF-0177 fixture has {len(tasks)} tasks")
    d["reviewer"] = reviewer
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"receipt-repaired {rel} (reviewer n_tasks=10 promoted to direct field)")
    refresh_manifests(rel, "CNF-0177")

if __name__ == "__main__":
    fix_cnf0188()
    fix_cnf0177()
    print("SUCCESS:shard5 receipts repaired")
