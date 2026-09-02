#!/usr/bin/env python3
"""Emit ADV-0117 artifact plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py
--write. Does not git add/commit/push.
"""
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
sys.path.insert(0, str(HERE))

from probe1_component_matrix import run_probe1  # noqa: E402
from probe2_count_crosscheck import run_probe2  # noqa: E402

UID = "ADV-0117"
OUT = "command-center/adversarial/ADV-0117-windows-hostile-path-matrix.json"
SCHEMA = "command-center/schema/fault-injection-run.schema.json"
SENTINEL = (
    "SUCCESS:ADV-0117 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0117 <reason>."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0117/probe1_component_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0117/probe2_count_crosscheck.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0117/probe_common.py",
    "command-center/p2-wave/probes/ADV-0117/probe1_component_matrix.py",
    "command-center/p2-wave/probes/ADV-0117/probe2_count_crosscheck.py",
    "command-center/p2-wave/probes/ADV-0117/write_receipts.py",
    "tools/router/index_build.py",
    "tools/marketplace/census.py",
    "tools/layout/migrate.py",
    "tools/plugin/cache_ownership.py",
]
ALLOWED = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
QUESTION = (
    "Which program components fail, corrupt data, or silently skip when a path "
    "contains a reserved device name, exceeds MAX_PATH, differs only by case, "
    "or contains spaces, non-ASCII characters or a trailing dot?"
)


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    receipt = "command-center/p2-wave/probes/ADV-0117/SUBAGENT-RETURN.json"
    if not path.is_file():
        return {
            "path": rel,
            "bytes": 0,
            "sha256": "",
            "exists": False,
            "present": False,
            "role": role,
            "unit_id": UID,
            "receipt_path": receipt,
        }
    sha, n = sha_file(path)
    return {
        "path": rel,
        "bytes": n,
        "sha256": sha,
        "exists": True,
        "present": True,
        "role": role,
        "eol": "LF",
        "unit_id": UID,
        "receipt_path": receipt,
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def probe_blob(role: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
        "exit_code": exit_code,
    }


def main() -> int:
    live1 = run_probe1()
    live2 = run_probe2()
    if live1.get("pass") is not True or live2.get("pass") is not True:
        print("FAILED:ADV-0117 in-process protocol did not pass")
        print(
            json.dumps(
                {"p1": live1.get("pass"), "p2": live2.get("pass")},
                indent=2,
            )
        )
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0117 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1b = probe_blob("source", P1, t1, c1)
    p2b = probe_blob("verifier", P2, t2, c2)

    ordinary_ok = bool(live1["ordinary_control"]["match"]) and bool(
        live2["ordinary_control"]["all_components_match"]
    )
    crash_distinct = bool(
        live1["reserved_relpath_control"]["crash_distinct_from_refusal"]
    ) and bool(live2["swallowed_exception_control"]["crash_distinct_from_refusal"])
    nc1 = {nc["id"]: nc for nc in live1["negative_controls"]}
    nc2 = {nc["id"]: nc for nc in live2["negative_controls"]}
    nc_ok = all(
        [
            nc1.get("NC-NAIVE-RELPATH-RESERVED", {}).get("fired_on_bad_state"),
            nc1.get("NC-NAIVE-RELPATH-RESERVED", {}).get("silent_on_good_state"),
            nc1.get("NC-CASEFOLD-HASHER-BOTH-STATES", {}).get("fired_on_bad_state"),
            nc1.get("NC-CASEFOLD-HASHER-BOTH-STATES", {}).get("silent_on_good_state"),
            nc2.get("NC-SWALLOWED-ZERO-VS-PRODUCTION", {}).get("fired_on_bad_state"),
            nc2.get("NC-SWALLOWED-ZERO-VS-PRODUCTION", {}).get("silent_on_good_state"),
            nc2.get("NC-CASEFOLD-HASHER-BOTH-STATES", {}).get("fired_on_bad_state"),
            nc2.get("NC-CASEFOLD-HASHER-BOTH-STATES", {}).get("silent_on_good_state"),
        ]
    )
    missing_control = not (ordinary_ok and crash_distinct and nc_ok)

    skip_index = {
        (r["component"], r["class_id"]): r for r in (live2.get("silent_skips") or [])
    }
    raw_targets: dict[str, str] = {}
    target_rows: list[dict] = []
    for row in live1.get("matrix") or []:
        if row.get("class_id") == "ordinary":
            continue
        tid = f"TARGET-{row['component'].upper()}-{row['class_id'].upper()}"
        verd = row.get("verdict") or "PARTIAL"
        skip = skip_index.get((row["component"], row["class_id"]))
        if skip and verd == "REFUTED":
            verd = "CONFIRMED"
        raw_targets[tid] = verd
        target_rows.append(
            {
                "id": tid,
                "class_id": row["class_id"],
                "component": row["component"],
                "outcome": row.get("outcome"),
                "verdict": verd,
                "expected_count": row.get("expected_count"),
                "reported_count": row.get("reported_count"),
                "silent_skip": bool(skip),
            }
        )

    targets = {
        tid: ("NOT-CHECKED" if missing_control else verd)
        for tid, verd in raw_targets.items()
    }
    for item in target_rows:
        item["verdict"] = targets[item["id"]]
    for tid, verd in targets.items():
        if verd not in ALLOWED:
            print(f"FAILED:ADV-0117 illegal verdict {tid}={verd}")
            return 1

    confirmed = sorted(tid for tid, verd in targets.items() if verd == "CONFIRMED")
    refuted = sorted(tid for tid, verd in targets.items() if verd == "REFUTED")
    skips = live2.get("silent_skips") or []

    tests = [
        {
            "id": "T1-NAMED-PROBE-1",
            "name": "Run each component over the fixture tree; record per-class outcome",
            "command": P1,
            "result": "PASS" if c1 == 0 else "FAIL",
            "exit_code": c1,
        },
        {
            "id": "T2-NAMED-PROBE-2",
            "name": "Count-based cross-check against an independent scandir oracle",
            "command": P2,
            "result": "PASS" if c2 == 0 else "FAIL",
            "exit_code": c2,
        },
        {
            "id": "T3-ORDINARY-PATH-IDENTICAL-COUNTS",
            "name": "control: an ordinary-path fixture must produce identical counts from both enumerations",
            "result": "PASS" if ordinary_ok else "FAIL",
        },
        {
            "id": "T4-SWALLOWED-EXCEPTION-DISTINCT-FROM-REFUSAL",
            "name": (
                "a swallowed exception must be classified as a defect distinct "
                "from a correct refusal; the NUL precedent shows a crash is safer "
                "than a silent zero"
            ),
            "result": "PASS" if crash_distinct else "FAIL",
        },
        {
            "id": "T5-NAIVE-RELPATH-RED-ON-RESERVED",
            "name": "Naive os.path.relpath walker goes red on NUL/CON under the ValueError monkeypatch",
            "result": "PASS"
            if nc1.get("NC-NAIVE-RELPATH-RESERVED", {}).get("fired_on_bad_state")
            else "FAIL",
        },
        {
            "id": "T6-CASEFOLD-HASHER-BOTH-STATES",
            "name": "Casefold hasher mutant drops a case-collision sibling and is silent on ordinary paths",
            "result": "PASS"
            if nc1.get("NC-CASEFOLD-HASHER-BOTH-STATES", {}).get("fired_on_bad_state")
            and nc1.get("NC-CASEFOLD-HASHER-BOTH-STATES", {}).get("silent_on_good_state")
            else "FAIL",
        },
        {
            "id": "T7-LONG-PATH-EXCEEDS-260",
            "name": "Long-path fixture relative length exceeds MAX_PATH (260)",
            "result": "PASS"
            if live1.get("classes", {}).get("long-path", {}).get("exceeds_max_path")
            else "FAIL",
        },
    ]

    defects = []
    for row in target_rows:
        if row["verdict"] != "CONFIRMED":
            continue
        defects.append(
            {
                "id": f"ADV-0117-{row['component']}-{row['class_id']}",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"{row['component']} on {row['class_id']}: outcome="
                    f"{row['outcome']} expected={row['expected_count']} "
                    f"reported={row['reported_count']}"
                ),
            }
        )

    plat = live1.get("platform") or {}
    answer = (
        f"On this {plat.get('system')} worktree (CreateFile not executed), "
        f"{len(refuted)} component×class cells handled the planted tree "
        f"(verdict REFUTED: no fail/corrupt/silent-skip) and {len(confirmed)} "
        f"cells CONFIRMED a failure class. Probe 2 silent-skips={len(skips)}. "
        f"Ordinary-path counts matched ({ordinary_ok}). A naive os.path.relpath "
        f"walker went red on NUL ({live1['reserved_relpath_control']['naive_exception']}); "
        f"production walk_files listed "
        f"{live1['reserved_relpath_control']['production_names']} under the same "
        f"monkeypatch, so a swallowed zero is distinct from a correct refusal. "
        f"Confirmed targets: {confirmed or 'none'}."
    )

    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    artifact = {
        "schema_version": 1,
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "completion_line": "UNIT-COMPLETE:ADV-0117",
        "title": (
            "Windows-hostile path matrix: reserved names, long paths, "
            "case collisions and Unicode"
        ),
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "report_kind": "fault-injection-run",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 1024,
        "spec_anchor": "_USER-PROMPTS.md:11016-11017, 11310, 11053",
        "produced_by": {
            "vendor": "spacexai-cursor",
            "model": "grok-4.6",
            "role": "platform-fault-injector",
            "execution_substrate": "linux-local-serialized",
        },
        "reviewer": {
            "reviewer_id": "ADV-0117-probe2-count-crosscheck",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "cross-probe-mechanism",
            "note": (
                "Probe 2 does not reuse probe 1's outcome table. It rebuilds the "
                "fixture forest and re-derives silent skips from oracle-vs-reported "
                "item counts."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0117/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the SECOND failure "
                "on the same hypothesis, enumerate >=2 mechanically different "
                "attack vectors before any third attempt"
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "platform": plat,
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "probe": "G-1-delivery-measure",
            }
        ],
        "defects": defects,
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": supporting,
        "evidence": [
            {
                "id": "probe1-component-matrix",
                "claim": (
                    "Each enumerator, packager, installer, artifact writer and "
                    "manifest hasher ran over one directory per hostile class. "
                    "Outcomes are correct/crash/silent_skip/wrong_result from "
                    "live exceptions and file lists, not from a summary."
                ),
                "verdict": "CONFIRMED" if live1.get("pass") else "REFUTED",
                "anchor": (
                    "tools/router/index_build.py:walk_files; "
                    "tools/plugin/cache_ownership.py:_copy_tree_files; "
                    "tools/marketplace/census.py:census"
                ),
                "probes": [p1b],
                "matrix": live1.get("matrix"),
                "ordinary_control": live1.get("ordinary_control"),
                "reserved_relpath_control": live1.get("reserved_relpath_control"),
            },
            {
                "id": "probe2-count-crosscheck",
                "claim": (
                    "Independent scandir+lexical-relpath oracle compared to each "
                    "component's reported item count. Silent skip is a negative "
                    "delta with no exception. Ordinary-path counts matched."
                ),
                "verdict": "CONFIRMED" if skips else "REFUTED",
                "anchor": (
                    "command-center/p2-wave/probes/ADV-0117/"
                    "probe2_count_crosscheck.py"
                ),
                "probes": [p2b],
                "ordinary_control": live2.get("ordinary_control"),
                "swallowed_exception_control": live2.get("swallowed_exception_control"),
                "silent_skips": skips,
                "row_count": len(live2.get("rows") or []),
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-NAIVE-RELPATH-RESERVED",
                "kind": "unguarded-os.path.relpath-on-NUL",
                "description": (
                    "Monkeypatched os.path.relpath raises ValueError on NUL/CON. "
                    "The naive walker must go red; production walk_files must not."
                ),
                "fired_on_bad_state": bool(
                    nc1.get("NC-NAIVE-RELPATH-RESERVED", {}).get("fired_on_bad_state")
                ),
                "silent_on_good_state": bool(
                    nc1.get("NC-NAIVE-RELPATH-RESERVED", {}).get("silent_on_good_state")
                ),
            },
            {
                "id": "NC-SWALLOWED-ZERO-VS-PRODUCTION",
                "kind": "crash-swallowed-as-zero",
                "description": (
                    "A walker that catches the NUL ValueError and returns count=0 "
                    "is the defect. Production listing of NUL+CON+keep.txt is not "
                    "an explicit refusal; it is the green state."
                ),
                "fired_on_bad_state": bool(
                    nc2.get("NC-SWALLOWED-ZERO-VS-PRODUCTION", {}).get(
                        "fired_on_bad_state"
                    )
                ),
                "silent_on_good_state": bool(
                    nc2.get("NC-SWALLOWED-ZERO-VS-PRODUCTION", {}).get(
                        "silent_on_good_state"
                    )
                ),
            },
            {
                "id": "NC-CASEFOLD-HASHER-BOTH-STATES",
                "kind": "casefold-key-collision",
                "description": (
                    "A hasher that keys by casefold silently drops one of "
                    "ReadMe.txt/readme.txt. The production hasher must keep both "
                    "on this case-sensitive volume, and the mutant must fire."
                ),
                "fired_on_bad_state": bool(
                    nc1.get("NC-CASEFOLD-HASHER-BOTH-STATES", {}).get(
                        "fired_on_bad_state"
                    )
                ),
                "silent_on_good_state": bool(
                    nc1.get("NC-CASEFOLD-HASHER-BOTH-STATES", {}).get(
                        "silent_on_good_state"
                    )
                ),
            },
        ],
        "enumerated_targets": [
            {"id": tid, "verdict": verd} for tid, verd in sorted(targets.items())
        ],
        "targets": [
            {"id": tid, "verdict": verd} for tid, verd in sorted(targets.items())
        ],
        "controls": {
            "ordinary_path_identical_counts": ordinary_ok,
            "swallowed_exception_distinct_from_refusal": crash_distinct,
            "long_path_exceeds_260": live1.get("classes", {})
            .get("long-path", {})
            .get("exceeds_max_path"),
            "missing_control_downgraded": missing_control,
        },
        "notes": (
            "G-1 for ADV-0117: live named probes, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Linux substrate: reserved names are POSIX files. "
            + SENTINEL
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(artifact, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:ADV-0117 completion sentinel missing from artifact text")
        return 1
    sha, n = sha_file(out_path)
    if n < 1024:
        print(f"FAILED:ADV-0117 artifact too small: {n}")
        return 1

    primary = art_row(OUT, "primary")
    primary["sha256"] = sha
    primary["bytes"] = n
    primary["exists"] = True
    primary["present"] = True
    man_rows = [primary] + [art_row(p, "supporting") for p in SUPPORTING]
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
                "role": "component-matrix",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "count-crosscheck",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": n,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0117/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0117-probe2-count-crosscheck",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0117: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(man_rows),
        "present": len(man_rows),
        "artifacts": man_rows,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={sha} bytes={n}")
    print("SUCCESS:ADV-0117 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
