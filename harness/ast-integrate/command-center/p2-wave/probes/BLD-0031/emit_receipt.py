#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0031.json and validate the schema."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

OUT_REL = "command-center/receipts/BLD-0031.json"
SCHEMA_REL = "command-center/schema/tag-position-audit.schema.json"
QUESTION = (
    "Which forward-looking claim ships with no calibrated confidence band, or "
    "carries a band with no paired evidence anchor? This unit contributes the "
    "MISSING-band population — claims carrying no band at all — which a "
    "band-versus-evidence audit (ADV-0108) structurally cannot see."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0031/probe1_lexicon_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0031/probe2_blind_rescore.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def present(rel: str) -> bool:
    return (REPO / rel).is_file()


def artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    exists = path.is_file()
    rec = {"path": rel, "exists": True if exists else False, "role": role}
    if exists:
        sha, size = sha256_file(path)
        rec["sha256"] = sha
        rec["bytes"] = size
    return rec


def validate(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"totally": "unrelated"}, {"unit_id": "NOPE"}):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:BLD-0031 schema accepts garbage")


def main() -> int:
    ctrls = A.control_sentences(HERE / "fixtures" / "controls.md")
    c_miss = A.classify_lexicon(ctrls["CONTROL-MISSING-BAND"])
    c_ok = A.classify_lexicon(ctrls["CONTROL-COMPLIANT"])
    c_err = A.classify_lexicon(ctrls["CONTROL-CATEGORY-ERROR"])
    if c_miss["class"] != "MISSING-BAND":
        print(f"FAILED:BLD-0031 control missing-band -> {c_miss}")
        return 1
    if c_ok["class"] != "COMPLIANT":
        print(f"FAILED:BLD-0031 control compliant -> {c_ok}")
        return 1
    if c_err["class"] != "CATEGORY-ERROR":
        print(f"FAILED:BLD-0031 control category-error -> {c_err}")
        return 1

    sample = A.load_sample20(HERE / "fixtures" / "sample20.md")
    lex_n = sum(int(A.flagged(A.classify_lexicon(r["text"]))) for r in sample)
    mod_n = sum(int(A.flagged(A.classify_modality(r["text"]))) for r in sample)
    delta = abs(lex_n - mod_n)
    if len(sample) != 20 or delta > 2:
        print(f"FAILED:BLD-0031 reviewer sample n={len(sample)} delta={delta}")
        return 1

    rows = A.scan_corpus(REPO, method="lexicon")
    findings = []
    unflagged = []
    for rec in rows:
        klass = rec["class"]
        item = {
            "id": f"{rec['path']}:{rec['line']}",
            "quote": rec["quote"],
            "class": klass if klass != "COMPLIANT" else "MISSING-BAND",
            "path": rec["path"],
            "line": rec["line"],
            "band": rec.get("band"),
            "evidence_tag": rec.get("evidence_tag"),
            "method": rec.get("method"),
            "bare_hedge": rec.get("bare_hedge"),
        }
        if klass in A.FLAGGED:
            item["class"] = "MISSING-BAND" if klass == "BARE-HEDGE" else klass
            findings.append(item)
        elif klass == "COMPLIANT":
            item["class"] = "COMPLIANT"
            unflagged.append(item)

    # findings.class cannot be COMPLIANT (schema enum for defects)
    findings_out = []
    for i, f in enumerate(findings, 1):
        row = {
            "id": f"F{i:04d}",
            "quote": f["quote"],
            "class": f["class"],
            "path": f["path"],
            "line": f["line"],
            "band": f.get("band"),
            "evidence_tag": f.get("evidence_tag"),
            "bare_hedge": bool(f.get("bare_hedge")),
            "method": "lexicon",
        }
        findings_out.append(row)

    counts = {
        "units_scanned": len(rows),
        "forward_or_uncertain": sum(
            1 for r in rows if r["class"] != "NOT-CLAIM"
        ),
        "missing_band": sum(1 for r in rows if r["class"] == "MISSING-BAND"),
        "category_error": sum(1 for r in rows if r["class"] == "CATEGORY-ERROR"),
        "compliant": sum(1 for r in rows if r["class"] == "COMPLIANT"),
        "banded_no_evidence": sum(
            1 for r in rows if r["class"] == "BANDED-NO-EVIDENCE"
        ),
        "not_claim": sum(1 for r in rows if r["class"] == "NOT-CLAIM"),
        "findings_emitted": len(findings_out),
    }

    claim_reg = "command-center/CLAIM-REGISTRY.json"
    agents = "AGENTS.md"
    input_status = [
        {
            "path": claim_reg,
            "present": present(claim_reg),
            "role": "claim-id join",
            "note": "absent on this worktree; findings are path:line quotes, not registry ids",
        },
        {
            "path": agents,
            "present": present(agents),
            "role": "confidence lexicon",
            "note": "AGENTS.md 7 absent; Sherman-Kent set taken from the catalog unit text",
        },
        {
            "path": "command-center/receipts/",
            "present": (REPO / "command-center" / "receipts").is_dir(),
            "role": "lane receipt narratives",
            "note": "directory created by this unit if missing; sibling BLD receipts may be absent",
        },
    ]

    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)

    supporting = [
        SCHEMA_REL,
        "command-center/p2-wave/probes/BLD-0031/audit.py",
        "command-center/p2-wave/probes/BLD-0031/fixtures/controls.md",
        "command-center/p2-wave/probes/BLD-0031/fixtures/sample20.md",
        "command-center/p2-wave/probes/BLD-0031/probe1_lexicon_controls.py",
        "command-center/p2-wave/probes/BLD-0031/probe2_blind_rescore.py",
    ]
    artifacts = [artifact(p, "supporting") for p in supporting]
    for a in artifacts:
        if a["exists"] is not True:
            print(f"FAILED:BLD-0031 missing supporting {a['path']}")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "BLD-0031",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0031",
        "kind": "tag-position-audit",
        "audit_focus": "confidence-band-and-evidence-tag",
        "schema_version": 1,
        "ts": now,
        "question": QUESTION,
        "scope_boundary": (
            "ADV-0108 audits unsupported certainty (stated band versus evidence). "
            "BLD-0031 reports the MISSING-band population and the CATEGORY-ERROR "
            "class (a band attached to a past measured fact)."
        ),
        "sherman_kent_bands": list(A.SHERMAN_KENT),
        "evidence_requirement": (
            "Each finding quotes the hedged sentence. A band attached to a PAST "
            "measured fact is a category error and is reported in a separate class "
            "from a missing band."
        ),
        "input_status": input_status,
        "counts": counts,
        "findings": findings_out,
        "unflagged": [
            {
                "quote": u["quote"],
                "class": "COMPLIANT",
                "path": u["path"],
                "line": u["line"],
                "band": u.get("band"),
                "evidence_tag": u.get("evidence_tag"),
            }
            for u in unflagged
        ],
        "tests": [
            {
                "id": "control-should-work",
                "name": "bare should work with no band is caught",
                "command": P1,
                "result": "PASS",
                "observed_class": c_miss["class"],
            },
            {
                "id": "control-banded-evidence",
                "name": "likely (55-80%), measured at path:line is unflagged",
                "command": P1,
                "result": "PASS",
                "observed_class": c_ok["class"],
            },
            {
                "id": "control-category-error",
                "name": "past-tense measured fact plus band is CATEGORY-ERROR",
                "command": P1,
                "result": "PASS",
                "observed_class": c_err["class"],
            },
            {
                "id": "reviewer-blind-rescore",
                "name": "twenty sampled claims, flagged counts agree within two",
                "command": P2,
                "result": "PASS",
                "lexicon_flagged": lex_n,
                "modality_flagged": mod_n,
                "abs_delta": delta,
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0031-probe2-modality-blind-rescore",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "sampled_n": 20,
            "lexicon_flagged": lex_n,
            "modality_flagged": mod_n,
            "abs_delta": delta,
            "must_agree_within": 2,
            "method": "modality tagging (numeric ranges + modals), not Sherman-Kent tokens",
        },
        "artifacts": artifacts
        + [
            {
                "path": OUT_REL,
                "exists": True,
                "role": "primary",
            }
        ],
        "method": {
            "primary": "lexicon matching of Sherman-Kent bands and catalog bare hedges",
            "independent": "modality tagging of modals / future register / (N-M%) ranges",
            "retry_policy": "two strikes then pivot from lexicon matching to modality tagging",
            "adv_rebuild_circle": False,
        },
    }
    validate(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha} findings={len(findings_out)}")
    print("SUCCESS:BLD-0031 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
