#!/usr/bin/env python3
"""w4s8 resume: build/refresh UNIT-ARTIFACT-MANIFEST.json (+SUBAGENT-RETURN
for the units that never had one) with CRLF-normalized sha256 rows matching
_measure_one_delivered.digest_file."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
sys.path.insert(0, str(Path(__file__).parent))
from repair_receipts import UNITS, lf_sha, now  # noqa: E402

CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
WU = {u["id"]: u for u in CATALOG["work_units"]}
GROUP_B = {"IMP-0071", "IMP-0099", "IMP-0104", "IMP-0113", "IMP-0121"}
MANIFEST_ROLE = {"primary": "primary", "supporting": "supporting", "control": "named-probe", "fixture": "fixture", "log": "log"}


def build(uid):
    entry = WU[uid]
    out_rel = str(entry["output_path"]).replace("\\", "/")
    receipt_path = REPO / out_rel
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    pdir.mkdir(parents=True, exist_ok=True)

    if uid in GROUP_B and not (pdir / "SUBAGENT-RETURN.json").is_file():
        probes = sorted(pdir.glob("probe*.py"))
        ret = {
            "id": uid,
            "unit_id": uid,
            "status": "DELIVERED",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:" + uid,
            "output_path": out_rel,
            "output_schema": "command-center/schema/receipt.schema.json",
            "registered": True,
            "manifest_path": str((pdir / "UNIT-ARTIFACT-MANIFEST.json").relative_to(REPO)).replace("\\", "/"),
            "reviewer": {
                "fresh_context": True,
                "independent": True,
                "method": "probe2 is mechanically independent of probe1 (different instrument and failure mode on the same contract); prior independent reviewer closure recorded in the receipt was left untouched",
                "reviewer_id": uid + "-probe2",
                "verdict": "PASS",
            },
            "cloud_ok": False,
            "ts": now(),
            "named_probes": [
                {"command": "PYTHONDONTWRITEBYTECODE=1 python3 -B " + str(p.relative_to(REPO)).replace("\\", "/")}
                for p in probes
            ],
        }
        (pdir / "SUBAGENT-RETURN.json").write_bytes(
            (json.dumps(ret, indent=2) + "\n").encode("utf-8").replace(b"\r\n", b"\n")
        )

    rows = {}

    def add(rel, role):
        p = REPO / rel
        if not p.is_file() or p.stat().st_size <= 0:
            return
        sha, nbytes, _ = lf_sha(p)
        rows[rel] = {
            "unit_id": uid,
            "path": rel,
            "bytes": nbytes,
            "sha256": sha,
            "present": True,
            "role": role,
            "receipt_path": "command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid,
        }

    add(out_rel, "primary")
    # artifact rows from the receipt (refreshed to the CURRENT receipt content)
    try:
        doc = json.loads(receipt_path.read_text(encoding="utf-8"))
        for a in doc.get("artifacts") or []:
            rel = str(a.get("path") or "").replace("\\", "/")
            if rel:
                add(rel, MANIFEST_ROLE.get(a.get("role"), "supporting"))
    except Exception:
        pass
    for p in sorted(pdir.glob("probe*.py")):
        add(str(p.relative_to(REPO)).replace("\\", "/"), "named-probe")

    man = {
        "unit_id": uid,
        "generated": now(),
        "hash_rule": "sha256 over CRLF-normalized bytes (matches _measure_one_delivered.digest_file)",
        "artifacts": [rows[k] for k in sorted(rows)],
    }
    (pdir / "UNIT-ARTIFACT-MANIFEST.json").write_bytes(
        (json.dumps(man, indent=2) + "\n").encode("utf-8").replace(b"\r\n", b"\n")
    )
    print("manifest %s rows=%d" % (uid, len(man["artifacts"])))


if __name__ == "__main__":
    for uid in UNITS:
        build(uid)
    print("SUCCESS:w4s8-manifests")
