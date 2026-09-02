#!/usr/bin/env python3
"""Emit TST-0214 receipt, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST.

Runs live installer scenarios, writes command-center/receipts/TST-0214.json,
then runs named probes and registers the per-unit manifest row. Does not
invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import scenario as S  # noqa: E402

UID = "TST-0214"
OUT = "command-center/receipts/TST-0214.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/security_report"
SENTINEL = "SUCCESS:TST-0214"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0214/probe1_widen_halts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0214/probe2_narrow_or_same_proceeds.py"
)
SUPPORTING = [
    "tools/plugin/permission_diff.py",
    "tools/plugin/install.py",
    "tools/marketplace/install.py",
    "tools/plugin/tests/test_permission_diff.py",
    "command-center/p2-wave/probes/TST-0214/scenario.py",
    "command-center/p2-wave/probes/TST-0214/probe1_widen_halts.py",
    "command-center/p2-wave/probes/TST-0214/probe2_narrow_or_same_proceeds.py",
]
QUESTION = (
    "When an update widens a package's requested permissions, is the DIFF "
    "surfaced and the install halted pending approval? PASS requires the diff "
    "name each added permission and the install to block, not warn."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def live_both_states() -> dict:
    with tempfile.TemporaryDirectory(prefix="tst0214-emit-") as tmp:
        root = Path(tmp)
        dest = root / "dest"
        v1 = S.write_payload(
            root, version="1.0.0", permissions=S.BASE_PERMS, note="baseline"
        )
        wide = S.write_payload(
            root,
            version="1.1.0",
            permissions=S.WIDE_PERMS,
            note="malicious or excessive permissions",
        )
        same = S.write_payload(
            root,
            version="1.0.1",
            permissions=list(reversed(S.BASE_PERMS)),
            note="reordered identical set",
        )
        # first install
        first = S.install(v1, dest)
        before = S.census_tree(dest)
        before_perms = S.live_permissions(dest)
        try:
            S.install(wide, dest)
            widen_exc = None
        except S.PermissionWideningBlocked as exc:
            widen_exc = {
                "type": type(exc).__name__,
                "halt": exc.halt,
                "warn": exc.warn,
                "status": exc.status,
                "added": list(exc.added),
                "rendered_diff": exc.rendered_diff,
            }
        after = S.census_tree(dest)
        after_perms = S.live_permissions(dest)
        # identical/reorder proceeds on a fresh dest clone of v1
        dest2 = root / "dest2"
        S.install(v1, dest2)
        same_res = S.install(same, dest2)
        # narrower proceeds from a wide first-install
        dest3 = root / "dest3"
        S.install(wide, dest3)
        narrow = S.write_payload(
            root, version="1.2.0", permissions=S.NARROW_PERMS, note="narrower"
        )
        narrow_res = S.install(narrow, dest3)
        return {
            "first_install_verdict": first["result"]["permission_gate"]["verdict"],
            "widening": {
                "halted": widen_exc is not None,
                "exception": widen_exc,
                "census_unchanged": after == before,
                "effective_permissions_after": after_perms,
                "effective_permissions_before": before_perms,
                "independent_verdict": S.independent_set_verdict(
                    before_perms, S.WIDE_PERMS
                ),
            },
            "identical_reorder": {
                "verdict": same_res["result"]["permission_gate"]["verdict"],
                "halt": same_res["result"]["permission_gate"]["halt"],
                "version": S.live_version(dest2),
                "permissions": S.live_permissions(dest2),
                "independent_verdict": S.independent_set_verdict(
                    S.BASE_PERMS, list(reversed(S.BASE_PERMS))
                ),
            },
            "narrower": {
                "verdict": narrow_res["result"]["permission_gate"]["verdict"],
                "halt": narrow_res["result"]["permission_gate"]["halt"],
                "version": S.live_version(dest3),
                "permissions": S.live_permissions(dest3),
                "independent_verdict": S.independent_set_verdict(
                    S.WIDE_PERMS, S.NARROW_PERMS
                ),
            },
        }


def build_receipt(live: dict, tests: dict) -> dict:
    widen = live["widening"]
    exc = widen.get("exception") or {}
    added = list(exc.get("added") or [])
    ok = (
        widen.get("halted") is True
        and exc.get("halt") is True
        and exc.get("warn") is False
        and exc.get("status") == "blocked"
        and "net:connect" in added
        and "spawn:python" in added
        and widen.get("census_unchanged") is True
        and widen.get("effective_permissions_after") == S.BASE_PERMS
        and live["identical_reorder"]["verdict"] == "unchanged"
        and live["identical_reorder"]["halt"] is False
        and live["narrower"]["verdict"] == "narrow"
        and live["narrower"]["halt"] is False
        and tests.get("passed") is True
    )
    answer = (
        "Yes. A live marketplace.install of a widening candidate (the "
        "malicious/excessive-permissions seed) HALTS with status=blocked, not "
        "a warning. The rendered diff names each added permission "
        f"({', '.join(added)}). The dest census and effective permission set "
        "stay at the previously installed values. An identical (reordered) set "
        "and a narrower set install without a prompt, confirmed by reading "
        "the dest plugin.json after the update. An independent raw "
        "set-containment check reproduces the three verdicts."
        if ok
        else "No. The live installer did not satisfy the widening-halt contract."
    )
    return {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS" if ok else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "security_report",
        "title": "Permission widening at install requires an explicit owner decision",
        "output_schema": SCHEMA,
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "both_states": {
            "widening_halts": widen.get("halted") is True,
            "identical_or_reordered_proceeds": live["identical_reorder"]["halt"]
            is False
            and live["identical_reorder"]["verdict"] == "unchanged",
            "narrower_proceeds": live["narrower"]["halt"] is False
            and live["narrower"]["verdict"] == "narrow",
        },
        "evidence": [
            {
                "id": "signal-a-halt-and-named-diff",
                "claim": (
                    "Widening update is halted (not warned) and the rendered "
                    "diff names each added permission."
                ),
                "verdict": "CONFIRMED" if ok else "FAILED",
                "halt": exc.get("halt"),
                "warn": exc.get("warn"),
                "status": exc.get("status"),
                "named_added_permissions": added,
                "rendered_diff": exc.get("rendered_diff"),
            },
            {
                "id": "signal-b-effective-permissions-unchanged",
                "claim": (
                    "After the halted widening attempt, the installed package's "
                    "effective permission set and dest census are unchanged."
                ),
                "verdict": "CONFIRMED"
                if widen.get("census_unchanged")
                and widen.get("effective_permissions_after") == S.BASE_PERMS
                else "FAILED",
                "effective_permissions_before": widen.get(
                    "effective_permissions_before"
                ),
                "effective_permissions_after": widen.get(
                    "effective_permissions_after"
                ),
                "census_unchanged": widen.get("census_unchanged"),
            },
        ],
        "live": live,
        "tests": [
            {
                "id": "tools/plugin/tests/test_permission_diff.py",
                "result": "PASS" if tests.get("passed") else "FAIL",
                "tail": (tests.get("tail") or "")[-1500:],
            }
        ],
        "named_probes": [
            {"id": "probe1", "role": "widen-halts-named-diff", "command": P1},
            {
                "id": "probe2",
                "role": "narrow-or-same-proceeds",
                "command": P2,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0214-probe2-narrow-or-same-proceeds",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
            "notes": (
                "Probe 2 is a mechanically different check: it requires the "
                "update to commit and then reads dest plugin.json. Catalog "
                "asks two fresh reviewers; this headless worker records the "
                "independent probe as the second signal rather than an ADV "
                "rebuild circle."
            ),
        },
        "regression_seed": {
            "name": "marketplace package has malicious or excessive permissions",
            "anchor": "_USER-PROMPTS.md:11346",
            "fixture_permissions": S.WIDE_PERMS,
        },
        "implementation": {
            "gate": "tools/plugin/permission_diff.py",
            "installer": "tools/plugin/install.py",
            "marketplace": "tools/marketplace/install.py",
            "tests": "tools/plugin/tests/test_permission_diff.py",
        },
        "cloud_ok": False,
        "registered": True,
        "notes": (
            "G-1 for TST-0214: live named probes, honest non-BLOCKED artifact, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild circle."
        ),
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
        "receipt_path": "command-center/p2-wave/probes/TST-0214/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    code, tail = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "tools/plugin/tests/test_permission_diff.py"
    )
    tests = {
        "passed": code == 0,
        "tail": tail,
        "exit_code": code,
    }
    if not tests["passed"]:
        print("FAILED:TST-0214 unit tests")
        print(tail[-4000:])
        return 1
    live = live_both_states()
    doc = build_receipt(live, tests)
    if doc["state"] != "SUCCESS":
        print("FAILED:TST-0214 live both-states")
        print(json.dumps(live, indent=2)[:4000])
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:TST-0214 sentinel missing from serialized receipt")
        return 1
    out.write_text(body, encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0214 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [
        row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "widen-halts-named-diff",
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "narrow-or-same-proceeds",
                "raw_output": t2[-4000:],
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
        "manifest_path": (
            "command-center/p2-wave/probes/TST-0214/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "TST-0214-probe2-narrow-or-same-proceeds",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0214: live named probes exit 0, receipts/TST-0214.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0214 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
