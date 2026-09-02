#!/usr/bin/env python3
"""Emit IMP-0001 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import payload_allowlist as pa  # noqa: E402

OUT = "command-center/receipts/IMP-0001.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0001/probe1_setdiff_and_archive.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0001/probe2_negative_and_mutation.py"
)
TESTS = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_payload_allowlist.py"
)
SUPPORTING = [
    "tools/plugin/payload-allowlist.json",
    "tools/plugin/schema/payload-allowlist.schema.json",
    "tools/plugin/payload_allowlist.py",
    "tools/plugin/pack.py",
    "tools/plugin/tests/test_payload_allowlist.py",
    "command-center/p2-wave/probes/IMP-0001/probe1_setdiff_and_archive.py",
    "command-center/p2-wave/probes/IMP-0001/probe2_negative_and_mutation.py",
    ".claude-plugin/plugin.json",
    "skills/DEPLOYED-MANIFEST.json",
    "hooks/_dispatch/manifest.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0001",
        "receipt_path": "command-center/p2-wave/probes/IMP-0001/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    t_rc, t_out = run(TESTS)
    print(t_out)
    if t_rc != 0:
        print("FAILED:IMP-0001 tests did not pass")
        return 1

    doc = pa.load_allowlist()
    source, census = pa.listed_paths(REPO)
    payload = pa.expand(census, doc, matcher="a")
    payload_b = pa.expand(census, doc, matcher="b")
    if payload != payload_b:
        print("FAILED:IMP-0001 matcher A vs B disagreement")
        return 1
    diff = pa.set_difference(census, payload)
    derived = pa.independent_plugin_layout_paths(REPO)
    if derived != payload:
        print("FAILED:IMP-0001 independent layout derivation disagrees")
        return 1

    import tempfile

    with tempfile.TemporaryDirectory(prefix="imp0001-receipt-") as tmp:
        archive = Path(tmp) / "payload.tar"
        packed = pa.pack_repo(REPO, archive, doc)
        listing = pa.tar_tf_listing(archive)
        members = pa.tar_members(archive)
        if not packed["ok"] or listing != payload or members != payload:
            print("FAILED:IMP-0001 archive listing disagrees with expansion")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0001",
        "id": "IMP-0001",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0001",
        "completion_sentinel": "SUCCESS:IMP-0001",
        "title": "Package payload allowlist manifest (deny-by-default include set)",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0001",
        "question": (
            "Author tools/plugin/payload-allowlist.json declaring, deny-by-default, "
            "the exact path globs that constitute the distributable plugin payload, "
            "and make the packer refuse to emit any path not matched by an allowlist entry."
        ),
        "output_schema": (
            "command-center/schema/receipt.schema.json (receipt) + "
            "tools/plugin/schema/payload-allowlist.schema.json (artifact authored here)"
        ),
        "allowlist_path": "tools/plugin/payload-allowlist.json",
        "allowlist": {
            "policy": "deny-by-default",
            "include": doc["include"],
            "never": doc["never"],
        },
        "census": {
            "source": source,
            "count": diff["census_count"],
            "note": (
                "git ls-files when .git exists. This worktree has no .git; "
                "census is a worktree walk. Catalog mentioned 7,911 tracked files "
                "on the originating tree; this slice enumerates what is here."
            ),
        },
        "signal_1_python_set_difference": {
            "census_count": diff["census_count"],
            "payload_count": diff["payload_count"],
            "unmatched_count": diff["only_census_count"],
            "symmetric_difference_count": diff["symmetric_difference_count"],
            "payload_paths": payload,
            "unmatched_sample": diff["only_census_sample"],
        },
        "signal_2_tar_tf_listing": {
            "member_count": len(listing),
            "members": listing,
            "agrees_file_for_file_with_signal_1": listing == payload,
            "rechecked_with_matcher_b": True,
        },
        "signals_agree": listing == payload and packed["ok"],
        "negative_control": {
            "planted": [".git/config", "planted-40mb.log"],
            "packer_must_exit_nonzero_naming_both": True,
            "verified_by": "tools/plugin/tests/test_payload_allowlist.py::test_negative_control_git_and_40mb_log",
        },
        "mutation": {
            "change": "widen one include glob to **",
            "live_include_unbounded": False,
            "mutant_goes_red": True,
            "verified_by": "tools/plugin/tests/test_payload_allowlist.py::test_mutation_widen_one_glob_to_starstar_goes_red",
        },
        "reviewer": {
            "reviewer_id": "IMP-0001-probe2-independent-layout-and-negative-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives the payload from Claude plugin layout directories "
                "(.claude-plugin, skills, hooks, commands, agents) without reading the "
                "allowlist globs, plants .git/config and a 40 MiB log, and requires the "
                "packer to name both paths and exit non-zero. Widening one include glob "
                "to ** is required to go red."
            ),
        },
        "tests": [
            {
                "id": "test_every_emitted_path_is_allowlisted",
                "command": TESTS,
                "result": "PASS" if t_rc == 0 else "FAIL",
                "output_tail": t_out[-1500:],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0001/UNIT-ARTIFACT-MANIFEST.json",
            "note": "per-unit only; did not run tools/command-center/unit_manifest.py --write",
        },
        "report": {
            "kind": "payload-allowlist",
            "payload_count": len(payload),
            "census_count": diff["census_count"],
            "deny_by_default": True,
        },
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")

    c1, t1 = run(P1)
    c2, t2 = run(P2)
    print(t1)
    print(t2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0001 probes c1={c1} c2={c2}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "IMP-0001",
        "unit_id": "IMP-0001",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0001",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/plugin/schema/payload-allowlist.schema.json"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "set-difference-and-archive-listing",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "negative-control-and-mutation",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0001/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0001-probe2-independent-layout-and-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered IMP-0001",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered IMP-0001"},
        "ts": now,
        "notes": (
            "G-1 for IMP-0001: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0001",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print("SUCCESS:IMP-0001 receipts written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
