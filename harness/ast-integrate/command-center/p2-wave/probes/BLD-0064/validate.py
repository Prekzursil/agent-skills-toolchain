#!/usr/bin/env python3
"""Residual-risk ledger validator and BLD-0001..0063 finding extractor.

Counts are re-derived from receipts on disk. BLD-0064 is never a source.
An agent-signed acceptance is invalid. Unassigned findings fail closed.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
# Catalog-declared path is a generated $ref shim. jsonschema follows that $ref
# onto the network (ast-integrate.invalid) and crashes. Domain constraints live
# next to this validator.
CATALOG_SCHEMA_REL = "command-center/schema/residual-risk-ledger.schema.json"
DOMAIN_SCHEMA_REL = "command-center/p2-wave/probes/BLD-0064/ledger.schema.json"
SCHEMA_REL = DOMAIN_SCHEMA_REL
LIVE_LEDGER_REL = "command-center/receipts/BLD-0064.json"
LIVE_RECEIPTS_REL = "command-center/receipts"
SOURCE_UNITS = [f"BLD-{i:04d}" for i in range(1, 64)]
DISPOSITIONS = (
    "NEW-WORK-UNIT",
    "ACCEPTED-RESIDUAL-RISK",
    "RESOLVED",
)
FINDING_LIST_KEYS = (
    "findings",
    "residual_risks",
    "residual_unknowns",
    "blind_spots",
    "uncovered_questions",
    "contradictions",
)
COVERED_STATUSES = {"COVERED", "CONFIRMED", "REFUTED", "RESOLVED"}
AGENT_ID_RE = re.compile(
    r"(agent|subagent|claude|anthropic|gpt-|openai|gemini|sonnet|opus|cursor)",
    re.I,
)
AGENT_KINDS = {"agent-signed", "agent", "llm", "model", "subagent"}
OWNER_KINDS = {"owner-signature", "owner-decision-record"}
UNIT_ID_RE = re.compile(r"^[A-Z]{2,5}-[0-9]{4}$")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return exc


def _item_status(item: dict) -> str:
    for key in ("status", "coverage", "verdict", "state"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().upper()
    return ""


def coerce_finding(unit_id: str, source_path: str, key: str, idx: int, item):
    if isinstance(item, str):
        text = item.strip()
        if len(text) < 8:
            return None
        return {
            "id": f"{unit_id}:{key}:{idx}",
            "source_unit_id": unit_id,
            "source_path": source_path,
            "source_key": key,
            "summary": text[:500],
        }
    if not isinstance(item, dict):
        return None
    if key == "uncovered_questions" and _item_status(item) in COVERED_STATUSES:
        return None
    summary = (
        item.get("summary")
        or item.get("finding")
        or item.get("question")
        or item.get("claim")
        or item.get("title")
        or item.get("text")
    )
    if not isinstance(summary, str) or len(summary.strip()) < 8:
        try:
            summary = json.dumps(item, sort_keys=True)[:300]
        except (TypeError, ValueError):
            return None
        if len(summary) < 8:
            return None
    raw_id = item.get("id")
    fid = (
        str(raw_id).strip()
        if isinstance(raw_id, str) and raw_id.strip()
        else f"{unit_id}:{key}:{idx}"
    )
    row = {
        "id": fid,
        "source_unit_id": unit_id,
        "source_path": source_path,
        "source_key": key,
        "summary": summary.strip()[:500],
    }
    kind = item.get("kind")
    if isinstance(kind, str) and kind.strip():
        row["kind"] = kind.strip().upper()
    return row


def extract_from_doc(unit_id: str, source_path: str, doc) -> list:
    if not isinstance(doc, dict):
        return []
    out = []
    seen = set()
    for key in FINDING_LIST_KEYS:
        raw = doc.get(key)
        if not isinstance(raw, list):
            continue
        for idx, item in enumerate(raw):
            row = coerce_finding(unit_id, source_path, key, idx, item)
            if row is None:
                continue
            if row["id"] in seen:
                row = dict(row)
                row["id"] = f"{row['id']}#{idx}"
            seen.add(row["id"])
            out.append(row)
    return out


def census_and_extract(receipts_dir: Path, repo: Path | None = None):
    repo = repo or REPO
    try:
        rel_dir = receipts_dir.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        rel_dir = str(receipts_dir)
    present = []
    absent = []
    findings = []
    for uid in SOURCE_UNITS:
        path = receipts_dir / f"{uid}.json"
        if not path.is_file() or path.stat().st_size <= 0:
            absent.append(uid)
            continue
        doc = load_json(path)
        if isinstance(doc, Exception):
            absent.append(uid)
            continue
        present.append(uid)
        try:
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
        findings.extend(extract_from_doc(uid, rel, doc))
    census = {
        "source_unit_ids": list(SOURCE_UNITS),
        "expected_count": 63,
        "present_count": len(present),
        "absent_count": len(absent),
        "present_ids": present,
        "absent_ids": absent,
        "finding_count_from_receipts": len(findings),
        "receipts_dir": rel_dir,
        "derived_from_disk": True,
    }
    return findings, census


def load_schema():
    doc = load_json(REPO / SCHEMA_REL)
    if isinstance(doc, Exception) or not isinstance(doc, dict):
        raise SystemExit(f"FAILED:BLD-0064 schema unreadable: {doc}")
    return doc


def schema_errors(ledger: dict):
    import jsonschema

    try:
        validator = jsonschema.Draft7Validator(load_schema())
        return [
            f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
            for err in validator.iter_errors(ledger)
        ]
    except jsonschema.exceptions.RefResolutionError as exc:
        return [f"schema $ref unresolved (fail closed): {exc}"]


def _acceptance_errors(fid: str, acc):
    if not isinstance(acc, dict):
        return [f"{fid}: ACCEPTED-RESIDUAL-RISK missing owner-attributable acceptance object"]
    errs = []
    owner = acc.get("owner_id")
    if not isinstance(owner, str) or not owner.strip():
        errs.append(f"{fid}: acceptance record has no owner attribution")
    elif AGENT_ID_RE.search(owner):
        errs.append(f"{fid}: agent-signed acceptance is invalid (owner_id={owner!r})")
    kind = str(acc.get("attribution_kind") or "").strip()
    if not kind:
        errs.append(f"{fid}: acceptance record has no attribution_kind")
    elif kind in AGENT_KINDS or kind not in OWNER_KINDS:
        errs.append(f"{fid}: agent-signed acceptance is invalid (attribution_kind={kind!r})")
    if acc.get("agent_signed") is True:
        errs.append(f"{fid}: agent-signed acceptance is invalid (agent_signed=true)")
    return errs


def semantic_errors(ledger: dict, receipts_dir: Path):
    errs = []
    if not isinstance(ledger, dict):
        return ["ledger is not an object"]
    if str(ledger.get("unit_id") or "") != "BLD-0064":
        errs.append("unit_id must be BLD-0064")
    extracted, census = census_and_extract(receipts_dir)
    extracted_ids = [row["id"] for row in extracted]
    findings = ledger.get("findings")
    if not isinstance(findings, list):
        errs.append("findings must be an array")
        findings = []
    ledger_ids = []
    unassigned = []
    tallies = {d: 0 for d in DISPOSITIONS}
    for i, row in enumerate(findings):
        if not isinstance(row, dict):
            errs.append(f"findings[{i}] is not an object")
            unassigned.append(f"<index:{i}>")
            continue
        fid = str(row.get("id") or f"<index:{i}>")
        ledger_ids.append(fid)
        src = str(row.get("source_unit_id") or "")
        if src == "BLD-0064":
            errs.append(f"{fid}: self-reference; BLD-0064 is not a source unit")
        elif src not in SOURCE_UNITS:
            errs.append(f"{fid}: source_unit_id {src!r} is outside BLD-0001..BLD-0063")
        disp = row.get("disposition")
        if disp not in DISPOSITIONS:
            unassigned.append(fid)
            errs.append(f"{fid}: finding has no valid disposition")
            continue
        tallies[disp] += 1
        if disp == "NEW-WORK-UNIT":
            alloc = row.get("allocated_unit_id")
            if not isinstance(alloc, str) or not UNIT_ID_RE.match(alloc):
                errs.append(f"{fid}: NEW-WORK-UNIT requires allocated_unit_id")
        elif disp == "ACCEPTED-RESIDUAL-RISK":
            exp = row.get("settling_experiment")
            if not isinstance(exp, str) or len(exp.strip()) < 8:
                errs.append(f"{fid}: residual risk has no named settling experiment")
            impact = row.get("impact_statement")
            if not isinstance(impact, str) or len(impact.strip()) < 8:
                errs.append(f"{fid}: residual risk has no owner-visible impact statement")
            errs.extend(_acceptance_errors(fid, row.get("acceptance")))
        elif disp == "RESOLVED":
            ev = row.get("evidence")
            if not isinstance(ev, str) or len(ev.strip()) < 8:
                errs.append(f"{fid}: RESOLVED finding lacks evidence")
    if len(findings) != len(extracted):
        errs.append(
            "recount mismatch: ledger findings="
            f"{len(findings)} disk={len(extracted)}"
        )
    if ledger_ids != extracted_ids:
        errs.append(
            "recount mismatch: ledger ids "
            f"{ledger_ids} != disk ids {extracted_ids}"
        )
    claimed = ledger.get("counts") if isinstance(ledger.get("counts"), dict) else {}
    if claimed.get("findings") != len(findings):
        errs.append("counts.findings does not match findings array length")
    if claimed.get("unassigned") != len(unassigned):
        errs.append("counts.unassigned does not match unassigned finding count")
    for disp in DISPOSITIONS:
        if claimed.get(disp) != tallies[disp]:
            errs.append(f"counts.{disp} does not match dispositions on disk-derived rows")
    if ledger.get("unassigned_finding_ids") != unassigned:
        errs.append("unassigned_finding_ids does not match computed unassigned set")
    rc = ledger.get("receipt_census") if isinstance(ledger.get("receipt_census"), dict) else {}
    if rc.get("finding_count_from_receipts") != len(extracted):
        errs.append("receipt_census.finding_count_from_receipts disagrees with disk")
    if rc.get("present_count") != census["present_count"]:
        errs.append("receipt_census.present_count disagrees with disk")
    if rc.get("absent_count") != census["absent_count"]:
        errs.append("receipt_census.absent_count disagrees with disk")
    if rc.get("present_ids") != census["present_ids"]:
        errs.append("receipt_census.present_ids disagrees with disk")
    if rc.get("derived_from_disk") is not True:
        errs.append("receipt_census.derived_from_disk must be true")
    if unassigned:
        errs.append(f"unassigned findings block: {unassigned}")
    sign = ledger.get("owner_signoff") if isinstance(ledger.get("owner_signoff"), dict) else {}
    if sign.get("forged_by_agent") is True:
        errs.append("owner_signoff.forged_by_agent must be false")
    if tallies["ACCEPTED-RESIDUAL-RISK"] > 0 and sign.get("present") is not True:
        errs.append("ACCEPTED-RESIDUAL-RISK rows require a present owner sign-off")
    if str(ledger.get("state") or "").upper() == "SUCCESS" and unassigned:
        errs.append("state=SUCCESS is invalid while findings remain unassigned")
    return errs


def validate_ledger(ledger: dict, receipts_dir: Path):
    errs = schema_errors(ledger)
    errs.extend(semantic_errors(ledger, receipts_dir))
    seen = set()
    out = []
    for err in errs:
        if err not in seen:
            seen.add(err)
            out.append(err)
    return out


def validate_path(ledger_path: Path, receipts_dir: Path):
    doc = load_json(ledger_path)
    if isinstance(doc, Exception):
        return [f"unparseable ledger: {type(doc).__name__}: {doc}"]
    if not isinstance(doc, dict):
        return ["ledger is not a JSON object"]
    return validate_ledger(doc, receipts_dir)


def _base_finding(fid: str, source_unit_id: str, summary: str) -> dict:
    return {
        "id": fid,
        "source_unit_id": source_unit_id,
        "source_path": f"command-center/receipts/{source_unit_id}.json",
        "source_key": "findings",
        "summary": summary,
    }


def good_fixture_rows():
    a = _base_finding(
        "BLD-0001:findings:0",
        "BLD-0001",
        "Unread schema files inside declared scope were never opened.",
    )
    a.update({"disposition": "NEW-WORK-UNIT", "allocated_unit_id": "IMP-9001"})
    b = _base_finding(
        "BLD-0001:findings:1",
        "BLD-0001",
        "Extractor glob missed subagent JSONL transcripts.",
    )
    b.update(
        {
            "disposition": "ACCEPTED-RESIDUAL-RISK",
            "settling_experiment": (
                "Plant one subagent JSONL outside the glob and prove the unread count moves."
            ),
            "impact_statement": (
                "An undercounted unread set can certify a clean bill while files stay unread."
            ),
            "acceptance": {
                "owner_id": "owner-human-fixture",
                "attribution_kind": "owner-signature",
                "agent_signed": False,
            },
        }
    )
    c = _base_finding(
        "BLD-0002:findings:0",
        "BLD-0002",
        "Planted orphan module is unreachable from every declared entry point.",
    )
    c.update(
        {
            "disposition": "RESOLVED",
            "evidence": "Reachability probe reported the planted orphan in the scratch copy.",
        }
    )
    return [a, b, c]


def write_fixture_receipts(receipts_dir: Path) -> None:
    receipts_dir.mkdir(parents=True, exist_ok=True)
    r1 = {
        "unit_id": "BLD-0001",
        "findings": [
            "Unread schema files inside declared scope were never opened.",
            "Extractor glob missed subagent JSONL transcripts.",
        ],
    }
    r2 = {
        "unit_id": "BLD-0002",
        "findings": [
            "Planted orphan module is unreachable from every declared entry point."
        ],
    }
    (receipts_dir / "BLD-0001.json").write_text(
        json.dumps(r1, indent=2) + "\n", encoding="utf-8"
    )
    (receipts_dir / "BLD-0002.json").write_text(
        json.dumps(r2, indent=2) + "\n", encoding="utf-8"
    )


def fixture_ledger_template():
    rows = good_fixture_rows()
    present = ["BLD-0001", "BLD-0002"]
    absent = [u for u in SOURCE_UNITS if u not in present]
    return {
        "unit_id": "BLD-0064",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0064",
        "question": (
            "Every material blind spot from BLD-0001 through BLD-0063 becomes "
            "a work unit or an explicitly accepted residual risk."
        ),
        "extraction_rule": (
            "Findings are the list items under findings/residual_risks/"
            "residual_unknowns/blind_spots/uncovered_questions/contradictions "
            "on BLD-0001..BLD-0063 receipts only; BLD-0064 is excluded."
        ),
        "receipt_census": {
            "source_unit_ids": list(SOURCE_UNITS),
            "expected_count": 63,
            "present_count": 2,
            "absent_count": 61,
            "present_ids": present,
            "absent_ids": absent,
            "finding_count_from_receipts": 3,
            "receipts_dir": "scratch-receipts",
            "derived_from_disk": True,
        },
        "findings": rows,
        "counts": {
            "findings": 3,
            "NEW-WORK-UNIT": 1,
            "ACCEPTED-RESIDUAL-RISK": 1,
            "RESOLVED": 1,
            "unassigned": 0,
        },
        "unassigned_finding_ids": [],
        "owner_signoff": {
            "required_for_accepted_residual_risk": True,
            "accepted_residual_risk_count": 1,
            "present": True,
            "forged_by_agent": False,
            "note": "Fixture owner-signature for validator controls only.",
        },
        "inputs_measured": {
            "risk_register": {
                "path": "command-center/RISK-REGISTER.md",
                "present": False,
            },
            "unknowns_register": {
                "path": "command-center/UNKNOWNS-REGISTER.md",
                "present": False,
            },
        },
        "tests": [
            {"id": "no-disposition", "command": "validate.py control", "result": "PASS"},
            {"id": "no-experiment", "command": "validate.py control", "result": "PASS"},
            {"id": "no-owner", "command": "validate.py control", "result": "PASS"},
            {"id": "recount", "command": "validate.py control", "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "BLD-0064-probe2-live-recount",
            "independent": True,
            "verdict": "PASS",
            "scope_not_agreement": True,
            "recount_match": True,
        },
        "evidence": [
            {
                "path": SCHEMA_REL,
                "line": 1,
                "snippet": "residual-risk-ledger",
                "kind": "schema",
                "claim": "schema file exists for this fixture",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0064/validate.py",
                "line": 1,
                "snippet": "SOURCE_UNITS",
                "kind": "validator",
                "claim": "extractor excludes BLD-0064",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": 1,
                "snippet": "BLD-0064",
                "kind": "catalog",
                "claim": "unit is catalogued",
            },
            {
                "path": "command-center/receipts",
                "line": 1,
                "snippet": "receipts",
                "kind": "census",
                "claim": "receipts directory is the recount root",
            },
        ],
        "artifacts": [
            {
                "path": "command-center/schema/residual-risk-ledger.schema.json",
                "exists": True,
                "role": "schema",
            }
        ],
    }


def run_catalog_controls(scratch: Path) -> dict:
    receipts = scratch / "receipts"
    write_fixture_receipts(receipts)
    good = fixture_ledger_template()
    results = {}

    def check(name, mutant, must_reject, needle):
        errs = validate_ledger(mutant, receipts)
        rejected = bool(errs)
        ok = rejected if must_reject else (not rejected)
        if ok and must_reject and needle:
            ok = any(needle in e for e in errs)
        results[name] = {
            "ok": ok,
            "rejected": rejected,
            "errors": errs[:8],
            "must_reject": must_reject,
        }

    check("good-fixture-accepted", copy.deepcopy(good), False, None)

    m1 = copy.deepcopy(good)
    del m1["findings"][0]["disposition"]
    m1["counts"]["unassigned"] = 1
    m1["unassigned_finding_ids"] = [m1["findings"][0]["id"]]
    m1["counts"]["NEW-WORK-UNIT"] = 0
    check("no-disposition", m1, True, "no valid disposition")

    m2 = copy.deepcopy(good)
    del m2["findings"][1]["settling_experiment"]
    check("no-settling-experiment", m2, True, "settling experiment")

    m3 = copy.deepcopy(good)
    m3["findings"][1]["acceptance"] = {
        "attribution_kind": "owner-signature",
        "agent_signed": False,
    }
    check("no-owner-attribution", m3, True, "no owner attribution")

    m3b = copy.deepcopy(good)
    m3b["findings"][1]["acceptance"] = {
        "owner_id": "agent-claude-opus",
        "attribution_kind": "agent-signed",
        "agent_signed": True,
    }
    check("agent-signed-acceptance", m3b, True, "agent-signed")

    m4 = copy.deepcopy(good)
    dropped = m4["findings"].pop()
    m4["counts"]["findings"] = 2
    m4["counts"]["RESOLVED"] = 0
    m4["receipt_census"]["finding_count_from_receipts"] = 2
    check("recount-drop-one", m4, True, "recount mismatch")

    results["dropped_id"] = dropped["id"]
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(REPO / LIVE_LEDGER_REL))
    ap.add_argument("--receipts-dir", default=str(REPO / LIVE_RECEIPTS_REL))
    ap.add_argument("--controls", action="store_true")
    args = ap.parse_args()
    if args.controls:
        scratch = HERE / "fixtures" / "_control-scratch"
        if scratch.exists():
            shutil.rmtree(scratch)
        scratch.mkdir(parents=True, exist_ok=True)
        results = run_catalog_controls(scratch)
        printable = {
            k: (
                {kk: vv for kk, vv in v.items() if kk != "errors"}
                if isinstance(v, dict)
                else v
            )
            for k, v in results.items()
        }
        print(json.dumps(printable))
        bad = [
            k
            for k, v in results.items()
            if isinstance(v, dict) and "ok" in v and not v["ok"]
        ]
        if bad:
            print("FAILED:BLD-0064 controls", bad)
            for name in bad:
                print(name, results[name].get("errors"))
            return 1
        print("SUCCESS:BLD-0064 validator controls")
        return 0
    errs = validate_path(Path(args.ledger), Path(args.receipts_dir))
    if errs:
        for err in errs:
            print(f"INVALID: {err}")
        print("FAILED:BLD-0064 validator")
        return 1
    print("VALID residual-risk ledger")
    print("SUCCESS:BLD-0064 validator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
