#!/usr/bin/env python3
"""Join owner questions to recorded owner answers and to units using a default.

ANSWERED requires the owner's own words at path:line. An agent's summary,
delegated default, or mere acknowledgement is UNANSWERED. A blank required
answer takes the worst-case adverse-inference default, never 'probably fine'.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

QID_TOKEN = re.compile(r"(?:OQ-\d+|Q\d+|CTL-[A-Z0-9-]+)")
HEADING_ID = re.compile(
    r"^#{1,4}\s+`?(OQ-\d+|Q\d+|CTL-[A-Z0-9-]+)`?\b", re.MULTILINE
)
TABLE_ID = re.compile(r"^\|\s*`?(OQ-\d+|Q\d+|CTL-[A-Z0-9-]+)`?\s*\|")
OWNER_LINE = re.compile(
    r"(?i)^(?:[-*]\s+)?(?:\*\*)?owner(?: statement)?(?:\*\*)?\s*[:—-]\s*[\"“]?(.+?)[\"”]?\s*$"
)
AGENT_LINE = re.compile(
    r"(?i)^(?:[-*]\s+)?(?:\*\*)?agent(?: inference| summary)?(?:\*\*)?\s*[:—-]\s*(.+)$"
)
ACK_ONLY = {
    "got it",
    "acknowledged",
    "ok",
    "okay",
    "noted",
    "thanks",
    "thank you",
    "ack",
}
FILE_LINE = re.compile(r"([\w./\\-]+\.(?:md|json|txt|py)):(\d+)")

PACKET_CANDIDATES = (
    "command-center/OWNER-QUESTION-PACKET.md",
    "OWNER-QUESTION-PACKET.md",
    "command-center/14-OWNER-DECISION-PACKET.md",
    "14-OWNER-DECISION-PACKET.md",
)
DECISIONS_CANDIDATES = (
    "command-center/OWNER-DECISIONS.md",
    "OWNER-DECISIONS.md",
    "32-OWNER-DECISIONS.md",
    "command-center/32-OWNER-DECISIONS.md",
)
DECISION_LOG_CANDIDATES = (
    "17-DECISION-LOG.md",
    "command-center/17-DECISION-LOG.md",
    "docs/17-DECISION-LOG.md",
)

# Code that executes a named unanswered/delegated question's default.
CODE_CONSUMERS = (
    {
        "path": "command-center/ready_units.py",
        "question_id": "OQ-10",
        "needle": "BUCKET_SATISFIED = True",
        "assumed_default": (
            "A bucket dependency is satisfied by a bucket-level gate artifact "
            "(hard-coded BUCKET_SATISFIED=True). OWNER-DECISIONS.md is present "
            "but OQ-10 has no Owner: utterance at path:line."
        ),
        "kind": "code-consumer",
    },
    {
        "path": "command-center/p2-wave/_b1_rank.py",
        "question_id": "OQ-2",
        "needle": "OQ-2 owner ruling",
        "assumed_default": "Ascending phase (int), then unblocking power.",
        "kind": "code-consumer",
    },
    {
        "path": "command-center/p2-wave/_audit_rank.py",
        "question_id": "OQ-2",
        "needle": "rank READY units by OQ-2",
        "assumed_default": "Ascending phase, then unblocking power.",
        "kind": "code-consumer",
    },
)


def rel_of(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def present(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_line(text: str, snippet: str) -> int:
    idx = text.find(snippet)
    if idx < 0:
        return 0
    return text[:idx].count("\n") + 1


def is_mere_ack(answer: str) -> bool:
    s = re.sub(r"[^a-z]+", " ", (answer or "").lower()).strip()
    return s in ACK_ONLY


def adverse_default(text: str) -> str:
    t = (text or "").lower()
    if "public or private" in t:
        return (
            "Worst-case adverse inference: PRIVATE. Do not publish a marketplace "
            "index and do not assume a public release."
        )
    if "pr-only" in t or "release mode" in t:
        return (
            "Worst-case adverse inference: do not ship a canary or marketplace "
            "release; treat release mode as unset and halt Phase 15/16 gates."
        )
    if "adopt" in t:
        return (
            "Worst-case adverse inference: do not adopt. Halt any implementation "
            "that requires the owner to have chosen adoption."
        )
    if "quarantine" in t or "credential" in t or "diag 1" in t:
        return (
            "Worst-case adverse inference: do not touch, rotate, or index the "
            "credential file; quarantine is owner-only and is not assumed done."
        )
    if "canonical" in t and "beads" in t:
        return (
            "Worst-case adverse inference: treat the split as unresolved; do not "
            "delete either path and do not pick a canonical location."
        )
    if "reconstruct and commit, or accept" in t:
        return (
            "Worst-case adverse inference: do not overwrite live-only rules; do "
            "not accept absence as approval."
        )
    if "fix the doc or add the flag" in t:
        return (
            "Worst-case adverse inference: do not 'fix' by inventing a flag and "
            "do not silently drop the documented command; owner-blocked."
        )
    return (
        "Worst-case adverse inference: do not assume the permissive option; "
        "treat the unanswered question as blocking any action that requires it; "
        "never default to 'probably fine'."
    )


def token_re(ids: list[str]) -> re.Pattern[str]:
    parts = sorted({i for i in ids if i}, key=len, reverse=True)
    if not parts:
        return re.compile(r"(?!x)x")
    return re.compile(
        r"(?<![A-Za-z0-9_-])(" + "|".join(re.escape(p) for p in parts) + r")(?![A-Za-z0-9_-])"
    )


def parse_packet(text: str) -> list[dict[str, Any]]:
    """Extract question ids and texts from a packet markdown file."""
    found: dict[str, dict[str, Any]] = {}
    current: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current, buf
        if current:
            body = " ".join(x.strip() for x in buf if x.strip())
            row = found.setdefault(current, {"id": current, "text": "", "source": "packet"})
            if body and not row["text"]:
                row["text"] = body[:500]
        buf = []

    for line in text.splitlines():
        h = HEADING_ID.match(line)
        if h:
            flush()
            current = h.group(1)
            found.setdefault(current, {"id": current, "text": "", "source": "packet"})
            continue
        t = TABLE_ID.match(line)
        if t:
            flush()
            current = None
            qid = t.group(1)
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            text_cell = cells[1] if len(cells) > 1 else ""
            row = found.setdefault(qid, {"id": qid, "text": "", "source": "packet"})
            if text_cell and text_cell not in {"question", "text", "Question"}:
                row["text"] = text_cell[:500]
            continue
        if current:
            if line.strip().startswith("|") and re.match(r"^\|\s*-+", line):
                continue
            buf.append(line)
    flush()
    return [found[k] for k in found]


def _section_answers(text: str) -> dict[str, dict[str, Any]]:
    """Map question id -> owner/agent lines collected under that heading."""
    sections: dict[str, dict[str, Any]] = {}
    current: str | None = None
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        h = HEADING_ID.match(line)
        if h:
            current = h.group(1)
            sections.setdefault(current, {"owner": [], "agent": [], "raw": []})
            continue
        t = TABLE_ID.match(line)
        if t:
            current = t.group(1)
            sections.setdefault(current, {"owner": [], "agent": [], "raw": []})
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5 and cells[4] and cells[4] != "—":
                sections[current]["raw"].append((i, cells[4]))
            continue
        if not current:
            continue
        om = OWNER_LINE.match(line.strip())
        if om:
            sections[current]["owner"].append((i, om.group(1).strip()))
            continue
        am = AGENT_LINE.match(line.strip())
        if am:
            sections[current]["agent"].append((i, am.group(1).strip()))
    return sections


def owner_authored_hits(path: Path, repo: Path, text: str) -> dict[str, dict[str, Any]]:
    rel = rel_of(repo, path)
    out: dict[str, dict[str, Any]] = {}
    for qid, sec in _section_answers(text).items():
        for line_no, quote in sec["owner"]:
            if is_mere_ack(quote):
                out[qid] = {
                    "grade": "ack-only",
                    "quote": quote,
                    "anchor": f"{rel}:{line_no}",
                    "path": rel,
                    "line": line_no,
                }
                break
            out[qid] = {
                "grade": "owner-authored",
                "quote": quote,
                "anchor": f"{rel}:{line_no}",
                "path": rel,
                "line": line_no,
            }
            break
        if qid in out:
            continue
        if sec["agent"]:
            line_no, quote = sec["agent"][0]
            out[qid] = {
                "grade": "agent-inference",
                "quote": quote,
                "anchor": f"{rel}:{line_no}",
                "path": rel,
                "line": line_no,
            }
    return out


def catalog_provenance_grade(q: dict[str, Any]) -> str:
    prov = str(q.get("answer_provenance") or "")
    answer = str(q.get("answer") or "").strip()
    low = prov.lower()
    if not answer:
        return "no-catalog-answer"
    if FILE_LINE.search(prov):
        return "catalog-cites-file-line"
    if "delegated" in low or "not an owner-authored" in low:
        return "delegated-default"
    if "infer" in low or "agent" in low:
        return "agent-inference"
    if "session" in low or "spoken" in low:
        return "agent-summary-of-spoken-owner"
    if str(q.get("state") or "").upper() == "ANSWERED":
        return "catalog-answered-without-owner-utterance-anchor"
    return "catalog-answer-unanchored"


def classify_question(
    q: dict[str, Any],
    hits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    qid = str(q.get("id") or "")
    text = str(q.get("text") or "")
    catalog_state = str(q.get("state") or "OPEN").upper()
    hit = hits.get(qid)
    catalog_answer = str(q.get("answer") or "").strip()
    prov_grade = catalog_provenance_grade(q)

    if hit and hit["grade"] == "owner-authored":
        return {
            "verdict": "ANSWERED",
            "reason": "owner-authored-answer-at-path-line",
            "answer_anchor": hit["anchor"],
            "answer_quote": hit["quote"],
            "assumed_default": hit["quote"],
            "default_source": "owner-answer",
            "catalog_state": catalog_state,
            "provenance_grade": prov_grade,
        }
    if hit and hit["grade"] == "ack-only":
        return {
            "verdict": "UNANSWERED",
            "reason": "owner-acknowledged-but-did-not-resolve",
            "answer_anchor": hit["anchor"],
            "answer_quote": hit["quote"],
            "assumed_default": adverse_default(text),
            "default_source": "adverse-inference",
            "catalog_state": catalog_state,
            "provenance_grade": prov_grade,
        }
    if hit and hit["grade"] == "agent-inference":
        return {
            "verdict": "UNANSWERED",
            "reason": "answered-only-by-agent-inference",
            "answer_anchor": hit["anchor"],
            "answer_quote": hit["quote"],
            "assumed_default": adverse_default(text),
            "default_source": "adverse-inference",
            "catalog_state": catalog_state,
            "provenance_grade": "agent-inference",
        }

    if catalog_answer and prov_grade == "delegated-default":
        return {
            "verdict": "UNANSWERED",
            "reason": "catalog-answer-is-delegated-default-not-owner-authored",
            "answer_anchor": None,
            "answer_quote": catalog_answer,
            "assumed_default": catalog_answer,
            "default_source": "catalog-delegated-default-in-use",
            "catalog_state": catalog_state,
            "provenance_grade": prov_grade,
        }
    if catalog_answer:
        return {
            "verdict": "UNANSWERED",
            "reason": "agent-summary-of-owner-without-utterance-path-line",
            "answer_anchor": None,
            "answer_quote": catalog_answer,
            "assumed_default": catalog_answer,
            "default_source": "catalog-agent-recorded-answer-in-use",
            "catalog_state": catalog_state,
            "provenance_grade": prov_grade,
        }
    return {
        "verdict": "UNANSWERED",
        "reason": "no-recorded-owner-answer",
        "answer_anchor": None,
        "answer_quote": None,
        "assumed_default": adverse_default(text),
        "default_source": "adverse-inference",
        "catalog_state": catalog_state,
        "provenance_grade": prov_grade,
    }


def collect_answer_hits(repo: Path, paths: list[Path]) -> dict[str, dict[str, Any]]:
    hits: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not present(path):
            continue
        text = path.read_text(encoding="utf-8")
        for qid, hit in owner_authored_hits(path, repo, text).items():
            prev = hits.get(qid)
            if prev and prev.get("grade") == "owner-authored":
                continue
            if hit["grade"] == "owner-authored" or prev is None:
                hits[qid] = hit
    return hits


def scan_blob(blob: str, pattern: re.Pattern[str]) -> list[str]:
    return sorted(set(pattern.findall(blob)))


def dependents_from_catalog(
    catalog: dict[str, Any], ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    pattern = token_re(ids)
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(qid: str, rec: dict[str, Any]) -> None:
        existing = {(r["unit_id"], r["kind"]) for r in out[qid]}
        key = (rec["unit_id"], rec["kind"])
        if key not in existing:
            out[qid].append(rec)

    for item in catalog.get("items") or []:
        if not isinstance(item, dict):
            continue
        uid = str(item.get("id") or "")
        blob = json.dumps(item, ensure_ascii=False)
        found = scan_blob(blob, pattern)
        gates = [str(g) for g in (item.get("owner_gate") or [])]
        live_gates = set(gates)
        discharged: list[str] = []
        retired_ra03 = False
        for ev in item.get("history") or []:
            if not isinstance(ev, dict):
                continue
            discharged.extend(str(x) for x in (ev.get("discharged") or []))
            if ev.get("retired_dependency") == "R-A03":
                retired_ra03 = True
        status = str(item.get("status") or "")
        disp = item.get("disposition")
        for qid in found:
            waiting = qid in live_gates and str(disp or "") in {"", "null", "None"}
            # A live owner_gate means the item is waiting, not silently executing,
            # even if status is DONE-CLAIMED (R-B04 is blocked on Q22).
            if qid in live_gates and status in {"OPEN", "DONE-CLAIMED"} and not disp:
                kind = "waiting-live-owner-gate"
            elif qid in discharged:
                kind = "proceeding-gate-discharged-without-owner-authored-answer"
            elif retired_ra03 and qid in {"OQ-1", "OQ-2", "OQ-3"}:
                kind = "proceeding-walked-past-R-A03-gate"
            elif disp in {"DONE-VERIFIED", "DONE-CLAIMED"}:
                kind = "proceeding-closed-on-unanswered"
            else:
                kind = "dependent-mentioned"
            add(
                qid,
                {
                    "unit_id": uid,
                    "kind": kind,
                    "class": "backlog-item",
                    "status": status,
                    "disposition": disp,
                    "owner_gate": gates,
                    "title": str(item.get("title") or "")[:160],
                },
            )
        if retired_ra03:
            for qid in ("OQ-1", "OQ-2", "OQ-3"):
                if qid in ids:
                    add(
                        qid,
                        {
                            "unit_id": uid,
                            "kind": "proceeding-walked-past-R-A03-gate",
                            "class": "backlog-item",
                            "status": status,
                            "disposition": disp,
                            "owner_gate": gates,
                            "title": str(item.get("title") or "")[:160],
                        },
                    )

    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if uid == "BLD-0017":
            continue
        blob = json.dumps(unit, ensure_ascii=False)
        found = scan_blob(blob, pattern)
        gated = bool(unit.get("owner_approval_required"))
        for qid in found:
            kind = (
                "waiting-owner-approval-required"
                if gated
                else "proceeding-work-unit-input-or-target"
            )
            add(
                qid,
                {
                    "unit_id": uid,
                    "kind": kind,
                    "class": "work-unit",
                    "status": None,
                    "disposition": None,
                    "owner_gate": [],
                    "title": str(unit.get("title") or "")[:160],
                    "owner_approval_required": gated,
                },
            )
    return out


def code_consumers(repo: Path, ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    idset = set(ids)
    for spec in CODE_CONSUMERS:
        qid = spec["question_id"]
        if qid not in idset:
            continue
        path = repo / spec["path"]
        if not present(path):
            continue
        text = path.read_text(encoding="utf-8")
        if spec["needle"] not in text:
            continue
        line = find_line(text, spec["needle"])
        out[qid].append(
            {
                "unit_id": spec["path"],
                "kind": spec["kind"],
                "class": "code",
                "status": None,
                "disposition": None,
                "owner_gate": [],
                "title": spec["assumed_default"][:160],
                "anchor": f"{spec['path']}:{line}",
                "assumed_default": spec["assumed_default"],
            }
        )
    return out


def first_present(repo: Path, rels: tuple[str, ...]) -> dict[str, Any]:
    rows = []
    chosen = None
    for rel in rels:
        path = repo / rel
        rec = {
            "path": rel,
            "present": present(path),
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
        rows.append(rec)
        if rec["present"] and chosen is None:
            chosen = path
    return {"candidates": rows, "chosen": rel_of(repo, chosen) if chosen else None, "path": chosen}


def analyze(
    repo: Path,
    *,
    catalog_path: Path | None = None,
    packet_candidates: list[Path] | None = None,
    decisions_candidates: list[Path] | None = None,
    decision_log_candidates: list[Path] | None = None,
    scan_code: bool = True,
) -> dict[str, Any]:
    catalog_path = catalog_path or (repo / "command-center/WORK-UNIT-CATALOG.json")
    catalog = load_json(catalog_path)
    catalog_qs = [
        q
        for q in (catalog.get("owner_questions") or [])
        if isinstance(q, dict) and q.get("id")
    ]
    catalog_ids = [str(q["id"]) for q in catalog_qs]
    catalog_by = {str(q["id"]): q for q in catalog_qs}

    if packet_candidates is None:
        packet_candidates = [repo / r for r in PACKET_CANDIDATES]
    packet_path = next((p for p in packet_candidates if present(p)), None)
    packet_qs: list[dict[str, Any]] = []
    if packet_path:
        packet_qs = parse_packet(packet_path.read_text(encoding="utf-8"))
    packet_ids = [str(q["id"]) for q in packet_qs]
    packet_by = {str(q["id"]): q for q in packet_qs}

    if decisions_candidates is None:
        decisions_candidates = [repo / r for r in DECISIONS_CANDIDATES]
    if decision_log_candidates is None:
        decision_log_candidates = [repo / r for r in DECISION_LOG_CANDIDATES]
    answer_paths = [
        p
        for p in list(decisions_candidates) + list(decision_log_candidates)
        if present(p)
    ]
    hits = collect_answer_hits(repo, answer_paths)

    ordered_ids: list[str] = []
    for qid in catalog_ids:
        if qid not in ordered_ids:
            ordered_ids.append(qid)
    for qid in packet_ids:
        if qid not in ordered_ids:
            ordered_ids.append(qid)

    catalog_text = catalog_path.read_text(encoding="utf-8")
    table: list[dict[str, Any]] = []
    for qid in ordered_ids:
        src = (
            "both"
            if qid in catalog_by and qid in packet_by
            else ("catalog" if qid in catalog_by else "packet")
        )
        base = dict(catalog_by.get(qid) or packet_by.get(qid) or {"id": qid, "text": ""})
        if qid in packet_by and not base.get("text"):
            base["text"] = packet_by[qid].get("text") or ""
        cls = classify_question(base, hits)
        cat_line = find_line(catalog_text, f'"id": "{qid}"') if qid in catalog_by else 0
        table.append(
            {
                "id": qid,
                "source": src,
                "text": str(base.get("text") or "")[:400],
                "catalog_state": cls["catalog_state"],
                "verdict": cls["verdict"],
                "reason": cls["reason"],
                "answer_anchor": cls["answer_anchor"],
                "answer_quote": cls["answer_quote"],
                "assumed_default": cls["assumed_default"],
                "default_source": cls["default_source"],
                "provenance_grade": cls["provenance_grade"],
                "catalog_anchor": (
                    f"{rel_of(repo, catalog_path)}:{cat_line}" if cat_line else None
                ),
            }
        )

    counts = Counter(r["id"] for r in table)
    missing = [i for i in ordered_ids if counts.get(i, 0) == 0]
    duplicates = [i for i, n in counts.items() if n > 1]
    extra = [i for i in counts if i not in ordered_ids]

    deps = dependents_from_catalog(catalog, ordered_ids)
    if scan_code:
        for qid, rows in code_consumers(repo, ordered_ids).items():
            deps[qid].extend(rows)

    proceeding: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    by_id = {r["id"]: r for r in table}
    for qid, recs in deps.items():
        row = by_id.get(qid)
        if not row or row["verdict"] != "UNANSWERED":
            continue
        for rec in recs:
            assumed = rec.get("assumed_default") or row["assumed_default"]
            payload = {
                "unit_id": rec["unit_id"],
                "question_id": qid,
                "assumed_default": assumed,
                "kind": rec["kind"],
                "class": rec.get("class"),
                "title": rec.get("title"),
                "anchor": rec.get("anchor") or rec.get("catalog_anchor") or row.get("catalog_anchor"),
            }
            if rec["kind"].startswith("waiting-"):
                waiting.append(payload)
            elif rec["kind"].startswith("proceeding") or rec["kind"] == "code-consumer":
                proceeding.append(payload)
            elif rec["kind"] == "dependent-mentioned" and rec.get("class") == "work-unit":
                proceeding.append({**payload, "kind": "proceeding-work-unit-input-or-target"})

    def probe_src(rel_tuple: tuple[str, ...], paths: list[Path]) -> dict[str, Any]:
        rows = []
        for p in paths:
            rows.append(
                {
                    "path": rel_of(repo, p),
                    "present": present(p),
                    "bytes": p.stat().st_size if p.is_file() else 0,
                }
            )
        chosen = next((r["path"] for r in rows if r["present"]), None)
        return {"candidates": rows, "present": chosen is not None, "chosen": chosen}

    return {
        "catalog_path": rel_of(repo, catalog_path),
        "catalog_count": len(catalog_ids),
        "packet_count": len(packet_ids),
        "packet_ids": packet_ids,
        "catalog_ids": catalog_ids,
        "ordered_ids": ordered_ids,
        "closure_table": table,
        "coverage": {
            "catalog_count": len(catalog_ids),
            "packet_count": len(packet_ids),
            "table_count": len(table),
            "expected_ids": ordered_ids,
            "missing": missing,
            "duplicates": duplicates,
            "extra": extra,
            "exact_once": not missing and not duplicates and extra == [],
            "claimed_in_unit_brief": 27,
            "count_drift_vs_brief_27": len(catalog_ids) != 27,
        },
        "dependents": {k: v for k, v in deps.items()},
        "proceeding_on_default": proceeding,
        "waiting_on_owner": waiting,
        "answered_count": sum(1 for r in table if r["verdict"] == "ANSWERED"),
        "unanswered_count": sum(1 for r in table if r["verdict"] == "UNANSWERED"),
        "sources": {
            "catalog": {
                "path": rel_of(repo, catalog_path),
                "present": present(catalog_path),
                "owner_questions_measured": len(catalog_ids),
                "claimed_in_unit_brief": 27,
            },
            "packet": probe_src(PACKET_CANDIDATES, packet_candidates),
            "owner_decisions": probe_src(DECISIONS_CANDIDATES, decisions_candidates),
            "decision_log": probe_src(DECISION_LOG_CANDIDATES, decision_log_candidates),
        },
        "answer_files_present": [rel_of(repo, p) for p in answer_paths],
    }


def control_verdicts(result: dict[str, Any]) -> dict[str, str]:
    return {r["id"]: r["verdict"] for r in result.get("closure_table") or []}


def proceeding_ids(result: dict[str, Any], qid: str) -> set[str]:
    return {
        str(r["unit_id"])
        for r in (result.get("proceeding_on_default") or [])
        if r.get("question_id") == qid
    }


def analyze_controls(repo: Path, fixture_dir: Path) -> dict[str, Any]:
    return analyze(
        repo,
        catalog_path=fixture_dir / "catalog.json",
        packet_candidates=[fixture_dir / "OWNER-QUESTION-PACKET.md"],
        decisions_candidates=[fixture_dir / "OWNER-DECISIONS.md"],
        decision_log_candidates=[],
        scan_code=False,
    )
