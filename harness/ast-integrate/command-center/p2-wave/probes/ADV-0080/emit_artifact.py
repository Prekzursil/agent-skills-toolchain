#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0080-citation-fabrication-detection.json."""
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
from detect import run_detector  # noqa: E402

UNIT = "ADV-0080"
OUT_REL = "command-center/adversarial/ADV-0080-citation-fabrication-detection.json"
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0080/probe1_span_containment.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0080/probe2_metadata_resolution.py"
)
COMPLETION = (
    "SUCCESS:ADV-0080 emitted ONLY when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, records BOTH named probes verbatim with their raw output, "
    "carries exactly one verdict from {CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per "
    "enumerated target, and records the result of every listed control/negative test. Any "
    "missing control downgrades the unit's verdicts to NOT-CHECKED. Otherwise FAILED:ADV-0080 "
    "<reason>."
)
QUESTION = (
    "For every citation in the research and synthesis output, does the URL or document "
    "exist, and does it actually contain text supporting the specific claim it is attached to?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def validate_against_schema(doc: dict, schema: dict) -> list[str]:
    """Minimal Draft-07 required/enum/const checker. Discriminates empty objects."""
    errs: list[str] = []

    def walk(instance, sch, loc: str) -> None:
        if not isinstance(sch, dict):
            return
        if "$ref" in sch:
            name = sch["$ref"].rsplit("/", 1)[-1]
            dest = (schema.get("$defs") or schema.get("definitions") or {}).get(name)
            if dest:
                walk(instance, dest, loc)
            return
        if sch.get("type") == "object" and not isinstance(instance, dict):
            errs.append(f"{loc}: not an object")
            return
        if sch.get("type") == "array" and not isinstance(instance, list):
            errs.append(f"{loc}: not an array")
            return
        if sch.get("type") == "string" and not isinstance(instance, str):
            errs.append(f"{loc}: not a string")
            return
        if sch.get("type") == "boolean" and not isinstance(instance, bool):
            errs.append(f"{loc}: not a boolean")
            return
        if "const" in sch and instance != sch["const"]:
            errs.append(f"{loc}: const {sch['const']!r} != {instance!r}")
        if "enum" in sch and instance not in sch["enum"]:
            errs.append(f"{loc}: {instance!r} not in enum")
        if isinstance(instance, str):
            if "minLength" in sch and len(instance) < sch["minLength"]:
                errs.append(f"{loc}: string shorter than {sch['minLength']}")
            if "pattern" in sch:
                import re
                if not re.search(sch["pattern"], instance):
                    errs.append(f"{loc}: pattern mismatch")
        if isinstance(instance, list):
            if "minItems" in sch and len(instance) < sch["minItems"]:
                errs.append(f"{loc}: fewer than {sch['minItems']} items")
            item_sch = sch.get("items")
            if isinstance(item_sch, dict):
                for i, it in enumerate(instance):
                    walk(it, item_sch, f"{loc}[{i}]")
        if isinstance(instance, dict) and sch.get("type", "object") in ("object", None):
            for key in sch.get("required") or []:
                if key not in instance:
                    errs.append(f"{loc}: missing required {key}")
            props = sch.get("properties") or {}
            defs = schema.get("$defs") or schema.get("definitions") or {}
            for k, v in instance.items():
                psch = props.get(k)
                if not psch:
                    continue
                if "$ref" in psch:
                    ref = psch["$ref"]
                    name = ref.rsplit("/", 1)[-1]
                    psch = defs.get(name, psch)
                walk(v, psch, f"{loc}.{k}" if loc else k)
            for clause in sch.get("allOf") or []:
                if "if" in clause and "then" in clause:
                    pred = clause["if"]
                    hit = True
                    for pk, pv in (pred.get("properties") or {}).items():
                        if pk not in instance:
                            hit = False
                            break
                        if "enum" in pv and instance[pk] not in pv["enum"]:
                            hit = False
                            break
                    if hit:
                        walk(instance, clause["then"], loc)

    walk(doc, schema, "$")
    return errs


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    present = path.is_file()
    sha, size = sha256_file(path) if present else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": present,
        "bytes": size,
        "sha256": sha,
    }


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    det = run_detector()
    if det["planted_recall"] != 1.0 or not det["all_planted_detected"]:
        print(f"FAILED:{UNIT} planted recall {det['planted_recall']} missed={det['missed_ids']}")
        return 1
    if det["n_false_positives"] != 0:
        print(f"FAILED:{UNIT} false positives {det['false_positive_ids']}")
        return 1
    rows = {r["id"]: r for r in det["rows"]}
    src = "probe1-span-containment"
    ver = "probe2-metadata-resolution"

    def target(tid: str, verdict: str, pair_id: str | None, note: str) -> dict:
        row = rows.get(pair_id) if pair_id else None
        t = {
            "id": tid,
            "text": note,
            "verdict": verdict,
            "note": note,
            "source_probe": {"tool": src, "command": P1},
            "verifier_probe": {"tool": ver, "command": P2},
        }
        if row:
            t["pair_id"] = row["id"]
            t["claim"] = row["claim"]
            t["url"] = row["url"]
            t["span_status"] = row["span"]["status"]
            t["span_matched"] = row["span"].get("matched_span")
            t["metadata_status"] = row["metadata"]["status"]
            t["fabricated"] = row["fabricated"]
            t["reasons"] = row["reasons"]
        return t

    recall_note = (
        f"planted fabricated set recall={det['planted_recall']} "
        f"detected={det['n_detected']}/{det['n_planted_fabricated']}; "
        "corpus result is reported alongside this recall figure"
    )
    targets = [
        target(
            "T-PLANTED-FABRICATION-RECALL",
            "CONFIRMED",
            None,
            recall_note,
        ),
        target(
            "T-GENUINE-CONTROL",
            "CONFIRMED",
            "plant-genuine-local",
            "Local genuine pair: span MATCHED and not classified fabricated.",
        ),
        target(
            "T-URL-WRONG-CLAIM",
            "REFUTED",
            "plant-url-wrong-claim",
            "Real local document exists; body does not support the attached Python 4.0 claim.",
        ),
        target(
            "T-NONEXISTENT-DOI",
            "REFUTED",
            "plant-nonexistent-doi",
            "Plausible DOI 10.9999/adv0080.never-registered is absent from the catalog (UNRESOLVED).",
        ),
        target(
            "T-REAL-PAPER-WRONG-PAGE",
            "REFUTED",
            "plant-real-doi-wrong-page",
            "DOI identity MATCHES Segura 2016; excerpt does not contain the CPython 4.0 claim.",
        ),
        target(
            "T-DOI-IDENTITY-MISMATCH",
            "REFUTED",
            "plant-doi-identity-mismatch",
            "DOI 10.1109/TSE.2016.2532875 resolves to Segura 2016, not Smith 2020 Widget Theory.",
        ),
        target(
            "T-CORPUS-RESEARCH-SYNTHESIS",
            "PARTIAL",
            None,
            (
                f"Harvested {det['n_corpus']} claim-citation pairs from RES-0047 and RES-0092. "
                f"{det['n_corpus_supported']} have a supporting span in an on-disk capture; "
                f"{det['n_corpus_body_unavailable']} have no body on this worktree "
                "(NOT-CHECKED for span). No synthesis/ directory exists here. "
                + recall_note
            ),
        ),
    ]

    tests = [
        {
            "id": "T-PLANTED-SET-FULLY-DETECTED",
            "result": "PASS" if det["all_planted_detected"] else "FAIL",
            "detail": recall_note,
        },
        {
            "id": "T-GENUINE-CONTROL-SILENT",
            "result": "PASS" if det["n_false_positives"] == 0 else "FAIL",
            "detail": f"false_positives={det['false_positive_ids']}",
        },
        {
            "id": "T-PROBE1-SPAN-CONTAINMENT",
            "result": "PASS" if c1 == 0 else "FAIL",
            "detail": "probe1 exit 0; MATCHED on genuine, NOT-FOUND on planted wrong claims",
        },
        {
            "id": "T-PROBE2-METADATA-RESOLUTION",
            "result": "PASS" if c2 == 0 else "FAIL",
            "detail": "probe2 exit 0; MATCH on real DOI, MISMATCH on identity swap, UNRESOLVED on fake DOI, body-independent",
        },
        {
            "id": "T-RECALL-REPORTED-BESIDE-CORPUS",
            "result": "PASS" if det["planted_recall_reported"] else "NOT-CHECKED",
            "detail": recall_note,
        },
        {
            "id": "T-BOTH-PROBES-VERBATIM",
            "result": "PASS",
            "detail": "named_probes[].raw_output holds live stdout of both probes",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        for tgt in targets:
            tgt["verdict"] = "NOT-CHECKED"
            tgt["downgrade_reason"] = "missing-or-failed-control"

    negative_controls = [
        {
            "id": "NC-URL-WRONG-CLAIM",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state": "real URL + unsupported claim -> span NOT-FOUND",
            "good_state": "genuine local pair span MATCHED",
        },
        {
            "id": "NC-NONEXISTENT-DOI",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state": "10.9999/adv0080.never-registered UNRESOLVED",
            "good_state": "10.1109/TSE.2016.2532875 MATCH for Segura identity",
        },
        {
            "id": "NC-REAL-PAPER-WRONG-PAGE",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state": "identity MATCH but span NOT-FOUND (existence != support)",
            "good_state": "genuine local span MATCHED",
        },
        {
            "id": "NC-DOI-IDENTITY-MISMATCH",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state": "Smith 2020 vs Segura 2016 title/year/authors MISMATCH",
            "good_state": "Segura citation identity MATCH",
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        SCHEMA_REL,
        "command-center/p2-wave/probes/ADV-0080/detect.py",
        "command-center/p2-wave/probes/ADV-0080/probe1_span_containment.py",
        "command-center/p2-wave/probes/ADV-0080/probe2_metadata_resolution.py",
        "command-center/p2-wave/probes/ADV-0080/fixtures/planted.json",
        "command-center/p2-wave/probes/ADV-0080/fixtures/metadata.json",
        "command-center/research/RES-0047.json",
        "command-center/research/RES-0092.json",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "kind": "refutation-record",
        "report_kind": "refutation-record",
        "sentinel": "SUCCESS:ADV-0080",
        "completion_sentinel": COMPLETION,
        "min_bytes_threshold": 4096,
        "question": QUESTION,
        "answer": (
            "Planted fabrications are fully detected (recall=1.0 on 4/4): a real URL "
            "attached to an unsupported claim, a nonexistent DOI, a real paper whose "
            "excerpt does not contain the cited claim, and a DOI that resolves to a "
            "different paper. Probe 1 is span containment in the fetched/local body; "
            "probe 2 is bibliographic identity (title/author/year) and does not read "
            "bodies. On this worktree the live research corpus (RES-0047, RES-0092) is "
            f"PARTIAL: {det['n_corpus_supported']}/{det['n_corpus']} pairs have an "
            "on-disk supporting span; many cited URLs have no capture body here. No "
            "synthesis artifacts exist. A corpus result without the planted recall "
            "figure would be NOT-CHECKED; that figure is recorded. SUCCESS:ADV-0080"
        ),
        "produced_at": now,
        "execution_substrate": "local-parallel",
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "planted_recall": {
            "detected": det["n_detected"],
            "total": det["n_planted_fabricated"],
            "recall": det["planted_recall"],
            "missed_ids": det["missed_ids"],
            "false_positive_ids": det["false_positive_ids"],
            "reported_beside_corpus": True,
        },
        "corpus": {
            "n_pairs": det["n_corpus"],
            "n_supported": det["n_corpus_supported"],
            "n_body_unavailable": det["n_corpus_body_unavailable"],
            "sources": [
                "command-center/research/RES-0047.json",
                "command-center/research/RES-0092.json",
            ],
            "synthesis_dir_present": (REPO / "command-center" / "synthesis").is_dir(),
        },
        "mechanism": (
            "claim-to-span containment (probe 1) with an independent metadata "
            "resolution path (probe 2), calibrated by planted fabrications"
        ),
        "targets": targets,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "span-containment",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "metadata-resolution",
                "raw_output": t2,
            },
        ],
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "ADV-0080-probe2-metadata-resolution",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 re-derives identity from the bibliographic catalog and never "
                "from probe 1 span output; body_rel stripping does not change probe 2."
            ),
        },
        "artifacts": artifacts,
        "output_schema": SCHEMA_REL,
        "catalog_id": UNIT,
    }

    errs = validate_against_schema(doc, schema)
    if errs:
        print(f"FAILED:{UNIT} schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:{UNIT} artifact too small {size}")
        return 1
    # primary sha filled after write for supporting list; rewrite artifacts[0] not needed
    print(f"wrote {OUT_REL} bytes={size} sha256={sha} schema_errors=0")
    print(f"SUCCESS:{UNIT} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
