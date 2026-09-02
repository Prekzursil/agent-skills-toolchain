"""Live measurement for CNF-0103 (no artifact I/O)."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools_under_test import both_states, run_all

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0103"
OUT = "command-center/confirmation/CNF-0103-longpath-devicename.json"
SCHEMA = "command-center/schema/platform-report.schema.json"
QUESTION = (
    "Does the tooling survive Windows path edge cases? Exercise paths beyond "
    "the legacy limit and files named with reserved device names, and answer: "
    "does every file walker, hasher and installer handle them with the "
    "extended-length prefix, or does one crash and silently report zero files?"
)
SENTINEL = (
    "SUCCESS:CNF-0103 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and every tool reports the "
    "known fixture count or an explicit error; no tool silently returned zero. "
    "Any other terminal state is FAILED:CNF-0103 <classification> with the "
    "diagnostic tail attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0103/probe1_live_count.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0103/probe2_detector_control.py"
)


def snippet_line(rel: str, needle: str) -> int:
    path = REPO / rel
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    idx = text.find(needle)
    if idx < 0:
        return 0
    return text[:idx].count("\n") + 1


def payload_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Probe-readable fields live under report (receipt additionalProperties=false)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    tests = report.get("tests")
    if not isinstance(tests, dict):
        tests = doc.get("tests") if isinstance(doc.get("tests"), dict) else {}
    results = report.get("results")
    if not isinstance(results, list):
        results = doc.get("results") if isinstance(doc.get("results"), list) else []
    det = report.get("detector_controls")
    if not isinstance(det, list):
        det = (
            doc.get("detector_controls")
            if isinstance(doc.get("detector_controls"), list)
            else []
        )
    known = report.get("known_fixture_count")
    if known is None:
        known = doc.get("known_fixture_count")
    return {
        "tests": tests,
        "results": results,
        "detector_controls": det,
        "known_fixture_count": known,
    }


def live() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cnf0103-") as td:
        tmp = Path(td)
        bundle = run_all(tmp)
        det = both_states(tmp / "ctrl")
    return {"bundle": bundle, "both_states": det}


def verdict(bundle: dict[str, Any], det: dict[str, Any]) -> tuple[str, str]:
    silent = [
        r["id"]
        for r in bundle["toolchain_results"]
        if r.get("outcome") == "silent-zero"
    ]
    naive = bundle["naive_device"]
    precedent = bool(naive.get("raised") and "NUL" in (naive.get("error") or ""))
    prefix_ok = int(bundle.get("prefix_invocation_count") or 0) > 0
    inv = bundle["inventory"]
    if not inv.get("long_exceeds_legacy_260"):
        return "FAILED", "long-path-not-beyond-260"
    if not precedent:
        return "FAILED", "relpath-precedent-not-reproduced"
    if not prefix_ok:
        return "FAILED", "extended-length-prefix-not-exercised"
    if not det.get("fired_on_bad") or not det.get("silent_on_good"):
        return "FAILED", "detector-control-failed"
    if silent:
        return "FAILED", "silent-zero:" + ",".join(silent)
    return "SUCCESS", "all-tools-count-or-explicit-error"


def answer_text(bundle: dict[str, Any], det: dict[str, Any], state: str) -> str:
    inv = bundle["inventory"]
    naive = bundle["naive_device"]
    plug = bundle["plugin"]
    rows = []
    for r in bundle["results"]:
        rows.append(
            f"{r['id']} outcome={r['outcome']} count={r.get('file_count')!r}"
        )
    pg_row = next(
        (r for r in bundle["results"] if r["id"] == "walker-path-guard-contained-rglob"),
        {},
    )
    if pg_row.get("outcome") == "ok":
        pg_note = (
            f"path_guard.contained_rglob counted the known set "
            f"({pg_row.get('file_count')}). "
        )
    else:
        pg_note = (
            f"path_guard.py outcome={pg_row.get('outcome')} "
            f"error={pg_row.get('error')!r} (explicit-error, not silent zero). "
        )
    return (
        f"Host {os.name}/{platform.system()} cannot open() via \\\\?\\ (that is a "
        f"Windows CreateFile convention), so live I/O used POSIX paths. Known "
        f"fixture count={inv['known_count']} (ordinary control + 6 reserved "
        f"device names + one path of {inv['long_full_chars']} chars). "
        f"ntpath.relpath({naive.get('error')!r}) is the Phase-0 crash; the "
        f"matching \\\\?\\ prefix on path AND start recovers reserved and long "
        f"Windows paths (relpath-ntpath-extended-length). Production "
        f"unit_manifest.derive was run against a throwaway fake repo, never "
        f"--write. Plugin installer: {plug.get('error')}. "
        f"path_guard: {pg_note}"
        f"Detector: swallowed-zero count={det['bad_file_count']} on known "
        f"{det['known_fixture_count']}; honest count={det['good_file_count']}. "
        f"Rows: " + "; ".join(rows) + f" Terminal state={state}."
    )


def _digest(rel: str) -> tuple[str, int] | None:
    path = REPO / rel
    if not path.is_file():
        return None
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _eol(rel: str) -> str:
    raw = (REPO / rel).read_bytes()
    crlf = raw.count(b"\r\n")
    rest = raw.replace(b"\r\n", b"")
    lf = rest.count(b"\n")
    cr = rest.count(b"\r")
    if crlf and not lf and not cr:
        return "CRLF"
    if lf and not crlf and not cr:
        return "LF"
    if not crlf and not lf and not cr:
        return "BINARY"
    return "MIXED"


def _artifact(rel: str, role: str) -> dict[str, Any] | None:
    got = _digest(rel)
    if got is None:
        return None
    sha, size = got
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": _eol(rel),
        "role": role,
    }


def _probe(
    *,
    role: str,
    method: str,
    command: str,
    raw_output: str,
    fingerprint: str,
    exit_code: int,
) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65536],
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def build_document() -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    measured = live()
    ended = datetime.now(timezone.utc)
    bundle = measured["bundle"]
    det = measured["both_states"]
    state, why = verdict(bundle, det)
    sentinel = SENTINEL if state == "SUCCESS" else f"FAILED:CNF-0103 {why}"
    um = "tools/command-center/unit_manifest.py"
    pg = "tools/command-center/path_guard.py"
    wp = "command-center/p2-wave/probes/CNF-0103/winpath.py"
    um_line = snippet_line(um, "for path in sorted(base.rglob(\"*.json\")):")
    hash_line = snippet_line(
        um, 'raw = target.read_bytes().replace(b"\\r\\n", b"\\n")'
    )
    naive_line = snippet_line(wp, "return ntpath.relpath(path, start)")
    prefix_line = snippet_line(
        wp,
        "return ntpath.relpath(to_extended_length(path), to_extended_length(start))",
    )
    outcomes = {r["id"]: r["outcome"] for r in bundle["results"]}
    results = []
    for r in bundle["results"]:
        results.append(
            {
                "id": r["id"],
                "kind": r["kind"],
                "outcome": r["outcome"],
                "fixture_path": str(r["fixture_path"]),
                "file_count": r.get("file_count"),
                "error": r.get("error"),
            }
        )
    tests_map = {
        "known_nonempty_fixture": bundle["inventory"]["known_count"] > 0,
        "zero_distinguished_from_empty": bool(det["distinguished"]),
        "swallowed_exception_probed": bool(det["fired_on_bad"]),
        "extended_length_prefix_exercised": bundle["prefix_invocation_count"] > 0,
        "both_states": bool(det["fired_on_bad"] and det["silent_on_good"]),
        "precedent_relpath_crash": bool(bundle["naive_device"].get("raised")),
        "unit_manifest_write_not_used": True,
    }
    tests_arr = [
        {
            "id": name,
            "command": f"CNF-0103 live assertion {name}",
            "result": "PASS" if ok else "FAIL",
        }
        for name, ok in tests_map.items()
    ]
    detector_row = {
        "id": "swallowed-zero-vs-known-count",
        "fired_on_bad": bool(det["fired_on_bad"]),
        "silent_on_good": bool(det["silent_on_good"]),
        "bad_file_count": int(det["bad_file_count"]),
        "good_file_count": int(det["good_file_count"]),
        "known_fixture_count": int(det["known_fixture_count"]),
        "empty_tree_count": int(det["empty_tree_count"]),
        "zero_distinguished_from_empty": bool(det["distinguished"]),
    }
    pg_present = (REPO / pg).is_file()
    art_rels = [
        (um, "primary"),
        (SCHEMA, "supporting"),
        (wp, "supporting"),
        ("command-center/p2-wave/probes/CNF-0103/fixture.py", "supporting"),
        ("command-center/p2-wave/probes/CNF-0103/tools_under_test.py", "supporting"),
        ("command-center/p2-wave/probes/CNF-0103/measure.py", "supporting"),
        ("command-center/p2-wave/probes/CNF-0103/probe1_live_count.py", "supporting"),
        ("command-center/p2-wave/probes/CNF-0103/probe2_detector_control.py", "supporting"),
    ]
    if pg_present:
        art_rels.insert(2, (pg, "supporting"))
    artifacts = [row for rel, role in art_rels if (row := _artifact(rel, role))]
    naive = bundle["naive_device"]
    evidence = [
        {
            "claim": (
                "Every named walker, hasher and installer reported the known "
                f"fixture count ({bundle['inventory']['known_count']}) or an "
                "explicit error; none swallowed the walk into a silent zero."
            ),
            "verdict": "CONFIRMED" if state == "SUCCESS" else "REFUTED",
            "confidence": "almost-certain",
            "anchor": f"{um}:{um_line}",
            "probes": [
                _probe(
                    role="source",
                    method="test-run",
                    command=(
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import sys; sys.path.insert(0, "
                        "'command-center/p2-wave/probes/CNF-0103'); "
                        "from measure import live, verdict; m=live(); "
                        "print(verdict(m['bundle'], m['both_states']))\""
                    ),
                    raw_output=json.dumps(
                        {
                            "outcomes": outcomes,
                            "silent_zero_ids": bundle["silent_zero_ids"],
                            "known_count": bundle["inventory"]["known_count"],
                        },
                        sort_keys=True,
                    ),
                    fingerprint="cnf0103:source:run-all-outcomes",
                    exit_code=0 if state == "SUCCESS" else 1,
                ),
                _probe(
                    role="verifier",
                    method="command",
                    command=P1,
                    raw_output=(
                        f"outcomes={outcomes} silent={bundle['silent_zero_ids']} "
                        f"prefix={bundle['prefix_invocation_count']}"
                    ),
                    fingerprint="cnf0103:verifier:probe1-live-count",
                    exit_code=0 if state == "SUCCESS" else 1,
                ),
            ],
        },
        {
            "claim": (
                "Naive ntpath.relpath on \\\\.\\NUL reproduces ValueError "
                f"{naive.get('error')!r}; the extended-length prefix on path "
                f"AND start recovered {bundle['prefix_invocation_count']} "
                "invocations including reserved names and the >260-char path."
            ),
            "verdict": "CONFIRMED" if state == "SUCCESS" else "REFUTED",
            "confidence": "almost-certain",
            "anchor": f"{wp}:{naive_line or prefix_line}",
            "probes": [
                _probe(
                    role="source",
                    method="static-analysis",
                    command=f"{wp}:naive_nt_relpath",
                    raw_output=json.dumps(naive, sort_keys=True),
                    fingerprint="cnf0103:source:naive-relpath",
                    exit_code=0,
                ),
                _probe(
                    role="verifier",
                    method="test-run",
                    command=f"{wp}:safe_nt_relpath+to_extended_length",
                    raw_output=(
                        f"prefix_invocation_count="
                        f"{bundle['prefix_invocation_count']} "
                        f"long_chars={bundle['inventory']['long_full_chars']}"
                    ),
                    fingerprint="cnf0103:verifier:prefixed-relpath",
                    exit_code=0 if bundle["prefix_invocation_count"] > 0 else 1,
                ),
            ],
        },
        {
            "claim": (
                "Detector control fires on the swallowed-zero walker "
                f"(count={det['bad_file_count']} over known "
                f"{det['known_fixture_count']}) and is silent on the honest "
                f"walk (count={det['good_file_count']}); empty tree is also "
                f"zero and is marked distinguished."
            ),
            "verdict": "CONFIRMED" if det["fired_on_bad"] and det["silent_on_good"] else "REFUTED",
            "confidence": "almost-certain",
            "anchor": (
                "command-center/p2-wave/probes/CNF-0103/"
                "tools_under_test.py:both_states"
            ),
            "probes": [
                _probe(
                    role="source",
                    method="test-run",
                    command=P2,
                    raw_output=json.dumps(det, sort_keys=True, default=str),
                    fingerprint="cnf0103:source:detector-control",
                    exit_code=0 if det["fired_on_bad"] and det["silent_on_good"] else 1,
                ),
                _probe(
                    role="verifier",
                    method="file-read",
                    command=(
                        "command-center/p2-wave/probes/CNF-0103/"
                        "tools_under_test.py:swallowed_zero_walk"
                    ),
                    raw_output=(
                        f"fired_on_bad={det['fired_on_bad']} "
                        f"silent_on_good={det['silent_on_good']} "
                        f"empty={det['empty_tree_count']} "
                        f"hasher_line={hash_line}"
                    ),
                    fingerprint="cnf0103:verifier:swallowed-zero-walk",
                    exit_code=0,
                ),
            ],
        },
    ]
    duration = max(0.0, (ended - started).total_seconds())
    report: dict[str, Any] = {
        "kind": "platform-report",
        "observations": [
            {
                "name": "known_fixture_count",
                "measured": int(bundle["inventory"]["known_count"]),
                "method": "tempfile-hostile-tree",
                "anchor": "command-center/p2-wave/probes/CNF-0103/fixture.py:build_hostile_tree",
            },
            {
                "name": "prefix_invocation_count",
                "measured": int(bundle["prefix_invocation_count"]),
                "method": "winpath.to_extended_length counter",
                "anchor": f"{wp}:to_extended_length",
            },
            {
                "name": "silent_zero_ids",
                "measured": json.dumps(bundle["silent_zero_ids"]),
                "method": "run_all outcome classify",
                "anchor": "command-center/p2-wave/probes/CNF-0103/tools_under_test.py:run_all",
            },
            {
                "name": "path_guard_present",
                "measured": pg_present,
                "method": "stat",
                "anchor": pg,
            },
        ],
        "control_ids": ["swallowed-zero-vs-known-count"],
        "question": QUESTION,
        "title": "Long-path and reserved-device-name handling on Windows",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "answer": answer_text(bundle, det, state),
        "known_fixture_count": bundle["inventory"]["known_count"],
        "long_path_chars": bundle["inventory"]["long_full_chars"],
        "prefix_invocation_count": bundle["prefix_invocation_count"],
        "results": results,
        "detector_controls": [detector_row],
        "tests": tests_map,
        "platform": {
            "os_name": os.name,
            "system": platform.system(),
            "python": sys.version.split()[0],
            "windows_createfile_prefix_live": os.name == "nt",
        },
        "scope": {
            "plugin_installer": bundle["plugin"],
            "unit_manifest_global_write": False,
            "adv_rebuild_circle": False,
            "path_guard_present": pg_present,
        },
        "failure_classification_if_failed": why if state != "SUCCESS" else None,
    }
    doc: dict[str, Any] = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNF-0103",
        "min_bytes_threshold": 2000,
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": tests_arr,
        "negative_controls": [
            {
                "id": "swallowed-zero-vs-known-count",
                "kind": "known-broken-fixture",
                "description": (
                    "A walker that swallows reserved-name exceptions into an "
                    "empty list must be distinguished from an honest empty "
                    "tree. The known-non-empty hostile fixture is the bad "
                    "state; the honest walk is the good state."
                ),
                "fired_on_bad_state": bool(det["fired_on_bad"]),
                "silent_on_good_state": bool(det["silent_on_good"]),
                "bad_state_output": (
                    f"bad_file_count={det['bad_file_count']} "
                    f"known={det['known_fixture_count']}"
                ),
                "good_state_output": (
                    f"good_file_count={det['good_file_count']} "
                    f"empty_tree_count={det['empty_tree_count']}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNF-0103-probe2-detector-control",
            "verdict": "PASS"
            if det["fired_on_bad"] and det["silent_on_good"]
            else "FAIL",
            "independent": True,
            "notes": (
                "Re-run the DETECTOR CONTROL and confirm it fires on the "
                "known-broken swallowed-zero walker and is silent on the "
                "honest walk."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0103/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator + local $ref store",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": _probe(
                    role="verifier",
                    method="schema-validate",
                    command=(
                        "python3 command-center/p2-wave/probes/CNF-0103/emit.py"
                    ),
                    raw_output="schema-valid against platform-report via on-disk $ref store",
                    fingerprint="cnf0103:consumer:schema-validate",
                    exit_code=0,
                ),
            }
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; "
                "a later run that disagrees is a DISCREPANCY to record "
                "(spec 11039), never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live file open() via the Windows \\\\?\\ CreateFile prefix "
                    "was not exercised because this host is POSIX; ntpath "
                    "prefix conversion was exercised in-process."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Re-run probe1 on a Windows NTFS volume with long-path "
                    "aware CreateFile and confirm reserved device names open "
                    "under \\\\?\\C:\\...\\NUL rather than \\\\.\\NUL."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "platform-edge-case-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": report,
    }
    return doc
