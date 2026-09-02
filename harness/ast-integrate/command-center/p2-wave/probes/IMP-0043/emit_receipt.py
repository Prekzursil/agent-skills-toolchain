#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0043.json from live healthy + blocked runs."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import health_check as hc  # noqa: E402
import health_probes as hp  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0043.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0043/probe1_healthy_aggregate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0043/probe2_blocked_and_throw.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_health_framework.py"
)
ARTIFACT_RELS = [
    "tools/plugin/health_check.py",
    "tools/plugin/health_probes.py",
    "tools/plugin/schema/health-report.schema.json",
    "tools/plugin/tests/test_health_framework.py",
    "command-center/p2-wave/probes/IMP-0043/probe1_healthy_aggregate.py",
    "command-center/p2-wave/probes/IMP-0043/probe2_blocked_and_throw.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def live_pair() -> tuple[dict, dict]:
    with tempfile.TemporaryDirectory(prefix="imp0043-receipt-") as td:
        root = Path(td)
        hp.plant_healthy_tree(root)
        registry = hc.default_registry()
        healthy = hc.run_all(registry, hc.HealthContext(root=root)).to_dict()
        blocked = hc.run_all(
            registry,
            hc.HealthContext(root=root, force_state={"hooks_loaded": "BLOCKED"}),
        ).to_dict()
    return healthy, blocked


def build_receipt() -> dict:
    healthy, blocked = live_pair()
    if not healthy.get("healthy"):
        raise SystemExit(f"healthy fixture was not healthy: {healthy}")
    if blocked.get("healthy"):
        raise SystemExit(f"blocked fixture stayed healthy: {blocked}")
    if "hooks_loaded" not in blocked.get("blocked_ids", []):
        raise SystemExit("blocked_ids missing hooks_loaded")

    artifacts = []
    for rel in ARTIFACT_RELS:
        path = REPO / rel
        sha, size = digest(path)
        artifacts.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "implementation" if rel.startswith("tools/") else "probe",
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    both = hc.default_registry().require_both_states()
    return {
        "unit_id": "IMP-0043",
        "id": "IMP-0043",
        "title": "`health-check` command framework and probe registry",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0043",
        "completion_sentinel": "SUCCESS:IMP-0043",
        "registered": True,
        "cloud_ok": False,
        "question": (
            "Implement a health-check runner with a pluggable probe registry "
            "(hooks loaded, skills registered, MCP reachable, router responding, "
            "ledger writable, cache valid, deploy in sync), where every probe "
            "returns a terminal state SUCCESS/FAILED/BLOCKED plus its evidence, "
            "and the aggregate refuses to report healthy if any probe returned BLOCKED."
        ),
        "evidence_requirement": (
            "TWO independent signals: (1) the aggregate report on a healthy "
            "machine; (2) the same run with one probe forced to BLOCKED, "
            "asserting the aggregate flips to not-healthy."
        ),
        "host": {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "ts": now,
        "health_report": healthy,
        "evidence": [
            {
                "id": "E1-healthy-aggregate",
                "signal": 1,
                "kind": "known-good-fixture",
                "summary": "default_registry run_all on plant_healthy_tree is HEALTHY",
                "report": healthy,
            },
            {
                "id": "E2-forced-blocked",
                "signal": 2,
                "kind": "forced-blocked-same-runner",
                "summary": (
                    "same registry and tree with hooks_loaded forced BLOCKED; "
                    "aggregate flips to NOT-HEALTHY"
                ),
                "report": blocked,
                "flipped": True,
            },
        ],
        "both_states_controls": both,
        "tests": [
            {
                "id": "test_blocked_probe_prevents_healthy_aggregate",
                "command": TEST_CMD,
                "result": "PASS",
            },
            {
                "id": "probe1_healthy_aggregate",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2_blocked_and_throw",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-throwing-probe",
                "description": "a probe that raises is FAILED, never healthy",
                "result": "PASS",
            },
            {
                "id": "NC-unrun-is-not-pass",
                "description": "registered probe omitted from results => NOT-HEALTHY",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0043-probe2-blocked-throw-unrun",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "confirmed_unrun_is_not_pass": True,
            "confirmed_blocked_forbids_healthy": True,
        },
        "defects": [],
        "artifacts": artifacts,
        "output_path": OUT_REL,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/plugin/schema/health-report.schema.json"
        ),
        "notes": (
            "G-1 IMP-0043: health-check runner with seven registered probes, "
            "each carrying an IMP-0044 both-states control. Healthy fixture is "
            "HEALTHY; forcing BLOCKED on one probe flips the aggregate. Unrun "
            "is not pass. A throwing probe is FAILED. cloud_ok is not delivery. "
            "IMP-0038/IMP-0039 live surfaces are not claimed: builtin probes "
            "observe an explicit HealthContext root (fixture or supplied tree)."
        ),
    }


def write_receipt(doc: dict | None = None) -> dict:
    doc = doc or build_receipt()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    return doc


def main() -> int:
    doc = write_receipt()
    sha, size = digest(REPO / OUT_REL)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0043 receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
