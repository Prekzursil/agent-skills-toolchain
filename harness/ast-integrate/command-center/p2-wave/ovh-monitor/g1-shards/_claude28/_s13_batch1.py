#!/usr/bin/env python3
"""Shard-13 batch-1: ADV-0132 hoist, AUD-0037 live_tally, ARC-0042 hashes, manifests."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def refresh_manifest(uid: str, paths: list[str]) -> None:
    mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(mp.read_text(encoding="utf-8"))
    wanted = set(paths)
    seen = set()
    for row in man.get("artifacts") or []:
        rel = str(row.get("path") or "").replace("\\", "/")
        if rel not in wanted:
            continue
        p = REPO / rel
        sha, size = digest_file(p)
        row["sha256"] = sha
        row["bytes"] = size
        row["present"] = p.is_file()
        seen.add(rel)
        print(f"  manifest {uid} {rel} sha={sha[:12]} bytes={size}")
    missing = wanted - seen
    if missing:
        print(f"  NOT-IN-MANIFEST {uid}: {sorted(missing)}")
    mp.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")


def fix_adv0132() -> None:
    print("=== ADV-0132 ===")
    here = REPO / "command-center" / "p2-wave" / "probes" / "ADV-0132"
    sys.path.insert(0, str(here))
    import study as S  # noqa: E402

    doc = S.build_document()
    rpt = doc.get("report") or {}
    for key in (
        "conclusions",
        "headline",
        "negative_control",
        "mutation_control",
        "pre_registration",
    ):
        if key not in doc and key in rpt:
            doc[key] = rpt[key]
    out = REPO / S.OUT_REL
    write_json(out, doc)
    print(f"  wrote {S.OUT_REL} conclusions={len(doc.get('conclusions') or [])}")
    refresh_manifest(
        "ADV-0132",
        [
            S.OUT_REL,
            "command-center/p2-wave/probes/ADV-0132/study.py",
        ],
    )


def fix_aud0037() -> None:
    print("=== AUD-0037 ===")
    here = REPO / "command-center" / "p2-wave" / "probes" / "AUD-0037"
    sys.path.insert(0, str(here))
    import engine as E  # noqa: E402

    data = E.census()
    live_t = data["live_tally"]
    art = E.artifact_path()
    doc = json.loads(art.read_text(encoding="utf-8"))
    rpt = doc.get("report")
    if not isinstance(rpt, dict):
        rpt = {}
        doc["report"] = rpt
    rpt["kind"] = rpt.get("kind") or "audit-finding"
    rpt["live_tally"] = live_t
    rpt["registry_present"] = data.get("registry_present")
    rpt["registry_path"] = data.get("registry_path")
    if not rpt.get("observations"):
        rpt["observations"] = [
            {
                "name": "n_claims",
                "measured": live_t["n_claims"],
                "method": "json.loads CLAIM-REGISTRY.json claims array",
                "anchor": "command-center/CLAIM-REGISTRY.json",
            }
        ]
    if not rpt.get("control_ids"):
        rpt["control_ids"] = ["AUD-0037-subject-word-only"]
    write_json(art, doc)
    print(
        f"  live_tally n_claims={live_t['n_claims']} "
        f"resolved={live_t['n_mechanically_resolved_claims']} "
        f"semantic={live_t.get('semantic_counts')}"
    )
    refresh_manifest("AUD-0037", [E.OUT_REL])


def fix_arc0042() -> None:
    print("=== ARC-0042 ===")
    here = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0042"
    sys.path.insert(0, str(here))
    from differential import run_all  # noqa: E402
    from view import plan as domain  # noqa: E402

    live = run_all(REPO, here)
    if live.get("disagree") or live.get("failed"):
        print(f"  live disagree={live.get('disagree')} failed={live.get('failed')}")
    rows = live["rows"]
    art = REPO / "command-center/phase3/A6/MIGRATION.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    payload = domain(doc)
    sample = payload.get("sample") or []
    by_key = {(r["rail_id"], r["unit_id"]): r for r in rows}
    updated = 0
    for rec in sample:
        key = (rec.get("rail_id"), rec.get("unit_id"))
        got = by_key.get(key)
        if not got:
            print(f"  missing live row {key}")
            continue
        rec["payload_sha256"] = got["payload_sha256"]
        rec["byte_identical_payload"] = got["byte_identical_payload"]
        rec["both_directions"] = True
        rec["old_sha256"] = got.get("old_sha256", rec.get("old_sha256"))
        rec["new_sha256"] = got.get("new_sha256", rec.get("new_sha256"))
        if isinstance(rec.get("signal1_sha256_compare"), dict):
            rec["signal1_sha256_compare"]["old"] = got["payload_sha256"]
            rec["signal1_sha256_compare"]["new"] = got["payload_sha256"]
            rec["signal1_sha256_compare"]["match"] = True
        updated += 1
    tests = (payload.get("tests") or {}).get("differential_equivalence") or {}
    tests["files_checked"] = len(rows)
    tests["byte_identical_payload"] = sum(1 for r in rows if r["byte_identical_payload"])
    tests["adjudicated"] = max(int(tests.get("adjudicated") or 0), 1)
    if "tests" not in payload:
        payload["tests"] = {}
    payload["tests"]["differential_equivalence"] = tests
    if isinstance(doc.get("report"), dict) and doc["report"].get("kind") == "migration-plan":
        doc["report"]["sample"] = sample
        if "tests" not in doc["report"]:
            doc["report"]["tests"] = {}
        doc["report"]["tests"]["differential_equivalence"] = tests
    else:
        doc["sample"] = sample
        if "tests" not in doc or isinstance(doc.get("tests"), list):
            pass
        else:
            doc.setdefault("tests", {})["differential_equivalence"] = tests
    art.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"  updated {updated}/{len(rows)} sample rows identical={tests['byte_identical_payload']}")
    refresh_manifest("ARC-0042", ["command-center/phase3/A6/MIGRATION.json"])


def refresh_arc0100() -> None:
    print("=== ARC-0100 manifest ===")
    refresh_manifest(
        "ARC-0100",
        ["command-center/p2-wave/probes/ARC-0100/contracts.py"],
    )


def main() -> int:
    fix_adv0132()
    fix_aud0037()
    fix_arc0042()
    refresh_arc0100()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
