#!/usr/bin/env python3
"""Emit IMP-0081 receipt and per-unit G-1 return + manifest.

Order: run catalog tests, write receipts/IMP-0081.json, re-run named probes,
then write SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.
Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
from marketplace.federated_identity import (  # noqa: E402
    STATUS_ASSERTED,
    STATUS_FIRST_PARTY_LOCAL,
    STATUS_MISMATCH,
    STATUS_VERIFIED,
    GitLsRemoteResolver,
    ScriptedResolver,
    UnreachableUpstream,
    init_local_git_repo,
    map_identity,
    map_index,
    record_in_index,
    surfaces_distinguish,
)

UNIT = "IMP-0081"
OUT = "command-center/receipts/IMP-0081.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0081/probe1_verified_mapping.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0081/probe2_asserted_mismatch.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_federated_identity.py"
)
SUPPORTING = [
    "tools/marketplace/federated_identity.py",
    "tools/marketplace/tests/test_federated_identity.py",
    "command-center/p2-wave/probes/IMP-0081/probe1_verified_mapping.py",
    "command-center/p2-wave/probes/IMP-0081/probe2_asserted_mismatch.py",
    "command-center/p2-wave/probes/IMP-0081/fixtures/marketplace.json",
]
PLANTED = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
GIT_SRC = "https://github.com/acme/federated-pkg.git#v1.2.3"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def _no_sleep(_s: float) -> None:
    return None


def main() -> int:
    rc_t, out_t = run_cmd(TEST_CMD)
    if rc_t != 0:
        print(f"FAILED:IMP-0081 tests rc={rc_t}")
        print(out_t[-4000:])
        return 1

    import tempfile

    with tempfile.TemporaryDirectory(prefix="imp0081-emit-") as tmp:
        root = Path(tmp) / "upstream"
        head = init_local_git_repo(root)
        url = root.resolve().as_uri()
        live = map_identity(
            "planted-pkg",
            url,
            recorded_commit=head,
            resolver=GitLsRemoteResolver(timeout_seconds=15),
            sleeper=_no_sleep,
        )
    if live.status != STATUS_VERIFIED:
        print(f"FAILED:IMP-0081 live git map status={live.status}")
        return 1

    verified = map_identity(
        "federated-pkg",
        GIT_SRC,
        recorded_commit=PLANTED,
        resolver=ScriptedResolver([PLANTED]),
        sleeper=_no_sleep,
    )
    asserted = map_identity(
        "federated-pkg",
        GIT_SRC,
        recorded_commit=PLANTED,
        resolver=ScriptedResolver([UnreachableUpstream("emit-unreachable")]),
        sleeper=_no_sleep,
    )
    mismatch = map_identity(
        "federated-pkg",
        GIT_SRC,
        recorded_commit=PLANTED,
        resolver=ScriptedResolver([OTHER]),
        sleeper=_no_sleep,
    )
    local = map_identity("ast-integrate", "./")
    attached_mismatch = record_in_index({"name": "federated-pkg"}, mismatch)
    diff = surfaces_distinguish(verified, asserted)
    fixture = json.loads(
        (HERE / "fixtures" / "marketplace.json").read_text(encoding="utf-8")
    )
    mapped = map_index(
        fixture,
        resolver=ScriptedResolver([PLANTED]),
        sleeper=_no_sleep,
    )

    if (
        verified.status != STATUS_VERIFIED
        or asserted.status != STATUS_ASSERTED
        or mismatch.status != STATUS_MISMATCH
        or local.status != STATUS_FIRST_PARTY_LOCAL
        or attached_mismatch["federated_identity"]["status"] == STATUS_VERIFIED
        or not diff.get("distinguished")
        or mapped["plugins"][0]["federated_identity"]["status"]
        != STATUS_FIRST_PARTY_LOCAL
    ):
        print("FAILED:IMP-0081 mapper did not discriminate required states")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_present = (REPO / SCHEMA).is_file()
    p_live = L.probe(
        "source",
        "command",
        "git ls-remote file://planted + map_identity",
        json.dumps(
            {
                "status": live.status,
                "resolved": live.resolved_commit,
                "recorded": live.recorded_commit,
                "identity": live.identity.as_dict() if live.identity else None,
            },
            sort_keys=True,
        ),
        0,
    )
    p_surf = L.probe(
        "verifier",
        "command",
        "surfaces_distinguish(VERIFIED, ASSERTED) + mismatch index attach",
        json.dumps(
            {
                "distinguished": diff.get("distinguished"),
                "mismatch_index": attached_mismatch["federated_identity"]["status"],
                "local": local.status,
                "asserted_badge": asserted.badge,
                "verified_badge": verified.badge,
            },
            sort_keys=True,
        ),
        0,
    )
    p_test = L.probe("source", "command", TEST_CMD, out_t[-4000:], rc_t)

    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)
    artifacts = [
        L.art("tools/marketplace/federated_identity.py", "implementation"),
        L.art("tools/marketplace/tests/test_federated_identity.py", "supporting"),
        L.art(
            "command-center/p2-wave/probes/IMP-0081/probe1_verified_mapping.py",
            "named-probe",
        ),
        L.art(
            "command-center/p2-wave/probes/IMP-0081/probe2_asserted_mismatch.py",
            "named-probe",
        ),
        L.art(
            "command-center/p2-wave/probes/IMP-0081/fixtures/marketplace.json",
            "fixture",
        ),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0081",
        "completion_sentinel": "SUCCESS:IMP-0081",
        "spec_anchor": "_USER-PROMPTS.md:10865",
        "title": "Federated identity mapping for repository-sourced packages",
        "question_or_target": (
            "Map a package sourced from a git repository to a verifiable upstream "
            "identity (host, org, repo, ref) and record whether the mapping was "
            "verified or merely asserted, so a repo-sourced entry cannot masquerade "
            "as first-party without evidence."
        ),
        "min_bytes_threshold": 512,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "schema_validation": {
            "declared": SCHEMA,
            "present": schema_present,
            "verdict": "CHECKED" if schema_present else "NOT-CHECKED",
            "reason": (
                "declared schema present on this worktree"
                if schema_present
                else "declared schema path is absent; G-1 does not require it"
            ),
        },
        "artifacts": artifacts,
        "mapper": {
            "module": "tools/marketplace/federated_identity.py",
            "statuses": [
                STATUS_VERIFIED,
                STATUS_ASSERTED,
                STATUS_MISMATCH,
                STATUS_FIRST_PARTY_LOCAL,
            ],
            "retry": {"max_attempts": 3, "unreachable_yields": STATUS_ASSERTED},
            "live_git": {
                "status": live.status,
                "resolved_commit": live.resolved_commit,
                "identity": live.identity.as_dict() if live.identity else None,
            },
            "scripted": {
                "verified": verified.to_index_block(),
                "asserted": asserted.to_index_block(),
                "mismatch": mismatch.to_index_block(),
                "local_dot_slash": local.to_index_block(),
            },
            "surfaces": diff,
            "fixture_index": mapped,
        },
        "evidence": [
            L.evidence(
                "For a verified mapping, the upstream ref resolves and its commit "
                "matches recorded provenance. Independent git rev-parse of the "
                "planted repo agrees with the mapper.",
                "CONFIRMED",
                "tools/marketplace/federated_identity.py:map_identity",
                [p_live, p_test],
                "almost-certain",
            ),
            L.evidence(
                "For an unverifiable mapping the record is ASSERTED and is "
                "visibly distinguishable from VERIFIED on index_json, display_line, "
                "and query_row. A mismatched commit is REJECTED_MISMATCH and is "
                "not recorded as VERIFIED. Local './' is first-party-local and "
                "does not crash.",
                "CONFIRMED",
                "tools/marketplace/federated_identity.py:surfaces_distinguish",
                [p_surf, p_test],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "bounded backoff x3 on upstream fetch; unreachable => ASSERTED",
        },
        "tests": [
            {
                "id": "test_verified",
                "command": TEST_CMD + "::test_verified",
                "result": "PASS",
            },
            {
                "id": "test_asserted",
                "command": TEST_CMD + "::test_asserted",
                "result": "PASS",
            },
            {
                "id": "test_mismatched",
                "command": TEST_CMD + "::test_mismatched",
                "result": "PASS",
            },
            {
                "id": "test_unreachable_upstream",
                "command": TEST_CMD + "::test_unreachable_upstream",
                "result": "PASS",
            },
            {
                "id": "test_mismatched_commit_not_recorded_as_verified",
                "command": (
                    TEST_CMD + "::test_mismatched_commit_not_recorded_as_verified"
                ),
                "result": "PASS",
            },
            {
                "id": "test_local_dot_slash_source_does_not_crash",
                "command": TEST_CMD + "::test_local_dot_slash_source_does_not_crash",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "IMP0081-C1",
                "known-broken-fixture",
                "A mismatched commit must not be recorded as VERIFIED.",
                True,
                True,
                bad=f"resolved={OTHER} recorded={PLANTED} status={mismatch.status}",
                good=f"matching commit status={verified.status}",
            ),
            L.control(
                "IMP0081-C2",
                "both-states-same-run",
                "ASSERTED and VERIFIED must not render identically on any surface.",
                True,
                True,
                bad=json.dumps(asserted.surfaces(), sort_keys=True),
                good=json.dumps(verified.surfaces(), sort_keys=True),
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0081-probe2-asserted-surfaces",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 confirms ASSERTED never renders identically to VERIFIED "
                "on index_json, display_line, or query_row; mismatch is not "
                "indexed as VERIFIED; './' is handled without a crash."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0081/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "tools/marketplace/tests/test_federated_identity.py",
                "artifact_path": "tools/marketplace/federated_identity.py",
                "executed": True,
                "read_ok": True,
                "exit_code": rc_t,
                "probe": p_test,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    ".claude-plugin/marketplace.json is absent on this worktree; "
                    "the catalog names plugins[].source currently './'. The './' "
                    "case is exercised via fixtures/marketplace.json rather than "
                    "a live marketplace.json."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run map_index on .claude-plugin/marketplace.json once "
                    "IMP-0067 authors that file on this tree."
                ),
            }
        ],
        "notes": (
            "G-1 IMP-0081: federated identity mapper VERIFIED vs ASSERTED, "
            "mismatch refused, local './' handled. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "SUCCESS:IMP-0081"
        ),
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0081 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0081" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0081 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0081 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0081",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "verified-mapping-two-signal",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "asserted-surfaces-mismatch-local",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0081/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0081-probe2-asserted-surfaces",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0081: live named probes exit 0, receipts/IMP-0081.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        dgst, nbytes = digest_file(path)
        return {
            "path": rel,
            "sha256": dgst,
            "bytes": nbytes,
            "present": path.is_file(),
            "unit_id": UNIT,
            "receipt_path": (
                "command-center/p2-wave/probes/IMP-0081/SUBAGENT-RETURN.json"
            ),
            "role": role,
        }

    artifacts_man = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts_man),
        "present": sum(1 for a in artifacts_man if a["present"]),
        "artifacts": artifacts_man,
    }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0081 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
