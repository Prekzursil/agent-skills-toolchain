"""Catalog controls for BLD-0016 plus the ten-mapping body review."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from classify import ABSENT, DIR_INCOMPLETE, EMPTY, PRESENT, classify_path, unix_stat_reprobe
from join import JoinResult, Requirement, TestRec, apply_registry, discover_tests, join, load_registry_maps

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FX = HERE / "fixtures"
REVIEW_REQS = tuple(f"REQ-FX-{i:02d}" for i in range(1, 11))
PRESENT_FILES = tuple(f"present-{i}.txt" for i in range(1, 6))


def fixture_requirements() -> list[Requirement]:
    doc = json.loads((FX / "reqs.json").read_text(encoding="utf-8"))
    out: list[Requirement] = []
    for row in doc["requirements"]:
        out.append(
            Requirement(
                id=row["id"],
                text=row["text"],
                source_path=row["source_path"],
                source_line=int(row["source_line"]),
                tokens=tuple(row.get("tokens") or []),
            )
        )
    return out


def fixture_tests() -> list[TestRec]:
    tests = discover_tests(
        REPO,
        "command-center/p2-wave/probes/BLD-0016/fixtures",
        corpus="fixture",
    )
    apply_registry(tests, load_registry_maps(FX / "registry.json"))
    return tests


def control_missing_is_absent() -> dict[str, Any]:
    planted = json.loads((FX / "planted_manifest.json").read_text(encoding="utf-8"))
    rel = planted["entries"][0]["path"]
    rec = classify_path(REPO / rel)
    ok = rec["verdict"] == ABSENT and rec["sha256"] is None
    return {
        "id": "manifest-nonexistent-path-absent",
        "pass": ok,
        "detail": (
            f"path={rel} verdict={rec['verdict']} sha256={rec['sha256']} "
            f"claimed={planted['entries'][0].get('claimed_verdict')}"
        ),
        "probe": {
            "relpath": rel,
            "verdict": rec["verdict"],
            "bytes": rec.get("bytes") or 0,
            "sha256": rec.get("sha256"),
        },
    }


def control_zero_byte_is_empty() -> dict[str, Any]:
    rec = classify_path(FX / "empty.txt")
    ok = rec["verdict"] == EMPTY and rec["verdict"] != PRESENT and rec["st_size"] == 0
    return {
        "id": "zero-byte-file-empty-never-present",
        "pass": ok,
        "detail": (
            f"verdict={rec['verdict']} st_size={rec['st_size']} "
            f"bytes={rec['bytes']}"
        ),
        "probe": {
            "relpath": "command-center/p2-wave/probes/BLD-0016/fixtures/empty.txt",
            "verdict": rec["verdict"],
            "st_size": rec["st_size"],
            "sha256": rec.get("sha256"),
        },
    }


def control_directory_requires_member() -> dict[str, Any]:
    bare_no_name = classify_path(FX / "dir-only")
    bare_named = classify_path(FX / "dir-only", required_member="MINIMUM.md")
    ok_dir = classify_path(FX / "dir-with-member", required_member="MINIMUM.md")
    ok = (
        bare_no_name["verdict"] == DIR_INCOMPLETE
        and bare_no_name["verdict"] != PRESENT
        and bare_named["verdict"] == DIR_INCOMPLETE
        and bare_named["verdict"] != PRESENT
        and ok_dir["verdict"] == PRESENT
        and isinstance(ok_dir.get("sha256"), str)
        and ok_dir["bytes"] > 0
    )
    return {
        "id": "directory-requires-named-member",
        "pass": ok,
        "detail": (
            f"unnamed={bare_no_name['verdict']} "
            f"missing_member={bare_named['verdict']} "
            f"with_member={ok_dir['verdict']} bytes={ok_dir.get('bytes')}"
        ),
        "probe": {
            "dir_only_unnamed": bare_no_name["verdict"],
            "dir_only_named_missing": bare_named["verdict"],
            "dir_with_member": {
                "verdict": ok_dir["verdict"],
                "bytes": ok_dir.get("bytes"),
                "sha256": ok_dir.get("sha256"),
            },
        },
    }


def review_five_present_independent() -> dict[str, Any]:
    checked: list[dict[str, Any]] = []
    for name in PRESENT_FILES:
        path = FX / name
        py = classify_path(path)
        unix = unix_stat_reprobe(path)
        size_match = (
            py["verdict"] == PRESENT
            and unix["verdict"] == PRESENT
            and py["st_size"] == unix["st_size"]
            and unix["st_size"] is not None
            and unix["st_size"] > 0
        )
        # Independent hash: raw sha256sum vs hashlib of the same raw bytes.
        raw_sha = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
        hash_match = unix.get("sha256_raw") == raw_sha
        checked.append(
            {
                "path": f"command-center/p2-wave/probes/BLD-0016/fixtures/{name}",
                "python_verdict": py["verdict"],
                "python_st_size": py["st_size"],
                "python_sha256_crlf_norm": py["sha256"],
                "unix_verdict": unix["verdict"],
                "unix_st_size": unix["st_size"],
                "unix_sha256_raw": unix.get("sha256_raw"),
                "size_match": size_match,
                "raw_hash_match": hash_match,
                "unix_error": unix.get("error"),
            }
        )
    ok = len(checked) == 5 and all(
        c["size_match"] and c["raw_hash_match"] for c in checked
    )
    return {
        "reviewer_id": "BLD-0016-unix-stat-vs-python-os.stat",
        "independent": True,
        "powershell_get_item": {
            "present": False,
            "note": (
                "Catalog pairing is PowerShell Get-Item vs Python os.stat. "
                "pwsh and powershell are absent on this Linux estate; "
                "unix stat -c %s + sha256sum is the second tool."
            ),
        },
        "verdict": "PASS" if ok else "FAIL",
        "checked_count": len(checked),
        "present_reprobed": checked,
        "pass": ok,
        "detail": (
            f"reprobed={len(checked)} "
            f"size_match={sum(1 for c in checked if c['size_match'])} "
            f"raw_hash_match={sum(1 for c in checked if c['raw_hash_match'])}"
        ),
    }


def review_ten_mappings(result: JoinResult) -> dict[str, Any]:
    tests_by_id = {t.id: t for t in result.tests}
    reqs_by_id = {r.id: r for r in result.requirements}
    checked: list[dict[str, Any]] = []
    for rid in REVIEW_REQS:
        mapped = [m for m in result.mappings if m.requirement_id == rid]
        if not mapped:
            checked.append(
                {
                    "requirement_id": rid,
                    "test_id": "",
                    "channel": "",
                    "body_asserts_requirement": False,
                    "verdict": "ID-ONLY",
                    "missing_tokens": ["no-mapping"],
                }
            )
            continue
        order = {"test-id": 0, "marker": 1, "registry-entry": 2}
        mapped.sort(key=lambda m: order.get(m.channel, 9))
        m = mapped[0]
        test = tests_by_id[m.test_id]
        req = reqs_by_id[rid]
        body = test.source.lower()
        missing = [tok for tok in req.tokens if tok.lower() not in body]
        confirms = not missing
        checked.append(
            {
                "requirement_id": rid,
                "test_id": m.test_id,
                "channel": m.channel,
                "body_asserts_requirement": confirms,
                "verdict": "CONFIRMS-REQUIREMENT" if confirms else "ID-ONLY",
                "missing_tokens": missing,
            }
        )
    id_only = [c for c in checked if c["verdict"] != "CONFIRMS-REQUIREMENT"]
    ok = len(checked) >= 10 and not id_only
    return {
        "reviewer_id": "BLD-0016-body-read-not-id-match",
        "verdict": "PASS" if ok else "FAIL",
        "independent": True,
        "checked_count": len(checked),
        "mappings_checked": [
            {
                "requirement_id": row["requirement_id"],
                "test_id": row["test_id"],
                "body_asserts_requirement": row["body_asserts_requirement"],
                "verdict": row["verdict"],
                "channel": row.get("channel"),
            }
            for row in checked
        ],
        "id_only": id_only,
    }


def run_fixture_controls() -> dict[str, Any]:
    reqs = fixture_requirements()
    tests = fixture_tests()
    result = join(reqs, tests)
    c1 = control_missing_is_absent()
    c2 = control_zero_byte_is_empty()
    c3 = control_directory_requires_member()
    five = review_five_present_independent()
    matrix = review_ten_mappings(result)
    controls = [c1, c2, c3]
    all_pass = (
        all(c["pass"] for c in controls)
        and five["pass"]
        and matrix["verdict"] == "PASS"
    )
    return {
        "result": result,
        "controls": controls,
        "five_present": five,
        "matrix_reviewer": matrix,
        "all_pass": all_pass,
    }
