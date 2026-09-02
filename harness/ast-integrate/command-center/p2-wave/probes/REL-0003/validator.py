"""REL-0003 owner-packet validator.

Checks the four catalog tests_required:
  1. Structural: exactly one question (spec 11366).
  2. Satisfiability: named receipt paths resolve by catalog id lookup.
  3. Negative control: missing default_if_unanswered is rejected.
  4. Anti-re-ask: the question must not match a prior OWNER-DECISIONS.md ruling.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCHEMA_REL = "command-center/schema/owner-decision-packet.schema.json"
LOCAL_SCHEMA_REL = "command-center/p2-wave/probes/REL-0003/packet.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
OWNER_REL = "command-center/OWNER-DECISIONS.md"
PHASE_REL = "command-center/PHASE-GRAPH.json"
SPEC_VERBATIM = "release/canary succeeds"
THIS_IDS = {"REL-0003", "OQ-9"}
UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$")
ID_IN_HEADING_RE = re.compile(r"\b((?:OQ|REL)-\d+)\b")
TABLE_RE = re.compile(
    r"^\|\s*((?:OQ|REL)-\d+|Q\d+)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*(.*?)\s*\|\s*(.*?)\s*\|?\s*$"
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema() -> dict:
    """Load the local non-vacuous packet schema, never the catalog $ref shim."""
    return load_json(REPO / LOCAL_SCHEMA_REL)


def _usable_schema(schema: dict | None) -> dict:
    if schema is None:
        return load_schema()
    blob = json.dumps(schema)
    if "ast-integrate.invalid" in blob or schema.get("$ref"):
        return load_schema()
    return schema


def schema_errors(doc: Any, schema: dict | None = None) -> list[str]:
    sch = _usable_schema(schema)
    validator = jsonschema.Draft7Validator(sch)
    out = []
    try:
        errors = list(validator.iter_errors(doc))
    except jsonschema.exceptions.RefResolutionError as exc:
        return [f"schema:<root>: RefResolutionError {exc}"]
    for err in sorted(errors, key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "<root>"
        out.append(f"schema:{path}: {err.message}")
    return out


def question_count(doc: dict) -> int:
    n = 0
    q = doc.get("question")
    if isinstance(q, str):
        n += q.count("?")
    for key in ("questions", "owner_questions", "extra_questions"):
        raw = doc.get(key)
        if isinstance(raw, list):
            n += sum(1 for item in raw if isinstance(item, str) and "?" in item)
        elif isinstance(raw, str):
            n += raw.count("?")
    q2 = doc.get("question_2")
    if isinstance(q2, str):
        n += q2.count("?")
    return n


def catalog_index(catalog: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if UID_RE.match(uid):
            out[uid] = unit
    return out


def named_receipts(doc: dict) -> list[dict]:
    rec = doc.get("recommendation")
    if not isinstance(rec, dict):
        return []
    rows = rec.get("named_receipts") or []
    return [r for r in rows if isinstance(r, dict)]


def satisfiability_errors(doc: dict, catalog: dict) -> list[str]:
    errors: list[str] = []
    index = catalog_index(catalog)
    rows = named_receipts(doc)
    if len(rows) < 3:
        errors.append("satisfiability: named_receipts fewer than 3")
    seen: set[str] = set()
    for row in rows:
        uid = str(row.get("unit_id") or "")
        path = str(row.get("path") or "").replace("\\", "/")
        if uid in seen:
            errors.append(f"satisfiability: duplicate unit_id {uid}")
        seen.add(uid)
        if uid not in index:
            errors.append(f"satisfiability: catalog id lookup missed {uid}")
            continue
        want = str(index[uid].get("output_path") or "").replace("\\", "/")
        if not want:
            errors.append(f"satisfiability: catalog unit {uid} has no output_path")
        elif want != path:
            errors.append(
                f"satisfiability: {uid} path {path!r} != catalog output_path {want!r}"
            )
    return errors


def norm_q(text: str) -> str:
    t = text.strip().lower()
    t = t.replace("**", " ")
    t = re.sub(r"\s+", " ", t)
    return t


def parse_owner_decisions(text: str) -> list[dict]:
    """Parse ## / ### sections, - id/question/answer bullets, and the owner table.

    The live OWNER-DECISIONS.md rendered from the catalog uses a markdown table
    plus ### OQ-N headings, not only `##` + `- question:` bullets.
    """
    records: list[dict] = []
    current: dict | None = None
    for i, line in enumerate(text.splitlines(), 1):
        hm = HEADING_RE.match(line)
        if hm:
            if current:
                records.append(current)
            heading = hm.group(2).strip()
            current = {"heading": heading, "heading_line": i}
            im = ID_IN_HEADING_RE.search(heading)
            if im:
                current["id"] = im.group(1)
            continue
        tm = TABLE_RE.match(line)
        if tm:
            records.append(
                {
                    "id": tm.group(1),
                    "state": tm.group(2).strip(),
                    "question": tm.group(4).strip(),
                    "answer": tm.group(5).strip(),
                    "heading": f"table:{tm.group(1)}",
                    "heading_line": i,
                }
            )
            continue
        if current is None:
            continue
        m = re.match(r"- (id|question|answer):\s*(.*)$", line)
        if m:
            current[m.group(1)] = m.group(2).strip()
            current[f"{m.group(1)}_line"] = i
    if current:
        records.append(current)
    return records


def similar_question(a: str, b: str) -> bool:
    na, nb = norm_q(a), norm_q(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    marker = "pr-only / private canary / public marketplace"
    if marker in na and marker in nb:
        return True
    ta, tb = set(re.findall(r"[a-z0-9]+", na)), set(re.findall(r"[a-z0-9]+", nb))
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.72


def anti_reask_errors(doc: dict, owner_text: str) -> list[str]:
    errors: list[str] = []
    q = doc.get("question")
    if not isinstance(q, str) or "?" not in q:
        errors.append("anti-reask: packet has no question")
        return errors
    records = parse_owner_decisions(owner_text)
    for rec in records:
        rid = str(rec.get("id") or "")
        if rid in THIS_IDS:
            continue
        prior = rec.get("question") or ""
        if similar_question(q, prior):
            errors.append(
                f"anti-reask: packet question matches settled {rid or rec.get('heading')}"
            )
    return errors


def spec_quote_errors(doc: dict) -> list[str]:
    errors: list[str] = []
    quote = doc.get("spec_quote_11390")
    if not isinstance(quote, dict):
        return ["spec_quote: missing"]
    verbatim = str(quote.get("verbatim") or "")
    if verbatim != SPEC_VERBATIM:
        errors.append(
            f"spec_quote: verbatim {verbatim!r} != {SPEC_VERBATIM!r}"
        )
    if quote.get("line") != 11390:
        errors.append("spec_quote: line is not 11390")
    blob = json.dumps(doc)
    if SPEC_VERBATIM not in blob:
        errors.append("spec_quote: verbatim text absent from packet")
    q = str(doc.get("question") or "")
    if SPEC_VERBATIM not in q:
        errors.append("spec_quote: question does not quote spec 11390 verbatim")
    return errors


def phase_graph_errors(doc: dict, phase: Any) -> list[str]:
    errors: list[str] = []
    cite = doc.get("phase_graph_citation")
    if not isinstance(cite, dict):
        return ["phase_graph: citation missing"]
    if str(cite.get("path") or "").replace("\\", "/") != PHASE_REL:
        errors.append("phase_graph: citation path is not command-center/PHASE-GRAPH.json")
    field = str(cite.get("field") or "")
    if field != "constrained_by_release_mode.owner_decision_needed":
        errors.append(f"phase_graph: unexpected field {field!r}")
    if not isinstance(phase, dict):
        errors.append("phase_graph: PHASE-GRAPH.json missing or unparseable")
        return errors
    node = phase.get("constrained_by_release_mode")
    if not isinstance(node, dict):
        errors.append("phase_graph: constrained_by_release_mode absent")
        return errors
    if "owner_decision_needed" not in node:
        errors.append("phase_graph: owner_decision_needed absent")
    elif node.get("owner_decision_needed") is not True:
        errors.append("phase_graph: owner_decision_needed did not measure the gap as true")
    if node.get("satisfiable_as_written") is not False:
        errors.append("phase_graph: satisfiable_as_written was not measured false")
    if str(node.get("stop_condition_13_as_written") or "") != SPEC_VERBATIM:
        errors.append("phase_graph: stop condition 13 text mismatch")
    return errors


def validate_packet(
    doc: Any,
    *,
    catalog: dict | None = None,
    owner_text: str | None = None,
    phase: Any = None,
    schema: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["packet is not an object"]
    errors.extend(schema_errors(doc, schema))
    nq = question_count(doc)
    if nq != 1:
        errors.append(f"structural: question_count={nq} want=1 (spec 11366)")
    if "default_if_unanswered" not in doc or not str(doc.get("default_if_unanswered") or "").strip():
        errors.append("negative-control-surface: default_if_unanswered missing")
    cat = catalog if catalog is not None else load_json(REPO / CATALOG_REL)
    errors.extend(satisfiability_errors(doc, cat))
    if owner_text is None:
        op = REPO / OWNER_REL
        owner_text = op.read_text(encoding="utf-8") if op.is_file() else ""
    if not owner_text.strip():
        errors.append("anti-reask: OWNER-DECISIONS.md missing")
    else:
        errors.extend(anti_reask_errors(doc, owner_text))
    errors.extend(spec_quote_errors(doc))
    if phase is None:
        pp = REPO / PHASE_REL
        phase = load_json(pp) if pp.is_file() else None
    errors.extend(phase_graph_errors(doc, phase))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errors.append(f"self-declared {doc.get('state')}")
    sentinel = str(doc.get("sentinel") or "")
    if sentinel != "SUCCESS:REL-0003":
        errors.append("sentinel-absent")
    rec = doc.get("durable_record_location") or {}
    if isinstance(rec, dict):
        path = str(rec.get("path") or "").replace("\\", "/")
        line = rec.get("line")
        if path != OWNER_REL:
            errors.append("durable_record_location path is not OWNER-DECISIONS.md")
        if not isinstance(line, int) or line < 1:
            errors.append("durable_record_location line missing")
        elif owner_text:
            lines = owner_text.splitlines()
            if line > len(lines) or "REL-0003" not in "\n".join(lines[max(0, line - 3) : line + 8]):
                errors.append("durable_record_location does not cite the REL-0003 record")
    return errors


def reject_missing_default(doc: dict, schema: dict | None = None) -> bool:
    """Catalog negative control: a packet missing default_if_unanswered is rejected."""
    mutant = copy.deepcopy(doc)
    mutant.pop("default_if_unanswered", None)
    if "default_if_unanswered" in mutant:
        return False
    errs = schema_errors(mutant, schema)
    return any("default_if_unanswered" in e for e in errs)


def reject_second_question(doc: dict, schema: dict | None = None) -> bool:
    mutant = copy.deepcopy(doc)
    mutant["question"] = (
        str(mutant.get("question") or "What?")
        + " Should condition 12 also be waived?"
    )
    nq = question_count(mutant)
    sch = schema_errors(mutant, schema)
    return nq != 1 or bool(sch)
