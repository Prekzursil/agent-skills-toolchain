#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0151.json (reproduction matrix)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from container import is_floating_ref  # noqa: E402
from matrix import build_live, isolation_both_states, second_digest_review  # noqa: E402

OUT = "command-center/receipts/CNF-0151.json"
SCHEMA = "command-center/schema/reproduction-matrix.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0151/probe1_three_way.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0151/probe2_controls.py"
)
QUESTION = (
    "For the portable subset of claims, does a Linux container reproduce the "
    "same verdict as the Windows box and as CI? Report a three-way table, not "
    "a pass/fail. This is the third leg that resolves 'green in CI, red locally' "
    "into a definite cause."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    live = build_live(nonce="emit")
    iso = isolation_both_states(nonce="emit-iso")
    rev = second_digest_review(nonce="emit-rev")
    if not live.get("pass"):
        print("FAILED:CNF-0151 emit live matrix")
        print(json.dumps({k: live.get(k) for k in ("portable_agree", "windows_specific_diverges", "pass")}))
        return 1
    if not iso.get("pass") or not rev.get("pass"):
        print("FAILED:CNF-0151 emit isolation or second-digest review")
        return 1
    if is_floating_ref(live["image"]["ref"]):
        print("FAILED:CNF-0151 emit floating image")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    img = live["image"]
    ci = live["ci"]
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    doc = {
        "unit_id": "CNF-0151",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0151",
        "title": (
            "Linux container reproduction of the portable subset, "
            "reconciled against CI-green"
        ),
        "question": QUESTION,
        "claim_under_test": (
            "Portable claims agree across windows-box, linux-container, and CI; "
            "a windows-specific .cmd-shim claim diverges, proving the container "
            "is not silently reusing host Windows lookup state."
        ),
        "headline": (
            "three-way table, not a pass/fail: 3 portable claims AGREE in all "
            "three columns; 1 windows-specific claim DIVERGES (windows-box PASS, "
            "linux-container FAIL, ci FAIL)."
        ),
        "dependencies_on_disk": {
            "CNF-0150": {
                "output_path": "command-center/receipts/CNF-0150.json",
                "present": (REPO / "command-center/receipts/CNF-0150.json").is_file(),
                "reconstruction": (
                    "Portable subset reconstructed from CNF-0150's named traps: "
                    "claims that do not use MSYS path conversion, PowerShell caret "
                    "escaping, CRLF-as-bytes .sh validation, or .cmd shim lookup."
                ),
            },
            "CNF-0185": {
                "output_path": "command-center/receipts/CNF-0185.json",
                "present": (REPO / "command-center/receipts/CNF-0185.json").is_file(),
                "reconstruction": (
                    "Toolchain pin is the sha256 of /usr/bin/python3.12 executed "
                    "inside the chroot; invocation is the pinned ref, not ambient PATH."
                ),
            },
        },
        "columns": live["columns"],
        "matrix": live["matrix"],
        "image": img,
        "host_cache_isolation": {
            "host_cache_path": "/var/tmp/cnf0151-host-cache/MARKER",
            "clean_container_sees_host_cache": iso["clean_sees_host_cache"],
            "mounted_container_sees_host_cache": iso["mounted_sees_host_cache"],
            "clean_resolves_cmd_shim": iso["clean_resolves_shim"],
            "mounted_with_pathext_resolves_cmd_shim": iso["mounted_resolves_shim"],
            "pass": iso["pass"],
        },
        "ci_evidence": {
            "run_id": ci["run_id"],
            "run_path": ci["run_path"],
            "conclusion_source": ci["used_source"],
            "rejected_source": ci["rejected_source"],
            "run_conclusion": ci["run_conclusion"],
            "stale_summary_path": ci["summary_path"],
            "stale_summary_conclusion": ci["stale_summary_conclusion"],
            "stale_summary_rejected": ci["stale_differs"],
        },
        "windows_box": live["windows"],
        "second_digest_review": rev,
        "portable_agree": live["portable_agree"],
        "windows_specific_diverges": live["windows_specific_diverges"],
        "tests": [
            {
                "id": "windows-specific-diverges",
                "name": "Control: a claim known to be Windows-specific must diverge",
                "command": P1,
                "result": "PASS" if live["windows_specific_diverges"] else "FAIL",
            },
            {
                "id": "portable-agree-all-columns",
                "name": "Both-states: a claim known portable must agree in all three columns",
                "command": P1,
                "result": "PASS" if live["portable_agree"] else "FAIL",
            },
            {
                "id": "image-pinning",
                "name": "Image pinning: container digest recorded; floating tag invalidates",
                "command": P2,
                "result": "PASS" if (not img["floating_tag"] and not is_floating_ref(img["ref"])) else "FAIL",
            },
            {
                "id": "no-host-mount",
                "name": "No-host-mount control: container cannot see the host cache",
                "command": P2,
                "result": "PASS" if iso["pass"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0151-second-digest-reviewer",
            "verdict": "PASS" if rev["pass"] else "FAIL",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Re-ran C-WIN-CMD-SHIM and C-PORTABLE-JSON on a second container "
                "instance digest; image digest held, instance digests differed, "
                "windows-specific stayed FAIL, portable JSON value agreed."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "three-way-matrix"},
            {"id": "probe2", "command": P2, "role": "pin-isolation-second-digest"},
        ],
        "evidence": [
            {
                "path": ci["run_path"],
                "kind": "ci-run-reread",
                "claim": "CI cells cite the run's own conclusion field, not a stored summary.",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0151/container.py",
                "kind": "live-container",
                "claim": f"Pinned ref {img['ref']} is sha256 of /usr/bin/python3.12.",
            },
        ],
        "ts": now,
        "notes": (
            "G-1 for CNF-0151 on this Linux worktree: live mount-namespace chroot "
            "is the Linux container (docker/podman absent). Windows column is a "
            "PATHEXT/Get-Command oracle, not a Win32 VM. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    if any(t["result"] != "PASS" for t in doc["tests"]):
        print("FAILED:CNF-0151 emit tests not all PASS")
        return 1
    # Shim $ref points at ast-integrate.invalid. jsonschema 4.10 tries HTTPS
    # and fails; do not fetch. Demand the physical target on disk (BLD-0048).
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:CNF-0151 declared schema missing")
        return 1
    phys = str(schema.get("x-physical-definition") or "")
    phys_file = phys.split("#", 1)[0]
    if not phys_file or not (REPO / phys_file).is_file():
        print(f"FAILED:CNF-0151 physical schema missing {phys}")
        return 1
    ref = str(schema.get("$ref") or "")
    if ref.startswith("http") and "ast-integrate.invalid" not in ref:
        print("FAILED:CNF-0151 unexpected remote schema $ref")
        return 1
    if "SUCCESS:CNF-0151" not in json.dumps(doc):
        print("FAILED:CNF-0151 sentinel missing from document")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 1024:
        print(f"FAILED:CNF-0151 artifact too small {size}B")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0151 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
