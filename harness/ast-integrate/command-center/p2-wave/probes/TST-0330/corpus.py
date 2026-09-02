#!/usr/bin/env python3
"""Unit-state corpus for TST-0330, including malformed and partial rows.

Zero disagreements on a corpus with no malformed inputs is not a result.
This corpus deliberately includes partial artifacts, missing sentinels, and
torn JSON.
"""
from __future__ import annotations

import copy
import json
from typing import Any


def healthy() -> dict[str, Any]:
    return {
        "unit_id": "U-HEALTHY",
        "state": "SUCCESS",
        "min_bytes_threshold": 128,
        "artifact": {
            "path": "artifacts/U-HEALTHY.json",
            "exists": True,
            "bytes": 256,
            "sha256": "a" * 64,
            "parse_ok": True,
            "body": '{"ok":true}',
        },
        "sentinel": "SUCCESS:U-HEALTHY",
        "evidence": [
            {"anchor": "file:1", "claim": "artifact exists on disk"},
            {"anchor": "file:2", "claim": "artifact parses"},
        ],
        "tests": [{"id": "t1", "result": "PASS"}],
        "negative_controls": [{"id": "c1", "fired_on_bad_state": True}],
        "reviewer": {"verdict": "PASS", "independent": True},
        "defects": [],
        "manifest_registered": True,
        "downstream": [
            {"consumer": "probe1", "read_ok": True, "executed": True}
        ],
        "exit_code": 0,
        "notes": "exit_code is present and must be ignored",
    }


def _object(uid: str, kind_note: str, state: dict[str, Any], malformed: bool = False) -> dict[str, Any]:
    return {
        "id": uid,
        "kind": "object",
        "malformed": malformed,
        "class": kind_note,
        "state": state,
        "input_verbatim": json.dumps(state, sort_keys=True, ensure_ascii=True),
    }


def _raw(uid: str, kind_note: str, raw: str) -> dict[str, Any]:
    return {
        "id": uid,
        "kind": "raw",
        "malformed": True,
        "class": kind_note,
        "raw": raw,
        "input_verbatim": raw,
    }


