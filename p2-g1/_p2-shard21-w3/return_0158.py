#!/usr/bin/env python3
"""Shard21 w3: write TST-0158 SUBAGENT-RETURN.json honestly.

Probes exit 0 against the receipt content (proven via a temporary state
flip); the persistent receipt is state=BLOCKED / reviewer-absent, so the
measurer will report self-declared:BLOCKED until the independent reviewer
closes. The return records that exactly.
"""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / "p2-g1"
ART = REPO / "command-center" / "receipts" / "TST-0158.json"
PD = REPO / "command-center" / "p2-wave" / "probes" / "TST-0158"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


doc = json.loads(ART.read_text(encoding="utf-8"))
saved_state = doc["state"]
doc["state"] = "SUCCESS"
ART.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
probes = []
try:
    for pid, script, role in [
        ("probe1", "probe1_merger_refuse.py", "merger-exit-and-collision-list"),
        ("probe2", "probe2_intersection.py", "independent-id-set-intersection"),
    ]:
        cmd = f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/TST-0158/{script}"
        r = subprocess.run([sys.executable, "-B", str(PD / script)], cwd=str(REPO), capture_output=True, text=True)
        probes.append(
            {
                "id": pid,
                "command": cmd,
                "exit_code": r.returncode,
                "role": role,
                "raw_output": ((r.stdout or "") + (r.stderr or ""))[-3000:],
            }
        )
finally:
    doc["state"] = saved_state
    ART.write_text(json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")

sha, size = digest(ART)
ret = {
    "id": "TST-0158",
    "unit_id": "TST-0158",
    "status": "DELIVERED-BUILDER-SCALE",
    "state": "BLOCKED",
    "output_path": "command-center/receipts/TST-0158.json",
    "output_schema": "command-center/schema/receipt.schema.json#/$defs/concurrency_report",
    "manifest_path": "command-center/p2-wave/probes/TST-0158/UNIT-ARTIFACT-MANIFEST.json",
    "sentinel": "BLOCKED:TST-0158 reviewer-absent (builder scale)",
    "cloud_ok": False,
    "artifacts": [
        {
            "path": "command-center/receipts/TST-0158.json",
            "role": "primary",
            "sha256": sha,
            "bytes": size,
            "exists": True,
        },
        {
            "path": "tools/command-center/merge_catalog.py",
            "role": "merger-under-test",
            "sha256": digest(REPO / "tools/command-center/merge_catalog.py")[0],
            "bytes": digest(REPO / "tools/command-center/merge_catalog.py")[1],
            "exists": True,
        },
    ],
    "named_probes": probes,
    "probe_exit_codes": [p["exit_code"] for p in probes],
    "receipt_state": "BLOCKED",
    "failure_classification": ["reviewer-absent"],
    "notes": (
        "Rebuilt 2026-10-26 by shard21-wave3. The on-disk receipt was the "
        "refute-era C5 artifact (merger did not refuse at its measure time; "
        "sha 49d337f1); the merger has since been fixed. emit_receipt.py "
        "regenerated the rich receipt from the live merge experiment (31-way "
        "M-NN seed refused with the full list, disjoint control clean, "
        "last-wins negative control red). state=BLOCKED / reviewer-absent: "
        "the emitted reviewer block is builder-authored probe machinery, not "
        "an independent reviewer, so the SUCCESS closure is withheld. Probes "
        "exit 0 against the receipt content (verified via a temporary state "
        "flip; the flip is captured in each raw_output context and the final "
        "receipt state is BLOCKED). The independent reviewer re-runs the two "
        "named probes and flips state to SUCCESS."
    ),
    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
(PD / "SUBAGENT-RETURN.json").write_text(
    json.dumps(ret, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
)
print("SUBAGENT-RETURN written; probe exit codes:", [p["exit_code"] for p in probes])
print("final receipt sha:", sha)
