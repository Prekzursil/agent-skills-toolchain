#!/usr/bin/env python3
"""Fixture controls for SYN-0029: exactly-one, vocabulary, planted omission."""
from __future__ import annotations

import json
from pathlib import Path

import closure as C

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
META = {"path": "fixtures/report", "present": True}


def load_register() -> list[dict]:
    return json.loads((FIX / "register.json").read_text(encoding="utf-8"))["records"]


def load_report(name: str) -> list[dict]:
    return json.loads((FIX / name).read_text(encoding="utf-8"))["items"]


def test_exactly_one_and_vocabulary() -> dict:
    register = load_register()
    good = C.close(register, load_report("report_complete.json"), {**META, "path": "fixtures/report_complete.json"})
    doubled = C.close(register, load_report("report_double_R1.json"), {**META, "path": "fixtures/report_double_R1.json"})
    illegal = C.close(register, load_report("report_illegal.json"), {**META, "path": "fixtures/report_illegal.json"})
    used = {row["label"] for row in good["rows"]}
    good_ok = (
        good["register_size"] == 5
        and good["unlabelled_count"] == 0
        and good["exactly_one_label_per_requirement"] is True
        and used == set(C.FIVE)
        and good["vocabulary_ok"] is True
        and not good["double_labelled"]
    )
    double_fails = (
        doubled["exactly_one_label_per_requirement"] is False
        and any(d.get("requirement_id") == "REQ-FIX-R1" for d in doubled["double_labelled"])
        and set(doubled["double_labelled"][0]["labels"]) == {"VERIFIED", "INFERRED"}
    )
    vocab_fails = (
        illegal["vocabulary_ok"] is False
        and any(x.get("label") == "PARTIAL" for x in illegal["illegal_labels"])
        and any(x.get("requirement_id") == "REQ-FIX-R1" for x in illegal["illegal_labels"])
    )
    return {
        "id": "test_exactly_one_label_per_requirement_and_vocabulary",
        "good_ok": good_ok,
        "double_fails": double_fails,
        "vocab_fails": vocab_fails,
        "pass": good_ok and double_fails and vocab_fails,
        "good_counts": good["label_counts"],
        "double_labelled": doubled["double_labelled"],
        "illegal_labels": illegal["illegal_labels"],
    }


def test_planted_omission() -> dict:
    register = load_register()
    complete = C.close(
        register, load_report("report_complete.json"), {**META, "path": "fixtures/report_complete.json"}
    )
    planted = C.planted_omission(
        register,
        load_report("report_complete.json"),
        "REQ-FIX-R3",
        {**META, "path": "fixtures/report_omit_from_complete"},
    )
    omitted_file = C.close(
        register, load_report("report_omit_R3.json"), {**META, "path": "fixtures/report_omit_R3.json"}
    )
    r3 = next(r for r in planted["rows"] if r["requirement_id"] == "REQ-FIX-R3")
    r3_file = next(r for r in omitted_file["rows"] if r["requirement_id"] == "REQ-FIX-R3")
    others_ok = all(
        r["unlabelled"] is False
        for r in planted["rows"]
        if r["requirement_id"] != "REQ-FIX-R3"
    )
    fired = (
        complete["unlabelled_count"] == 0
        and planted["planted_omission_fired"] is True
        and planted["unlabelled_count"] == 1
        and r3["label"] == C.DISAPPEARED
        and r3_file["label"] == C.DISAPPEARED
        and others_ok
    )
    return {
        "id": "planted_omission_delete_one_requirement_from_report",
        "pass": fired,
        "complete_unlabelled": complete["unlabelled_count"],
        "planted_unlabelled": planted["unlabelled_count"],
        "planted_omission_fired": planted["planted_omission_fired"],
        "dropped_label": r3["label"],
        "file_omit_label": r3_file["label"],
    }


def all_fixture_tests() -> list[dict]:
    a = test_exactly_one_and_vocabulary()
    b = test_planted_omission()
    return [
        {
            "id": "test_exactly_one_label_per_requirement",
            "result": "PASS" if a["double_fails"] and a["good_ok"] else "FAIL",
            "detail": {k: a[k] for k in ("good_ok", "double_fails") if k in a},
        },
        {
            "id": "planted_omission",
            "result": "PASS" if b["pass"] else "FAIL",
            "detail": {
                "complete_unlabelled": b["complete_unlabelled"],
                "planted_unlabelled": b["planted_unlabelled"],
                "fired": b["planted_omission_fired"],
            },
        },
        {
            "id": "test_label_vocabulary_is_the_declared_five",
            "result": "PASS" if a["vocab_fails"] and a["good_ok"] else "FAIL",
            "detail": {"vocab_fails": a["vocab_fails"], "good_counts": a["good_counts"]},
        },
    ]