def build_corpus() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    h = healthy()
    rows.append(_object("healthy-complete", "healthy", copy.deepcopy(h)))

    m = copy.deepcopy(h)
    m["artifact"]["exists"] = False
    m["unit_id"] = "U-EXIT0-MISSING"
    m["sentinel"] = "SUCCESS:U-EXIT0-MISSING"
    m["exit_code"] = 0
    rows.append(
        _object(
            "exit-zero-missing-artifact",
            "partial-artifact",
            m,
        )
    )

    m = copy.deepcopy(h)
    m["artifact"]["bytes"] = 0
    m["unit_id"] = "U-EMPTY"
    m["sentinel"] = "SUCCESS:U-EMPTY"
    rows.append(_object("partial-artifact-empty", "partial-artifact", m))

    m = copy.deepcopy(h)
    m.pop("sentinel")
    m["unit_id"] = "U-NO-SENTINEL"
    rows.append(_object("missing-sentinel", "missing-sentinel", m))

    rows.append(_raw("torn-json", "torn-json", '{"unit_id":"U-TORN","state":'))
    rows.append(_raw("torn-json-unclosed", "torn-json", '{"state":"SUCCESS"'))
    rows.append(_raw("empty-raw", "torn-json", ""))
    rows.append(_raw("non-json-garbage", "torn-json", "not json at all"))
    rows.append(_raw("json-null", "torn-json", "null"))
    rows.append(_raw("json-array", "torn-json", "[]"))
    rows.append(_raw("json-string", "torn-json", '"SUCCESS"'))
    rows.append(_raw("json-number", "torn-json", "0"))

    m = copy.deepcopy(h)
    m["evidence"] = []
    m["unit_id"] = "U-NO-EV"
    m["sentinel"] = "SUCCESS:U-NO-EV"
    rows.append(_object("missing-evidence", "partial", m))

    m = copy.deepcopy(h)
    m["tests"] = [{"id": "t1", "result": "FAIL"}]
    m["unit_id"] = "U-TESTS-FAIL"
    m["sentinel"] = "SUCCESS:U-TESTS-FAIL"
    rows.append(_object("tests-failed", "partial", m))

    m = copy.deepcopy(h)
    m["negative_controls"] = [{"id": "c1", "fired_on_bad_state": False}]
    m["unit_id"] = "U-INERT-NC"
    m["sentinel"] = "SUCCESS:U-INERT-NC"
    rows.append(_object("inert-negative-control", "partial", m))

    m = copy.deepcopy(h)
    m["reviewer"] = {"verdict": "FAIL", "independent": True}
    m["unit_id"] = "U-REV-FAIL"
    m["sentinel"] = "SUCCESS:U-REV-FAIL"
    rows.append(_object("reviewer-not-pass", "partial", m))

    m = copy.deepcopy(h)
    m["defects"] = [
        {
            "id": "D1",
            "severity": "P0",
            "status": "open",
            "summary": "open blocker",
        }
    ]
    m["unit_id"] = "U-P0"
    m["sentinel"] = "SUCCESS:U-P0"
    rows.append(_object("open-p0", "partial", m))

    m = copy.deepcopy(h)
    m["manifest_registered"] = False
    m.pop("manifest", None)
    m["unit_id"] = "U-UNREG"
    m["sentinel"] = "SUCCESS:U-UNREG"
    rows.append(_object("unregistered", "partial", m))

    m = copy.deepcopy(h)
    m["downstream"] = [
        {"consumer": "probe", "read_ok": False, "executed": False}
    ]
    m["unit_id"] = "U-DOWN"
    m["sentinel"] = "SUCCESS:U-DOWN"
    rows.append(_object("downstream-unread", "partial", m))

    m = copy.deepcopy(h)
    m["state"] = "RUNNING"
    m["unit_id"] = "U-RUNNING"
    m["sentinel"] = "SUCCESS:U-RUNNING"
    rows.append(_object("non-terminal-state", "partial", m))

    m = copy.deepcopy(h)
    m["artifact"]["parse_ok"] = False
    m["artifact"]["body"] = "{not-json"
    m["unit_id"] = "U-BADPARSE"
    m["sentinel"] = "SUCCESS:U-BADPARSE"
    rows.append(_object("unparseable-artifact-body", "partial", m))

    m = copy.deepcopy(h)
    m["artifact"]["exists"] = False
    m["artifact"]["sha256"] = "b" * 64
    m["notes"] = "plausible digest is not a receipt"
    m["unit_id"] = "U-DIGEST-ONLY"
    m["sentinel"] = "SUCCESS:U-DIGEST-ONLY"
    rows.append(_object("plausible-digest-no-file", "partial-artifact", m))

    m = copy.deepcopy(h)
    m["artifact"]["exists"] = False
    m["notes"] = "path artifacts/U-PATH.json is not proof the file exists"
    m["unit_id"] = "U-PATH-TEXT"
    m["sentinel"] = "SUCCESS:U-PATH-TEXT"
    rows.append(_object("path-in-text-not-proof", "partial-artifact", m))

    m = {"state": "SUCCESS", "exit_code": 0}
    rows.append(
        _object("truncated-object-missing-keys", "partial", m, malformed=False)
    )

    rows.append(
        _raw(
            "partial-then-torn",
            "torn-json",
            '{"unit_id":"U-HALF","state":"SUCCESS","sentinel":"SUCCESS:U-HALF"',
        )
    )
    return rows


def corpus_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    classes = {}
    for row in rows:
        classes[row["class"]] = classes.get(row["class"], 0) + 1
    return {
        "size": len(rows),
        "malformed_count": sum(1 for r in rows if r.get("malformed")),
        "classes": classes,
        "ids": [r["id"] for r in rows],
    }


if __name__ == "__main__":
    rows = build_corpus()
    print(json.dumps(corpus_stats(rows), sort_keys=True, indent=2))
