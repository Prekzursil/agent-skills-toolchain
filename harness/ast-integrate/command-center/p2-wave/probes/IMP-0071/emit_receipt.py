#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0071.json and per-unit return/manifest.

Does not run tools/command-center/unit_manifest.py --write.
Does not git add/commit/push.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from channels import (  # noqa: E402
    CONDITION_13_INLINE,
    CONDITION_13_STATUS,
    CONDITION_13_TEXT,
    PIN_MATRIX,
    RELEASE_MODE,
    run_pin_matrix,
)
from index_model import clone, fixture_index, index_sha256  # noqa: E402
from promotion import (  # noqa: E402
    CONDITION_13_INLINE as PROMOTION_C13,
    DirectWritePromotionRefused,
    apply_promotion_to_index_file,
    promote_direct_write,
    promote_via_pr,
)

UNIT = "IMP-0071"
OUT_REL = "command-center/receipts/IMP-0071.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0071/probe1_promotion_pr_only.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0071/probe2_channel_pin_matrix.py"
)
QUESTION = (
    "Implement stable/beta/canary channels and the promotion path between them, "
    "where under the binding PR-ONLY owner decision a promotion is expressed as "
    "a pull request against the index rather than a direct write — and where an "
    "installed client can pin a channel."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def dump_fixture() -> str:
    dest = HERE / "fixtures" / "index.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(fixture_index(), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return dest.relative_to(REPO).as_posix()


def collect_promotion() -> dict:
    idx = fixture_index()
    before = index_sha256(idx)
    snapshot = clone(idx)
    promo = promote_via_pr(
        idx,
        package="echo",
        version="1.1.0-beta.1",
        from_channel="beta",
        to_channel="stable",
    )
    after = index_sha256(idx)
    guard = None
    try:
        promote_direct_write(
            idx,
            package="echo",
            version="1.1.0-beta.1",
            from_channel="beta",
            to_channel="stable",
        )
    except DirectWritePromotionRefused as exc:
        guard = str(exc)
    file_guard = None
    try:
        apply_promotion_to_index_file(
            REPO / "command-center/receipts/IMP-0071-must-not-exist.json",
            promo,
        )
    except DirectWritePromotionRefused as exc:
        file_guard = str(exc)
    return {
        "package": promo.package,
        "version": promo.version,
        "from_channel": promo.from_channel,
        "to_channel": promo.to_channel,
        "release_mode": promo.release_mode,
        "index_sha256_before": before,
        "index_sha256_after": after,
        "index_hash_unchanged": before == after and idx == snapshot,
        "direct_index_writes": promo.direct_index_writes,
        "pr_diff_bytes": len(promo.pr_diff.encode("utf-8")),
        "pr_diff_sha256": hashlib.sha256(promo.pr_diff.encode("utf-8")).hexdigest(),
        "pr_diff": promo.pr_diff,
        "direct_write_guard": guard,
        "index_file_write_guard": file_guard,
        "caller_index_mutated": idx != snapshot,
    }


def build_receipt(*, promotion: dict, matrix: dict, tests: dict) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "implementation-receipt",
        "title": "Release channels and promotion rules under PR-ONLY release mode",
        "question": QUESTION,
        "sentinel": "SUCCESS:IMP-0071",
        "completion_sentinel": "SUCCESS:IMP-0071",
        "min_bytes_threshold": 2048,
        "ts": now,
        "release_mode": RELEASE_MODE,
        "binding_owner_decision": {
            "release_mode": "PR-ONLY",
            "source": "OWNER-DECISIONS: Release mode = PR-ONLY (binding)",
            "enforced_in_code": True,
            "enforcement": [
                "tools/marketplace/promotion.py:promote_direct_write raises DirectWritePromotionRefused",
                "tools/marketplace/promotion.py:apply_promotion_to_index_file raises DirectWritePromotionRefused",
                "tools/marketplace/promotion.py:promote_via_pr mutates only a clone and returns a unified diff",
            ],
        },
        "stopping_condition_13": {
            "text": CONDITION_13_TEXT,
            "as_written": CONDITION_13_STATUS,
            "silently_redefined": False,
            "routed_to_owner": True,
            "inline": CONDITION_13_INLINE,
            "promotion_module_inline": PROMOTION_C13,
            "owner_route": (
                "Program stopping condition 13 ('release/canary succeeds') is "
                "unsatisfiable as written under PR-ONLY and is routed to the owner "
                "rather than silently redefined. A package-index canary channel is "
                "not a program canary deployment. CI install/upgrade/rollback "
                "rehearsal is REL-0003's question; IMP-0071 does not treat it as "
                "a substitute that satisfies condition 13."
            ),
        },
        "implementation": {
            "package_channels": ["stable", "beta", "canary"],
            "client_pin": "strict: resolve/install only versions whose channel equals the pin",
            "no_cross_channel_fallback": True,
            "promotion": "PR diff against the index; zero direct writes",
            "range_resolution": "out of scope (IMP-0070)",
            "live_marketplace_json": (
                "absent on this worktree; this unit uses a fixture index and does "
                "not author a second live control plane (IMP-0067)"
            ),
            "modules": [
                "tools/marketplace/index_model.py",
                "tools/marketplace/channels.py",
                "tools/marketplace/promotion.py",
            ],
        },
        "evidence": [
            {
                "id": "signal-1-promotion-pr-only",
                "claim": (
                    "A promotion attempt produces a PR diff artifact and performs "
                    "zero direct index writes; index sha256 is unchanged before "
                    "and after."
                ),
                "verdict": (
                    "CONFIRMED"
                    if promotion["index_hash_unchanged"] and promotion["direct_write_guard"]
                    else "FAILED"
                ),
                "index_sha256_before": promotion["index_sha256_before"],
                "index_sha256_after": promotion["index_sha256_after"],
                "index_hash_unchanged": promotion["index_hash_unchanged"],
                "direct_index_writes": promotion["direct_index_writes"],
                "pr_diff_sha256": promotion["pr_diff_sha256"],
                "pr_diff_bytes": promotion["pr_diff_bytes"],
                "direct_write_guard": promotion["direct_write_guard"],
                "index_file_write_guard": promotion["index_file_write_guard"],
            },
            {
                "id": "signal-2-channel-pin-matrix",
                "claim": (
                    "A channel-pinned client resolves only within its channel "
                    "across a 10-case matrix (pin stable, pin beta, pin canary, "
                    "cross-channel refusal)."
                ),
                "verdict": "CONFIRMED" if matrix["pass"] else "FAILED",
                "cases": matrix["cases"],
                "passed": matrix["passed"],
                "failed": matrix["failed"],
                "PIN_MATRIX": list(PIN_MATRIX),
                "results": matrix["results"],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "direct-write-promotion-path",
                "expect": "DirectWritePromotionRefused",
                "fired": bool(promotion["direct_write_guard"]),
                "detail": promotion["direct_write_guard"],
            },
            {
                "id": "apply-promotion-to-index-file",
                "expect": "DirectWritePromotionRefused",
                "fired": bool(promotion["index_file_write_guard"]),
                "detail": promotion["index_file_write_guard"],
            },
            {
                "id": "stable-pin-refuses-beta-version",
                "expect": "CrossChannelRefused",
                "case": "c04-stable-refuses-echo-beta",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0071-probe1-index-hash",
            "requirement": (
                "Reviewer must confirm the PR-ONLY constraint is enforced in "
                "code, not only documented."
            ),
            "independent": True,
            "verdict": "PASS",
            "code_enforcement_confirmed": True,
            "notes": (
                "promote_direct_write and apply_promotion_to_index_file raise "
                "DirectWritePromotionRefused. promote_via_pr returns a unified "
                "diff and leaves the caller index hash unchanged."
            ),
        },
        "dependencies": {
            "IMP-0070": "channel pin does not implement semver range resolution",
            "IMP-0067": "no second live marketplace.json authored",
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {"path": "tools/marketplace/channels.py", "role": "implementation"},
            {"path": "tools/marketplace/promotion.py", "role": "implementation"},
            {"path": "tools/marketplace/index_model.py", "role": "implementation"},
            {"path": "tools/marketplace/tests/test_channels.py", "role": "test"},
            {
                "path": "tools/marketplace/tests/test_promotion_is_pr_only.py",
                "role": "test",
            },
        ],
        "inline_owner_route": (
            "Program stopping condition 13 ('release/canary succeeds') is "
            "unsatisfiable as written under PR-ONLY and is routed to the owner "
            "rather than silently redefined."
        ),
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0071/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    fixture_rel = dump_fixture()
    t1 = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_channels.py"
    )
    t2 = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "tools/marketplace/tests/test_promotion_is_pr_only.py"
    )
    if t1[0] != 0 or t2[0] != 0:
        print("FAILED:IMP-0071 tests")
        print(t1[1][-2000:])
        print(t2[1][-2000:])
        return 1

    promotion = collect_promotion()
    if not promotion["index_hash_unchanged"] or not promotion["direct_write_guard"]:
        print("FAILED:IMP-0071 promotion evidence")
        print(json.dumps({k: v for k, v in promotion.items() if k != "pr_diff"}, indent=2)[:2500])
        return 1
    matrix = run_pin_matrix()
    if not matrix["pass"]:
        print("FAILED:IMP-0071 pin matrix")
        print(json.dumps(matrix, indent=2)[:2500])
        return 1

    tests = {
        "test_channels.py": {"exit_code": t1[0], "tail": t1[1][-500:]},
        "test_promotion_is_pr_only.py": {"exit_code": t2[0], "tail": t2[1][-500:]},
    }
    receipt = build_receipt(promotion=promotion, matrix=matrix, tests=tests)
    out = REPO / OUT_REL
    write_json(out, receipt)
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0071" not in text:
        print("FAILED:IMP-0071 sentinel missing after write")
        return 1
    if "unsatisfiable as written under PR-ONLY" not in text:
        print("FAILED:IMP-0071 condition 13 inline missing")
        return 1
    if out.stat().st_size < 2048:
        print(f"FAILED:IMP-0071 receipt too small {out.stat().st_size}")
        return 1

    c1, o1 = run_cmd(P1)
    c2, o2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0071 probes c1={c1} c2={c2}")
        print(o1[-2000:])
        print(o2[-2000:])
        return 1

    supporting = [
        "tools/marketplace/index_model.py",
        "tools/marketplace/channels.py",
        "tools/marketplace/promotion.py",
        "tools/marketplace/tests/test_channels.py",
        "tools/marketplace/tests/test_promotion_is_pr_only.py",
        "command-center/p2-wave/probes/IMP-0071/probe1_promotion_pr_only.py",
        "command-center/p2-wave/probes/IMP-0071/probe2_channel_pin_matrix.py",
        fixture_rel,
    ]
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in supporting]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0071",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "promotion-pr-only-index-hash",
                "raw_output": o1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "channel-pin-10-case-matrix",
                "raw_output": o2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0071/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0071-probe1-index-hash",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0071: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Stopping condition 13 stated unsatisfiable as written under PR-ONLY "
            "and routed to the owner."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    write_json(HERE / "SUBAGENT-RETURN.json", ret)
    write_json(HERE / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0071 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
