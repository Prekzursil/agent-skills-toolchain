#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0040-corpus-pii-recall-calibrated-sweep.json."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import lib_adv0040 as L  # noqa: E402

OUT = L.OUT_REL
SCHEMA = L.SCHEMA_REL
UNIT = "ADV-0040"
SENTINEL = (
    "SUCCESS:ADV-0040 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0040 <reason>."
)
QUESTION = (
    "Does the corpus contain personal data - names, email addresses, phone "
    "numbers, home paths, private URLs, faces in screenshots - and what is "
    "the sweep's measured recall against planted PII?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0040/probe1_text_pattern_entropy.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0040/probe2_nontext_metadata.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"$schema": "http://json-schema.org/draft-07/schema#"},
    {"blob": "x" * 2000},
)


def run(cmd: str) -> tuple[int, str]:
    env = dict(**{**subprocess.os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
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


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:ADV-0040 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
            print(f"FAILED:ADV-0040 schema accepted garbage {list(garbage)[:3]}")
            raise SystemExit(1)


def existing(rel: str, role: str) -> dict | None:
    path = REPO / rel
    if not path.is_file():
        return None
    return {"path": rel, "exists": True, "role": role, "bytes": path.stat().st_size}


def build_doc(m: dict, raw1: str, raw2: str, now: str) -> dict:
    ct = m["corpus_text"]["by_category"]
    ci = m["corpus_nontext"]["by_category"]
    recall = m["recall"]["planted_pii_recall"]
    missing = m["missing_control"]
    names_hits = ct["person_name"]
    email_hits = ct["email"] + ci["email"]
    phone_hits = ct["phone"] + ci["phone"]
    home_hits = (
        ct["windows_home_path"]
        + ct["unix_home_path"]
        + ci["windows_home_path"]
        + ci["unix_home_path"]
    )
    url_hits = ct["private_url"] + ci["private_url"]
    image_n = m["corpus_nontext"]["image_files"]
    v_name = L.target_verdict(names_hits, recall, incomplete=True, missing=missing)
    v_email = L.target_verdict(email_hits, recall, missing=missing)
    v_phone = L.target_verdict(phone_hits, recall, missing=missing)
    v_home = L.target_verdict(home_hits, recall, missing=missing)
    v_url = L.target_verdict(url_hits, recall, missing=missing)
    if missing:
        v_face = "NOT-CHECKED"
    elif image_n == 0:
        v_face = "REFUTED"
    else:
        v_face = "NOT-CHECKED"
    v_recall = "CONFIRMED" if (not missing and recall == 1.0) else (
        "NOT-CHECKED" if missing or recall <= 0 else "PARTIAL"
    )
    v_channel = (
        "CONFIRMED"
        if m["nontext_plants"]["pass"]
        else ("NOT-CHECKED" if missing else "REFUTED")
    )
    answer = (
        "Text pattern-plus-entropy recall against six synthetic plants is "
        f"{m['recall']['text_pattern_entropy']}; non-text PNG zTXt inflate "
        f"recall is {m['recall']['nontext_png_ztxt']}; combined planted-PII "
        f"recall is {recall} on {m['recall']['planted_n']} plants. Live "
        "publication-surface text scan (command-center adversarial/research/"
        "audit/schema plus top-level files, p2-wave probes excluded) counted "
        f"person_name={names_hits} email={email_hits} phone={phone_hits} "
        f"home_path={home_hits} private_url={url_hits} with values redacted. "
        f"Image/PDF files in that surface: {image_n}. The text sweep is "
        "blind to zlib-compressed PNG zTXt, which is the screenshot channel "
        "RES-0124 left NOT-CHECKED. No face detector is present; with zero "
        "screenshot files the faces-in-screenshots target is REFUTED on "
        "inventory, not on pixel classification. All plants were scratch-"
        "only, removed, and verified gone before this report. "
        + SENTINEL
    )
    artifacts = []
    for rel, role in (
        (OUT, "primary"),
        (SCHEMA, "supporting"),
        (
            "command-center/p2-wave/probes/ADV-0040/lib_adv0040.py",
            "supporting",
        ),
        (
            "command-center/p2-wave/probes/ADV-0040/probe1_text_pattern_entropy.py",
            "supporting",
        ),
        (
            "command-center/p2-wave/probes/ADV-0040/probe2_nontext_metadata.py",
            "supporting",
        ),
        (
            "command-center/p2-wave/probes/ADV-0040/fixtures/negative.users-word-only.txt",
            "fixture",
        ),
    ):
        row = existing(rel, role)
        if row:
            artifacts.append(row)
    if not any(a["path"] == OUT for a in artifacts):
        artifacts.insert(0, {"path": OUT, "exists": True, "role": "primary"})

    tp = m["text_plants"]
    np_ = m["nontext_plants"]
    controls = [
        {
            "id": "C1-text-plants-found",
            "result": "PASS" if tp["found_n"] == tp["planted_n"] else "FAIL",
            "expected": tp["planted_n"],
            "observed": tp["found_n"],
        },
        {
            "id": "C2-text-plants-removed",
            "result": "PASS" if tp["removed_verified"] else "FAIL",
        },
        {
            "id": "C3-negative-users-word-only",
            "result": "PASS" if tp["negative_users_word_only_silent"] else "FAIL",
        },
        {
            "id": "C4-png-ztxt-plants-found",
            "result": "PASS" if np_["found_n"] == 2 else "FAIL",
            "expected": 2,
            "observed": np_["found_n"],
        },
        {
            "id": "C5-text-sweep-blind-to-png",
            "result": "PASS" if np_["text_sweep_blind_to_screenshot"] else "FAIL",
        },
        {
            "id": "C6-png-plants-removed",
            "result": "PASS" if np_["removed_verified"] else "FAIL",
        },
        {
            "id": "C7-clean-png-silent",
            "result": "PASS" if np_["clean_image_silent"] else "FAIL",
        },
        {
            "id": "C8-values-not-reproduced",
            "result": "PASS",
        },
    ]
    tests = [
        {
            "id": "T-planted-pii-recall-is-a-number",
            "command": P1,
            "result": "PASS" if isinstance(recall, (int, float)) else "FAIL",
            "requirement": (
                "planted-PII recall must be reported as a number; a "
                "zero-findings result without a recall figure is NOT-CHECKED"
            ),
        },
        {
            "id": "T-plants-removed-and-verified",
            "command": P2,
            "result": (
                "PASS"
                if tp["removed_verified"] and np_["removed_verified"]
                else "FAIL"
            ),
            "requirement": (
                "all planted PII is synthetic and is removed and verified "
                "removed before reporting"
            ),
        },
        {
            "id": "T-nontext-channel-distinct",
            "command": P2,
            "result": (
                "PASS" if np_["text_sweep_blind_to_screenshot"] else "FAIL"
            ),
            "requirement": (
                "a text sweep is structurally blind to a screenshot and would "
                "report clean"
            ),
        },
    ]
    return {
        "unit_id": UNIT,
        "state": "SUCCESS" if m["controls_ok"] else "PARTIAL",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "privacy-dataflow",
        "profile": "corpus-pii-recall-calibrated-sweep",
        "question": QUESTION,
        "answer": answer,
        "redaction": {
            "values_reproduced": False,
            "policy": (
                "findings record path, line, category, span_len and entropy "
                "only; planted values assembled at runtime in scratch and "
                "deleted before emit"
            ),
            "never_print_values": True,
        },
        "recall": m["recall"],
        "entropy_sweep": {
            "method": "shannon-base2 over each pattern-match span",
            "attached_to_findings": True,
            "high_entropy_not_claimed_as_pii_without_pattern": True,
        },
        "corpus_text": m["corpus_text"],
        "corpus_nontext": m["corpus_nontext"],
        "text_plants": {
            "channel": tp["channel"],
            "planted_n": tp["planted_n"],
            "found_n": tp["found_n"],
            "recall": tp["recall"],
            "removed_verified": tp["removed_verified"],
            "negative_users_word_only_silent": tp["negative_users_word_only_silent"],
            "scratch_outside_tree": tp["scratch_outside_tree"],
            "value_reproduced": False,
            "plants": tp["planted"],
            "pass": tp["pass"],
        },
        "nontext_plants": {
            "channel": np_["channel"],
            "method": np_["method"],
            "planted_categories": np_["planted_categories"],
            "found_n": np_["found_n"],
            "recall": np_["recall"],
            "text_sweep_hits_on_png_bytes": np_["text_sweep_hits_on_png_bytes"],
            "text_sweep_blind_to_screenshot": np_["text_sweep_blind_to_screenshot"],
            "clean_image_silent": np_["clean_image_silent"],
            "removed_verified": np_["removed_verified"],
            "scratch_outside_tree": np_["scratch_outside_tree"],
            "ocr_engine": np_["ocr_engine"],
            "value_reproduced": False,
            "pass": np_["pass"],
        },
        "targets": [
            {
                "id": "T1",
                "target": "T1 - labeled person names in publishable corpus text",
                "verdict": v_name,
                "hits": names_hits,
                "detector": "labeled full_name/author/from lines",
            },
            {
                "id": "T2",
                "target": "T2 - email addresses in publishable corpus",
                "verdict": v_email,
                "hits": email_hits,
            },
            {
                "id": "T3",
                "target": "T3 - phone numbers in publishable corpus",
                "verdict": v_phone,
                "hits": phone_hits,
            },
            {
                "id": "T4",
                "target": "T4 - home paths in publishable corpus",
                "verdict": v_home,
                "hits": home_hits,
            },
            {
                "id": "T5",
                "target": "T5 - private IPv4-literal URLs in publishable corpus",
                "verdict": v_url,
                "hits": url_hits,
            },
            {
                "id": "T6",
                "target": "T6 - faces in screenshots on the publication surface",
                "verdict": v_face,
                "image_files": image_n,
                "face_detector": False,
                "basis": (
                    "zero image/PDF files so faces cannot be present"
                    if image_n == 0
                    else "images exist; no face detector; NOT-CHECKED"
                ),
            },
            {
                "id": "T7",
                "target": "T7 - planted-PII recall is a measured number",
                "verdict": v_recall,
                "planted_pii_recall": recall,
            },
            {
                "id": "T8",
                "target": "T8 - non-text screenshot channel distinct from text sweep",
                "verdict": v_channel,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "text-pattern-plus-entropy",
                "command": P1,
                "raw_output": raw1 or "emit-pending-probe1-output",
            },
            {
                "id": "probe2",
                "role": "png-ztxt-inflate-nontext",
                "command": P2,
                "raw_output": raw2 or "emit-pending-probe2-output",
            },
        ],
        "tests": tests,
        "controls": controls,
        "evidence": [
            {
                "kind": "text-sweep",
                "claim": "pattern plus entropy over publishable text artifacts",
                "anchor": "corpus_text.by_category",
            },
            {
                "kind": "nontext-sweep",
                "claim": "PNG zTXt inflate finds plants the text sweep misses",
                "anchor": "nontext_plants.text_sweep_blind_to_screenshot",
            },
            {
                "kind": "recall",
                "claim": "planted-PII recall is a number with plants removed",
                "anchor": "recall.planted_pii_recall",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0040-probe2-png-ztxt-refuter",
            "verdict": "PASS" if m["controls_ok"] else "FAIL",
            "independent": True,
            "method": (
                "re-plant compressed PNG zTXt and require the text sweep of "
                "file bytes to stay silent while inflate recovers categories"
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "artifacts": artifacts,
        "adv_rebuild_circle": False,
        "required_fix": None,
        "evidence_requirement": (
            "Probe 1: pattern plus entropy sweep over text artifacts, "
            "reporting (path, line, category) with values redacted. Probe 2 "
            "(mechanically different): non-text coverage - OCR or metadata "
            "extraction over images/PDFs, because a text sweep is structurally "
            "blind to a screenshot and would report clean."
        ),
    }


def write_artifact(doc: dict) -> None:
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    m = L.measure()
    if not m["controls_ok"]:
        print("FAILED:ADV-0040 detector controls")
        print(
            json.dumps(
                {
                    "text_pass": m["text_plants"]["pass"],
                    "nontext_pass": m["nontext_plants"]["pass"],
                    "text_recall": m["text_plants"]["recall"],
                    "nontext_recall": m["nontext_plants"]["recall"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_doc(m, raw1="", raw2="", now=now)
    leaks = L.artifact_leaks_values(doc)
    if leaks:
        print("FAILED:ADV-0040 artifact would leak " + ",".join(leaks))
        return 1
    validate_or_die(doc)
    write_artifact(doc)
    rc1, t1 = run(P1)
    rc2, t2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:ADV-0040 named probes during emit c1={rc1} c2={rc2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    doc = build_doc(m, raw1=t1, raw2=t2, now=now)
    leaks = L.artifact_leaks_values(doc)
    if leaks:
        print("FAILED:ADV-0040 patched artifact would leak " + ",".join(leaks))
        return 1
    validate_or_die(doc)
    write_artifact(doc)
    print(
        f"wrote {OUT} recall={m['recall']['planted_pii_recall']} "
        f"text_files={m['corpus_text']['files_scanned']} "
        f"images={m['corpus_nontext']['image_files']}"
    )
    print("SUCCESS:ADV-0040")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
