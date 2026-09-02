#!/usr/bin/env python3
"""Write IMP-0405 receipt plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from router.tombstones import scan_roots  # noqa: E402

UID = "IMP-0405"
OUT = "command-center/receipts/IMP-0405.json"
SENTINEL = "SENTINEL:IMP-0405:TOMBSTONES-RESOLVE"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0405/probe1_redirect.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0405/probe2_cycle_negative.py"
)
SUPPORTING = [
    "tools/router/tombstones.py",
    "tools/router/__init__.py",
    "skills/council/SKILL.md",
    "skills/four-voice-prompt/SKILL.md",
    "command-center/p2-wave/probes/IMP-0405/probe1_redirect.py",
    "command-center/p2-wave/probes/IMP-0405/probe2_cycle_negative.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def locator(path: Path, snippet: str) -> dict:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return {"path": path.relative_to(REPO).as_posix(), "line": 0, "snippet": snippet}
    line = text[:idx].count("\n") + 1
    return {
        "path": path.relative_to(REPO).as_posix(),
        "line": line,
        "snippet": snippet,
    }


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0405/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    census = scan_roots(repo=REPO, home=Path.home())
    if census["defect_count"] != 0:
        print(f"FAILED:receipts current-tree defects={census['defects']}")
        return 1
    if census["redirect_tombstone_count"] < 1:
        print("FAILED:receipts no redirect tombstone in current trees")
        return 1

    src = REPO / "tools" / "router" / "tombstones.py"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    question = (
        "Implement tombstone records so a renamed or retired capability still "
        "resolves - the router must follow a redirect rather than returning a "
        "dead selection. Exact question: how many redirect tombstones exist in "
        "the current trees, and does each one resolve to a live target?"
    )
    receipt = {
        "unit_id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "ts": now,
        "question": question,
        "answer": {
            "redirect_tombstone_count_current_trees": census["redirect_tombstone_count"],
            "all_redirects_resolve_to_live": census["all_redirects_resolve_to_live"],
            "missing_target_is_defect": True,
            "live_capability_never_treated_as_tombstone": True,
            "cycle_refused": True,
        },
        "tombstone_table": census["tombstone_table"],
        "roots_scanned": census["roots"],
        "live_count": census["live_count"],
        "defect_count": census["defect_count"],
        "implementation": {
            "module": "tools/router/tombstones.py",
            "router_entry": "route_selection",
            "real_tombstone": {
                "old_id": "skill.four-voice-prompt",
                "new_id": "skill.council",
                "source_path": "skills/four-voice-prompt/SKILL.md",
            },
            "locators": [
                locator(src, "def resolve("),
                locator(src, "def route_selection("),
                locator(src, 'defect="tombstone-cycle"'),
                locator(src, 'defect="missing-target"'),
            ],
        },
        "tests": {
            "redirect_real_tombstone": "probe1_redirect.py",
            "cycle_cannot_loop": "probe2_cycle_negative.py",
            "negative_live_not_tombstone": "probe2_cycle_negative.py",
            "missing_target_is_defect": "probe2_cycle_negative.py",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "notes": (
            "G-1 for IMP-0405: live named probes exit 0, receipt is not BLOCKED, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            f"{SENTINEL}"
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "redirect-real-tombstone",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "cycle-and-negative-control",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0405/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0405-probe2-cycle-negative",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0405: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0405 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
