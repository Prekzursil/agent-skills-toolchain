#!/usr/bin/env python3
"""Probe 2: independent recount from fixture JSON + artifact overclaim/anchors.

Does not call semantics.classify_abstention. Re-derives yes/no/abstain counts,
pivotality, expertise overlap, and principled-record completeness from raw
fields. Re-runs both-states. A review that skipped the control fails.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = (
    REPO
    / "command-center/design/council/CNL-0066-abstention-semantics-and-strategic-abstention-detection.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
SCHEMA = REPO / SCHEMA_REL
FIX = HERE / "fixtures"


def _schema_validator():
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import schema_local as SL  # noqa: PLC0415

    return SL.validator()


def _both_states(doc: dict) -> dict:
    if isinstance(doc.get("both_states"), dict):
        return doc["both_states"]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(report.get("both_states"), dict):
        return report["both_states"]
    ext = doc.get("extensions") if isinstance(doc.get("extensions"), dict) else {}
    if isinstance(ext.get("both_states"), dict):
        return ext["both_states"]
    return {}


def _reviewer_reran(doc: dict, rev: dict) -> bool:
    if rev.get("re_ran_both_states") is True:
        return True
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if report.get("re_ran_both_states") is True:
        return True
    notes = str(rev.get("notes") or "").lower()
    return "re-ran" in notes and "both-states" in notes


def load(name: str) -> dict:
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def tags(xs) -> set[str]:
    return {str(x) for x in (xs or [])}


def yes_count(ballots: list) -> int:
    return sum(1 for b in ballots if b.get("kind") == "YES")


def recount(doc: dict) -> dict:
    q = doc["question"]
    seats = {s["id"]: s for s in doc["seats"]}
    ballots = doc["ballots"]
    yes = yes_count(ballots)
    no = sum(1 for b in ballots if b.get("kind") == "NO")
    abstain = [b for b in ballots if b.get("kind") == "ABSTAIN"]
    n0 = len(doc["seats"])
    thr = int(q["threshold_yes"])
    basis = str(q.get("threshold_basis") or "")
    protocol_fired = basis == "present_and_voting" or basis not in {
        "seated",
        "eligible_snapshot",
    }
    rows = []
    for b in abstain:
        seat = seats[b["seat"]]
        overlap = tags(seat.get("expertise_tags")) & tags(q.get("required_domains"))
        claim = b.get("missing_claim") if isinstance(b.get("missing_claim"), dict) else {}
        pred = (
            b.get("would_unpark_if")
            if isinstance(b.get("would_unpark_if"), dict)
            else {}
        )
        code = str(b.get("reason_code") or "")
        claim_ok = bool(str(claim.get("what") or "").strip()) and bool(
            str(claim.get("why_blocks_vote") or "").strip()
        )
        pred_ok = bool(str(pred.get("field") or "").strip()) and bool(
            str(pred.get("op") or "").strip()
        )
        prior = any(
            isinstance(p, dict)
            and p.get("question_class_id") == q.get("question_class_id")
            and p.get("kind") in {"YES", "NO"}
            for p in (seat.get("prior_positions") or [])
        )
        expertise_lie = code == "NO_EXPERTISE" and (overlap or prior)
        principled = (
            code in {"NO_EXPERTISE", "CONFLICT_OF_INTEREST", "INSUFFICIENT_EVIDENCE"}
            and claim_ok
            and pred_ok
            and not expertise_lie
        )
        pivotal = yes < thr <= (yes + 1)
        if principled:
            cls, fire = "PRINCIPLED", False
        elif pivotal:
            cls, fire = "STRATEGIC", True
        else:
            cls, fire = "UNDETERMINED", False
        rows.append(
            {
                "seat": b["seat"],
                "class": cls,
                "strategic_fire": fire,
                "pivotal": pivotal,
                "overlap": sorted(overlap),
            }
        )
    fire = any(r["strategic_fire"] for r in rows)
    principled_ids = [r["seat"] for r in rows if r["class"] == "PRINCIPLED"]
    policy = str(q.get("abstention_policy") or "")
    if protocol_fired:
        decision = "INVALID-PROTOCOL"
    elif principled_ids and policy == "PARK_PRINCIPLED_ELSE_COUNT_AS_NO":
        decision = "PARKED"
    elif yes >= thr:
        decision = "PASS"
    else:
        decision = "FAIL"
    return {
        "id": doc["id"],
        "yes": yes,
        "no": no,
        "abstain_n": len(abstain),
        "seated_n0": n0,
        "class": rows[0]["class"] if rows else None,
        "strategic_fire": fire,
        "decision": decision,
        "protocol_fired": protocol_fired,
        "rows": rows,
    }


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        return -1
    return text[:idx].count("\n") + 1


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0066-probe2 artifact missing")
        return 1
    raw = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0066-probe2 artifact unparseable {exc}")
        return 1

    for name in (
        "known-good-principled",
        "planted-bad-strategic",
        "planted-bad-present-and-voting",
        "known-good-protocol-seated-basis",
        "negative-nonpivotal-generic",
    ):
        if not (FIX / f"{name}.json").is_file():
            print(f"FAILED:CNL-0066-probe2 fixture missing {name}")
            return 1

    good = recount(load("known-good-principled"))
    bad = recount(load("planted-bad-strategic"))
    pv = recount(load("planted-bad-present-and-voting"))
    seated = recount(load("known-good-protocol-seated-basis"))
    neg = recount(load("negative-nonpivotal-generic"))
    print(
        f"recount good class={good['class']} fire={good['strategic_fire']} "
        f"decision={good['decision']} yes={good['yes']}"
    )
    print(
        f"recount bad class={bad['class']} fire={bad['strategic_fire']} "
        f"decision={bad['decision']} yes={bad['yes']}"
    )
    print(
        f"recount pv proto_fired={pv['protocol_fired']} decision={pv['decision']}"
    )
    print(
        f"recount seated proto_fired={seated['protocol_fired']} "
        f"decision={seated['decision']}"
    )
    print(
        f"recount neg class={neg['class']} fire={neg['strategic_fire']} "
        f"decision={neg['decision']}"
    )

    errs: list[str] = []
    if good["class"] != "PRINCIPLED" or good["strategic_fire"] or good["decision"] != "PARKED":
        errs.append("good-recount")
    if bad["class"] != "STRATEGIC" or not bad["strategic_fire"] or bad["decision"] != "FAIL":
        errs.append("bad-recount")
    if not pv["protocol_fired"] or pv["decision"] != "INVALID-PROTOCOL":
        errs.append("pv-recount")
    if seated["protocol_fired"]:
        errs.append("seated-recount")
    if neg["strategic_fire"] or neg["class"] != "UNDETERMINED" or neg["decision"] != "PASS":
        errs.append("neg-recount")
    if good["yes"] != 3 or bad["yes"] != 3:
        errs.append("yes-count")

    recorded = _both_states(doc)
    rec_disc = recorded.get("discriminator") or {}
    if rec_disc.get("planted_bad") != "FIRE" or rec_disc.get("known_good") != "SILENT":
        errs.append("artifact-both-states-discriminator")
    rec_proto = recorded.get("protocol") or {}
    if rec_proto.get("planted_bad") != "FIRE" or rec_proto.get("known_good") != "SILENT":
        errs.append("artifact-both-states-protocol")

    if str(doc.get("state") or "") != "SUCCESS":
        errs.append(f"state={doc.get('state')}")
    if "SUCCESS:CNL-0066" not in raw:
        errs.append("sentinel-absent")

    if SCHEMA.is_file():
        import jsonschema

        try:
            validator = _schema_validator()
            validator.validate(doc)
        except Exception as exc:
            errs.append(f"schema-validate:{type(exc).__name__}:{exc}")
        else:
            mutant = dict(doc)
            dropped = None
            for key in ("answer", "evidence", "negative_controls", "records"):
                if key in mutant:
                    mutant.pop(key)
                    dropped = key
                    break
            if dropped is None:
                report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
                if "answer" in report:
                    mutant = dict(doc)
                    mutant["report"] = dict(report)
                    mutant["report"].pop("answer")
                    dropped = "answer"
            try:
                validator.validate(mutant)
                errs.append(f"schema-vacuous-accepted-{dropped}-drop")
            except jsonschema.ValidationError:
                print(f"schema_kind_mutant_rejected=true dropped={dropped}")
            print("schema_error_count=0")
    else:
        print("schema_file_missing=true")

    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        errs.append("evidence-short")
    for i, row in enumerate(evidence):
        sig = row.get("signal") if isinstance(row.get("signal"), dict) else {}
        anchor = str(sig.get("anchor") or row.get("anchor") or "")
        if ":" not in anchor:
            errs.append(f"anchor-malformed[{i}]")
            continue
        rel, _, line_s = anchor.rpartition(":")
        path = REPO / rel
        try:
            line = int(line_s)
        except ValueError:
            errs.append(f"anchor-line[{i}]")
            continue
        if not path.is_file():
            errs.append(f"anchor-missing[{i}] {rel}")
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        if line < 1 or line > len(lines):
            errs.append(f"anchor-oob[{i}]")
            continue
        print(f"anchor[{i}] ok=true {anchor}")

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        errs.append("reviewer-not-independent")
    if not _reviewer_reran(doc, rev):
        errs.append("reviewer-skipped-both-states")

    sem = HERE / "semantics.py"
    if find_line(sem, "decision denominator is seated_n0, never present-and-voting") < 1:
        errs.append("rule-comment-missing")

    if errs:
        print("FAILED:CNL-0066-probe2 " + " | ".join(errs))
        return 1
    print("SUCCESS:CNL-0066-probe2 independent-recount overclaim both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
