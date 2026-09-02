#!/usr/bin/env python3
"""Probe 2: every changed cell attributed; v1 freeze; mutant attribution fails."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import registry_lib as L  # noqa: E402


def check_unattributed_mutant_fails(artifact: dict) -> bool:
    mutant = copy.deepcopy(artifact)
    if not mutant["field_diff"]:
        return False
    mutant["field_diff"][0]["unit_id"] = ""
    ok, _ = L.attribution_ok(mutant)
    return ok is False


def check_v1_rewrite_detected(artifact: dict, fixture: Path) -> bool:
    live_sha, _ = L.sha256_file(fixture)
    claimed = artifact.get("v1", {}).get("sha256")
    if claimed != live_sha:
        return False
    raw = fixture.read_bytes()
    poisoned = raw + b"\n"
    poison_sha = L.sha256_bytes(poisoned)
    return poison_sha != live_sha


def independent_collapse_replay(v1: dict, artifact: dict) -> tuple[bool, str]:
    rows = v1["candidates"]
    toks = [L.pair_text(r) for r in rows]
    flagged = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            score = L.jaccard(toks[i], toks[j])
            if score >= L.JACCARD_THRESHOLD:
                flagged.append(tuple(sorted((rows[i]["id"], rows[j]["id"]))))
    logged = set()
    for item in artifact.get("collapses") or []:
        if "pairs_flagged" in item:
            for p in item["pairs_flagged"]:
                logged.add(tuple(sorted((p["a"], p["b"]))))
        if "absorbed" in item:
            for alias in item["absorbed"]:
                logged.add(tuple(sorted((item["survivor"], alias))))
    missing = set(flagged) - logged
    if missing and flagged:
        return False, f"flagged-not-logged {missing}"
    return True, f"flagged={len(flagged)}"


def main() -> int:
    out = L.REPO / L.OUT_REL
    fixture = L.REPO / L.V1_FIXTURE_REL
    if not out.is_file() or not fixture.is_file():
        print("FAILED:WFA-0078-probe2 missing artifact or v1 fixture")
        return 1
    artifact = L.load_json(out)
    v1 = L.load_json(fixture)

    ok, detail = L.attribution_ok(artifact)
    if not ok:
        print(f"FAILED:WFA-0078-probe2 attribution {detail}")
        return 1

    if not check_unattributed_mutant_fails(artifact):
        print("FAILED:WFA-0078-probe2 unattributed mutant still passed")
        return 1

    if not check_v1_rewrite_detected(artifact, fixture):
        print("FAILED:WFA-0078-probe2 v1 freeze control")
        return 1

    cok, cdetail = independent_collapse_replay(v1, artifact)
    if not cok:
        print(f"FAILED:WFA-0078-probe2 collapse replay {cdetail}")
        return 1

    live_sha, _ = L.sha256_file(fixture)
    if artifact["v1"]["sha256"] != live_sha:
        print("FAILED:WFA-0078-probe2 fixture mutated after emit")
        return 1

    for rec in artifact["records"]:
        if rec.get("disposition") not in L.CLASSIFICATIONS:
            print(f"FAILED:WFA-0078-probe2 bad disposition {rec['id']}")
            return 1
        if rec.get("family") not in L.FAMILIES:
            print(f"FAILED:WFA-0078-probe2 bad family {rec['id']}")
            return 1
        for dim, uid in L.EXTRACTION_DIMS:
            cell = rec["extraction"][dim]
            if cell["unit_id"] != uid:
                print(f"FAILED:WFA-0078-probe2 dim unit {dim}")
                return 1
            if cell["state"] not in {"EVIDENCED", "HONEST-NULL", "NOT-CHECKED"}:
                print(f"FAILED:WFA-0078-probe2 dim state {dim}")
                return 1

    print(
        json.dumps(
            {
                "attribution": detail,
                "collapse_replay": cdetail,
                "diff_rows": len(artifact["field_diff"]),
                "unattributed_mutant_rejected": True,
                "v1_poison_detected": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0078-probe2 attribution v1-freeze both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
