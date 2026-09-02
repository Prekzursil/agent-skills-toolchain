#!/usr/bin/env python3
"""Probe 2: live-tree anchors + source-byte lineage. Does not import the crash matrix.

Independent of probe1: re-reads program writers at file:line, re-hashes the
fetched primary sources, and defaults to REFUTED when lineage or the
NON-COMPENSABLE class is missing.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/gem-hunt/RES-0157-transfer-durability-transaction-models.json"
LINEAGE = HERE / "fixtures" / "sources" / "LINEAGE.json"
SENTINEL = "SUCCESS:RES-0157"

# Declared independently of engine.py so a drift in the simulator cannot
# silently retarget this probe. Needles are live-tree substrings.
ANCHORS = [
    {
        "id": "local_artifact_write",
        "path": "tools/command-center/catalog.py",
        "line": 161,
        "needle": 'target.write_text(text, encoding="utf-8", newline="\\n")',
        "compensable": True,
    },
    {
        "id": "append_only_ledger",
        "path": "tools/command-center/close.py",
        "line": 91,
        "needle": 'handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\\n")',
        "compensable": True,
    },
    {
        "id": "cloud_worker_launch",
        "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        "line": 384,
        "needle": "proc = subprocess.Popen(",
        "compensable": True,
    },
    {
        "id": "github_pr_mutation",
        "path": "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
        "line": 235,
        "needle": "gh pr merge --auto --squash",
        "compensable": True,
    },
    {
        "id": "human_notification",
        "path": "command-center/WORK-UNIT-CATALOG.json",
        "line": 71726,
        "needle": "a sent notification is the expected candidate",
        "compensable": False,
    },
]


def fail(msg: str) -> int:
    print(f"FAILED:RES-0157-probe2 {msg}")
    return 1


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    if not LINEAGE.is_file():
        return fail("lineage-absent")
    lineage = json.loads(LINEAGE.read_text(encoding="utf-8"))
    src_rows = [s for s in (lineage.get("sources") or []) if isinstance(s, dict)]
    if len(src_rows) < 6:
        return fail(f"lineage-short:{len(src_rows)}")

    live_hits = []
    for spec in ANCHORS:
        path = REPO / spec["path"]
        if not path.is_file():
            return fail(f"anchor-missing:{spec['path']}")
        lines = path.read_text(encoding="utf-8").splitlines()
        idx = spec["line"] - 1
        if idx < 0 or idx >= len(lines):
            return fail(f"anchor-oob:{spec['id']}")
        if spec["needle"] not in lines[idx]:
            return fail(f"needle-miss:{spec['id']}")
        live_hits.append(spec["id"])

    classes = doc.get("side_effect_classes") or []
    if len(classes) != 5:
        return fail(f"class-count:{len(classes)}")
    art_ids = [c.get("id") for c in classes]
    if art_ids != [a["id"] for a in ANCHORS]:
        return fail(f"class-id-drift:{art_ids}")
    for spec, cls in zip(ANCHORS, classes):
        anchor = str(cls.get("program_anchor") or "")
        want = f"{spec['path']}:{spec['line']}"
        if anchor != want:
            return fail(f"anchor-drift:{spec['id']}:{anchor}")
        live_comp = spec["compensable"]
        art_comp = cls.get("compensable")
        if art_comp is not live_comp:
            return fail(f"compensable-drift:{spec['id']}")
        label = str(
            cls.get("compensation_or_noncompensable") or cls.get("compensation") or ""
        )
        if live_comp is False and label != "NON-COMPENSABLE":
            return fail(f"notify-not-flagged:{spec['id']}")
        if live_comp is True and label == "NON-COMPENSABLE":
            return fail(f"false-noncompensable:{spec['id']}")

    noncomp = [c for c in classes if c.get("compensable") is False]
    if len(noncomp) != 1 or noncomp[0].get("id") != "human_notification":
        return fail("negative-control-missing")

    art_sources = {
        s.get("file"): s
        for s in (doc.get("sources") or [])
        if isinstance(s, dict) and s.get("file")
    }
    hashed = 0
    for row in src_rows:
        if not row.get("present"):
            return fail(f"source-absent:{row.get('file')}")
        rel = str(row.get("path") or "")
        path = REPO / rel
        if not path.is_file():
            return fail(f"source-file-missing:{rel}")
        live = digest_file(path)
        if live != row.get("sha256"):
            return fail(f"lineage-sha-mismatch:{row.get('file')}")
        art = art_sources.get(row["file"])
        if not isinstance(art, dict):
            return fail(f"artifact-source-missing:{row.get('file')}")
        if art.get("sha256") != live:
            return fail(f"artifact-sha-mismatch:{row.get('file')}")
        if not art.get("resolved_url"):
            return fail(f"url-missing:{row.get('file')}")
        if not art.get("fetch_timestamp"):
            return fail(f"ts-missing:{row.get('file')}")
        hashed += 1
    if hashed < 6:
        return fail(f"hashed-short:{hashed}")

    claims = doc.get("claims") or []
    if len(claims) < 4:
        return fail(f"claims-short:{len(claims)}")
    for claim in claims:
        lineage_n = len(claim.get("source_lineage") or [])
        signals = claim.get("signals") or []
        if lineage_n < 1:
            return fail(f"claim-no-lineage:{claim.get('id')}")
        if len(signals) < 2:
            return fail(f"claim-single-signal:{claim.get('id')}")
        if not claim.get("confidence_band"):
            return fail(f"claim-no-kent:{claim.get('id')}")
        if not claim.get("independent_verification_path"):
            return fail(f"claim-no-verify:{claim.get('id')}")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer-not-independent")
    if str(reviewer.get("verdict") or "").upper() in {"REFUTED", "CHANGES-REQUESTED"}:
        return fail(f"reviewer:{reviewer.get('verdict')}")

    print(
        json.dumps(
            {
                "probe": "probe2-live-lineage",
                "live_hits": live_hits,
                "sources_hashed": hashed,
                "noncompensable": noncomp[0]["id"],
                "claims": len(claims),
            },
            sort_keys=True,
        )
    )
    print(
        f"anchors=5/{len(ANCHORS)} sources_hashed={hashed} "
        f"noncompensable=human_notification"
    )
    print("SUCCESS:RES-0157-probe2 live anchors and source-byte lineage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
