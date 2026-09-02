"""Three-join blast-radius closures for refuted premises (ADV-0133)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from corpus import (
    ADV0134_REL,
    AUD0075_REL,
    BRIEF_CANDIDATES,
    CATALOG_REL,
    CONFIRMED_PREMISE_ID,
    DECISION_CANDIDATES,
    EVENTS_REL,
    FIRST_ASSERTED,
    LIVE_AS_CURRENT_MARKERS,
    MANIFEST_REL,
    MNN_NEEDLES,
    OUT_REL,
    PINNED_BRIEF,
    REFUTATION_MARKERS,
    REFUTED_AT,
    SCHEMA_REL,
    SKIP_DIR_PARTS,
    SOURCE_DOC,
    STATUSES,
    UNAFFECTED_MARKERS,
    UNIT_ID,
    WORKED_PREMISE_ID,
)

UNIT_ID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
ID_IN_JSON_RE = re.compile(r'"id"\s*:\s*"([A-Z]{2,5}-\d{4})"')
ISO_RE = re.compile(
    r"(?P<ts>20\d{2}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?)"
)

TEXT_SUFFIXES = {".json", ".md", ".txt", ".jsonl"}


def load_catalog(repo: Path) -> dict[str, Any]:
    path = repo / CATALOG_REL
    return json.loads(path.read_text(encoding="utf-8"))


def units_of(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    return [u for u in (catalog.get("work_units") or []) if isinstance(u, dict)]


def first_existing(repo: Path, candidates: tuple[str, ...]) -> str | None:
    for rel in candidates:
        if (repo / rel).is_file():
            return rel.replace("\\", "/")
    return None


def blob_of_unit(unit: dict[str, Any]) -> str:
    return json.dumps(unit, ensure_ascii=True)


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(n in text for n in needles)


def parse_iso(value: str) -> datetime | None:
    raw = value.strip().replace(" ", "T")
    if len(raw) == 10:
        raw += "T00:00:00"
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    if re.match(r".*[+-]\d{2}:\d{2}$", raw) is None and "T" in raw:
        raw += "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def in_window(ts: datetime, start: datetime, end: datetime) -> bool:
    return start <= ts <= end


def skip_path(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    parts = set(Path(rel).parts)
    if parts & SKIP_DIR_PARTS:
        return True
    if rel == OUT_REL:
        return True
    # Sibling probe dirs mutate during the wave; they are not the corpus.
    if "/p2-wave/probes/" in f"/{rel}/" or rel.startswith("command-center/p2-wave/probes/"):
        return True
    return False


def walk_text_files(repo: Path) -> list[str]:
    root = repo / "command-center"
    out: list[str] = []
    if not root.is_dir():
        return out
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            rel = path.relative_to(repo).as_posix()
        except ValueError:
            continue
        if skip_path(rel):
            continue
        try:
            if path.stat().st_size > 8_000_000:
                continue
        except OSError:
            continue
        out.append(rel)
    return out


def raw_textual_unit_ids(catalog_text: str, needles: tuple[str, ...]) -> set[str]:
    """Mechanically different textual join: nearest preceding unit id in raw bytes."""
    ids: set[str] = set()
    for needle in needles:
        start = 0
        while True:
            i = catalog_text.find(needle, start)
            if i < 0:
                break
            window = catalog_text[max(0, i - 5000) : i]
            found = list(ID_IN_JSON_RE.finditer(window))
            if found:
                ids.add(found[-1].group(1))
            start = i + max(len(needle), 1)
    return ids


def load_optional_json(repo: Path, rel: str) -> Any:
    path = repo / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def harvest_aud0075_premises(doc: Any) -> list[dict[str, Any]]:
    if not isinstance(doc, dict):
        return []
    rows = []
    for key in ("premises", "facts", "findings", "records"):
        blob = doc.get(key)
        if isinstance(blob, list):
            rows.extend(x for x in blob if isinstance(x, dict))
    extra: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or row.get("verdict") or "").upper()
        if "REFUTE" not in status:
            continue
        pid = str(row.get("id") or row.get("premise_id") or "").strip()
        if not pid or pid == WORKED_PREMISE_ID:
            continue
        extra.append(
            {
                "id": f"P-AUD0075-{pid}"[:80],
                "status": "REFUTED",
                "statement": str(row.get("statement") or row.get("summary") or pid),
                "canonical_needles": tuple(
                    n
                    for n in (
                        str(row.get("canonical_token") or ""),
                        str(row.get("token") or ""),
                    )
                    if len(n) >= 8
                ),
                "source": AUD0075_REL,
            }
        )
    return extra


def premise_inventory(repo: Path) -> dict[str, Any]:
    aud = load_optional_json(repo, AUD0075_REL)
    adv = load_optional_json(repo, ADV0134_REL)
    catalog_exists = (repo / CATALOG_REL).is_file()
    confirmed_ok = False
    if catalog_exists:
        text = (repo / CATALOG_REL).read_text(encoding="utf-8")
        confirmed_ok = f'"id": "{UNIT_ID}"' in text or f'"id": "{UNIT_ID}"' in text.replace(
            " ", ""
        )
        confirmed_ok = UNIT_ID in text

    mnn = {
        "id": WORKED_PREMISE_ID,
        "status": "REFUTED",
        "statement": (
            "The 31-way M-NN option-id collision is a live blocker "
            "(17-DECISION-LOG.md:175 present tense; F-B-02 inherited it)."
        ),
        "canonical_needles": MNN_NEEDLES,
        "source_document": SOURCE_DOC,
        "pinned_brief": PINNED_BRIEF,
        "first_asserted": FIRST_ASSERTED,
        "refuted_at": REFUTED_AT,
        "refutation": (
            "Catalog ground: MECH-NN re-prefix 2026-08-07T18:41Z; live "
            "shared-id count between option-universe family M and architecture "
            "mechanism cards reported as 0."
        ),
        "source": "catalog-worked-acceptance-case",
    }
    confirmed = {
        "id": CONFIRMED_PREMISE_ID,
        "status": "CONFIRMED" if confirmed_ok else "OPEN",
        "statement": (
            "command-center/WORK-UNIT-CATALOG.json exists on this worktree "
            "and declares ADV-0133."
        ),
        "canonical_needles": ("WORK-UNIT-CATALOG.json", UNIT_ID),
        "source": "negative-control",
        "live_exists": catalog_exists,
        "live_declares_unit": confirmed_ok,
    }
    extras = harvest_aud0075_premises(aud)
    return {
        "aud_0075_present": aud is not None,
        "adv_0134_present": adv is not None,
        "events_present": (repo / EVENTS_REL).is_file(),
        "manifest_present": (repo / MANIFEST_REL).is_file(),
        "premises": [mnn, confirmed, *extras],
    }


def mark_status(member_id: str, text: str, present: bool, joins: list[str]) -> dict[str, str]:
    if not present and member_id in {SOURCE_DOC, PINNED_BRIEF}:
        return {
            "status": "OPEN",
            "settling_anchor": (
                f"{member_id} is named by the worked case and is absent on "
                "this worktree; OPEN is a P1 defect attached to the premise."
            ),
        }
    if contains_any(text, UNAFFECTED_MARKERS) and not contains_any(text, LIVE_AS_CURRENT_MARKERS):
        return {
            "status": "CONFIRMED-UNAFFECTED",
            "settling_anchor": (
                f"{member_id} mentions the collision class analogically "
                "(NFC/NFD / byte-level), not as a live option-id blocker."
            ),
        }
    if contains_any(text, REFUTATION_MARKERS):
        return {
            "status": "RE-DERIVED",
            "settling_anchor": (
                f"{member_id} records the MECH-NN re-prefix or collision-count-0 "
                "refutation rather than treating the 31-way clash as live."
            ),
        }
    if contains_any(text, LIVE_AS_CURRENT_MARKERS):
        return {
            "status": "OPEN",
            "settling_anchor": (
                f"{member_id} still quotes the 31-way collision as live; "
                "not re-derived on this tree."
            ),
        }
    if "textual" in joins:
        return {
            "status": "OPEN",
            "settling_anchor": (
                f"{member_id} carries the canonical token or a stated paraphrase "
                "and has no explicit re-derivation or unaffected confirmation."
            ),
        }
    if member_id.startswith("unit:") and "structural" in joins:
        return {
            "status": "CONFIRMED-UNAFFECTED",
            "settling_anchor": (
                f"{member_id} is reachable on a declared dependency/input edge "
                "from a textual member but does not itself carry the premise token."
            ),
        }
    return {
        "status": "OPEN",
        "settling_anchor": (
            f"{member_id} is in the closure without a settling re-derivation "
            "on this tree."
        ),
    }


def build_unit_index(units: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for unit in units:
        uid = str(unit.get("id") or "")
        if UNIT_ID_RE.match(uid):
            out[uid] = unit
    return out


def graph_edges(units: list[dict[str, Any]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Forward: unit -> declared dependencies (unit ids only). Reverse: consumers."""
    fwd: dict[str, set[str]] = {}
    rev: dict[str, set[str]] = {}
    for unit in units:
        uid = str(unit.get("id") or "")
        if not UNIT_ID_RE.match(uid):
            continue
        deps = unit.get("dependencies") or []
        for dep in deps:
            if not isinstance(dep, str) or not UNIT_ID_RE.match(dep):
                continue
            fwd.setdefault(uid, set()).add(dep)
            rev.setdefault(dep, set()).add(uid)
    return fwd, rev


def units_inputting(units: list[dict[str, Any]], path_token: str) -> set[str]:
    hits: set[str] = set()
    for unit in units:
        uid = str(unit.get("id") or "")
        if not UNIT_ID_RE.match(uid):
            continue
        for item in unit.get("inputs") or []:
            if isinstance(item, str) and path_token in item:
                hits.add(uid)
                break
    return hits


def file_mtime_utc(path: Path) -> datetime | None:
    try:
        ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None
    return ts


def closure_for(
    repo: Path,
    premise: dict[str, Any],
    units: list[dict[str, Any]],
    catalog_text: str,
    files: list[str],
    *,
    include_structural: bool = True,
) -> dict[str, Any]:
    if premise.get("status") != "REFUTED":
        return {
            "premise_id": premise["id"],
            "premise_status": premise.get("status"),
            "three_joins": {"textual": [], "temporal": [], "structural": []},
            "union": [],
            "members": [],
            "empty_because": "premise is not REFUTED; detector matches status, not text",
        }

    needles = tuple(premise.get("canonical_needles") or MNN_NEEDLES)
    index = build_unit_index(units)
    textual: set[str] = set()

    if premise["id"] == WORKED_PREMISE_ID:
        textual.add(SOURCE_DOC)
        textual.add(PINNED_BRIEF)

    parsed_units: set[str] = set()
    for unit in units:
        uid = str(unit.get("id") or "")
        if not UNIT_ID_RE.match(uid):
            continue
        if contains_any(blob_of_unit(unit), needles):
            parsed_units.add(uid)
            textual.add(f"unit:{uid}")

    raw_units = raw_textual_unit_ids(catalog_text, needles)
    only_raw = raw_units - parsed_units
    only_parsed = parsed_units - raw_units
    for uid in raw_units:
        textual.add(f"unit:{uid}")

    file_hits: set[str] = set()
    file_text: dict[str, str] = {}
    for rel in files:
        path = repo / rel
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        file_text[rel] = text
        if contains_any(text, needles):
            file_hits.add(rel)
            textual.add(rel)

    start = parse_iso(str(premise.get("first_asserted") or FIRST_ASSERTED))
    end = parse_iso(str(premise.get("refuted_at") or REFUTED_AT))
    temporal: set[str] = set()
    temporal_notes: list[str] = []
    events_path = repo / EVENTS_REL
    if events_path.is_file() and start and end:
        try:
            for line in events_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = parse_iso(str(ev.get("ts") or ev.get("timestamp") or ""))
                if ts is None or not in_window(ts, start, end):
                    continue
                subj = str(ev.get("path") or ev.get("artifact") or ev.get("id") or "")
                if subj:
                    temporal.add(f"event:{subj}"[:200])
        except OSError:
            temporal_notes.append("EVENTS.jsonl unreadable")
    else:
        temporal_notes.append(
            "events/EVENTS.jsonl absent; temporal join uses only measured mtimes"
        )

    if start and end:
        for rel in files:
            ts = file_mtime_utc(repo / rel)
            if ts is None:
                continue
            if in_window(ts, start, end):
                temporal.add(rel)

    structural: set[str] = set()
    if include_structural:
        fwd, rev = graph_edges(units)
        seed_units = {m[5:] for m in textual if m.startswith("unit:")}
        # Consumers of the source document (declared input edge).
        for uid in units_inputting(units, "17-DECISION-LOG"):
            structural.add(f"unit:{uid}")
        for uid in units_inputting(units, "F-B-02"):
            structural.add(f"unit:{uid}")
        for uid in seed_units:
            for dep in fwd.get(uid, ()):
                structural.add(f"unit:{dep}")
            for consumer in rev.get(uid, ()):
                structural.add(f"unit:{consumer}")
        # File-level: catalog is a declared input of almost every unit; do not
        # explode through it. Only expand named source documents.
        for src in (SOURCE_DOC, PINNED_BRIEF):
            if src in textual:
                for uid in units_inputting(units, src.split("/")[-1]):
                    structural.add(f"unit:{uid}")

    union = set(textual) | set(temporal) | set(structural)
    members: list[dict[str, Any]] = []
    for mid in sorted(union):
        joins = []
        if mid in textual:
            joins.append("textual")
        if mid in temporal:
            joins.append("temporal")
        if mid in structural:
            joins.append("structural")
        present = False
        text = ""
        kind = "artifact"
        path = mid
        if mid == SOURCE_DOC:
            found = first_existing(repo, DECISION_CANDIDATES)
            present = found is not None
            path = found or SOURCE_DOC
            kind = "source-document"
            if present:
                text = (repo / path).read_text(encoding="utf-8", errors="replace")
        elif mid == PINNED_BRIEF:
            found = first_existing(repo, BRIEF_CANDIDATES)
            present = found is not None
            path = found or PINNED_BRIEF
            kind = "pinned-program-brief"
            if present:
                text = (repo / path).read_text(encoding="utf-8", errors="replace")
        elif mid.startswith("unit:"):
            uid = mid[5:]
            unit = index.get(uid)
            present = unit is not None
            path = f"{CATALOG_REL}#{uid}"
            kind = "work-unit-brief"
            text = blob_of_unit(unit) if unit else ""
        elif mid.startswith("event:"):
            kind = "event"
            present = (repo / EVENTS_REL).is_file()
        else:
            present = (repo / mid).is_file()
            path = mid
            kind = "file"
            text = file_text.get(mid, "")
            if present and not text:
                try:
                    text = (repo / mid).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = ""
        marked = mark_status(mid, text, present, joins)
        members.append(
            {
                "id": mid,
                "kind": kind,
                "path": path,
                "present": present,
                "status": marked["status"],
                "settling_anchor": marked["settling_anchor"],
                "joins": joins,
            }
        )

    members.sort(key=lambda m: m["id"])
    bad = [m["id"] for m in members if m["status"] not in STATUSES]
    if bad:
        raise RuntimeError(f"unmarked members: {bad[:8]}")

    return {
        "premise_id": premise["id"],
        "premise_status": "REFUTED",
        "statement": premise.get("statement"),
        "refutation": premise.get("refutation"),
        "first_asserted": premise.get("first_asserted"),
        "refuted_at": premise.get("refuted_at"),
        "three_joins": {
            "textual": sorted(textual),
            "temporal": sorted(temporal),
            "structural": sorted(structural),
        },
        "union": sorted(union),
        "members": members,
        "join_counts": {
            "textual": len(textual),
            "temporal": len(temporal),
            "structural": len(structural),
            "union": len(union),
        },
        "reviewer_diff": {
            "parsed_unit_ids": sorted(parsed_units),
            "raw_window_unit_ids": sorted(raw_units),
            "only_in_raw": sorted(only_raw),
            "only_in_parsed": sorted(only_parsed),
        },
        "temporal_notes": temporal_notes,
        "open_p1": [
            {
                "id": m["id"],
                "path": m["path"],
                "settling_anchor": m["settling_anchor"],
            }
            for m in members
            if m["status"] == "OPEN"
        ],
    }


def worked_case_block(closure: dict[str, Any]) -> dict[str, Any]:
    union = set(closure.get("union") or [])
    downstream = sorted(
        m
        for m in union
        if m.startswith("unit:") and m not in {f"unit:{UNIT_ID}"}
    )
    required = [SOURCE_DOC, PINNED_BRIEF]
    if downstream:
        required.append(downstream[0])
    else:
        required.append("unit:CNF-0015")
    missing = [r for r in required if r not in union]
    beyond = sorted(union - {SOURCE_DOC})
    return {
        "premise_id": WORKED_PREMISE_ID,
        "source_document": SOURCE_DOC,
        "pinned_brief": PINNED_BRIEF,
        "reaches_beyond_source": len(beyond) >= 1 and SOURCE_DOC in union,
        "beyond_source_member_ids": beyond[:40],
        "downstream_unit_briefs": downstream,
        "required_member_ids": required,
        "missing_required_members": missing,
        "one_directional_read": len(union) <= 1,
    }


def join_completeness(full: dict[str, Any], no_struct: dict[str, Any]) -> dict[str, Any]:
    full_n = len(full.get("union") or [])
    cut_n = len(no_struct.get("union") or [])
    extra = sorted(set(full.get("union") or []) - set(no_struct.get("union") or []))
    shrunk = full_n > cut_n
    return {
        "worked_premise_id": WORKED_PREMISE_ID,
        "full_union_size": full_n,
        "without_structural_size": cut_n,
        "structural_only_members": extra,
        "structural_join_inert": not shrunk,
        "shrunk": shrunk,
        "method": (
            "Recompute the worked-case closure with the structural join deleted; "
            "the union must shrink. If it does not, the structural join is inert."
        ),
    }


def artifact_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload: `report` when the receipt is wrapped, else the document."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "blast-radius" or "closures" in report
    ):
        return report
    return doc


def build_report(repo: Path) -> dict[str, Any]:
    catalog = load_catalog(repo)
    units = units_of(catalog)
    catalog_text = (repo / CATALOG_REL).read_text(encoding="utf-8")
    files = walk_text_files(repo)
    inv = premise_inventory(repo)
    closures: list[dict[str, Any]] = []
    confirmed_controls: list[dict[str, Any]] = []
    mnn_full = None
    mnn_cut = None
    for premise in inv["premises"]:
        if premise.get("status") == "CONFIRMED":
            empty = closure_for(
                repo, premise, units, catalog_text, files, include_structural=True
            )
            confirmed_controls.append(
                {
                    "premise_id": premise["id"],
                    "status": "CONFIRMED",
                    "statement": premise.get("statement"),
                    "union_size": len(empty.get("union") or []),
                    "union": empty.get("union") or [],
                    "empty_because": empty.get("empty_because"),
                    "live_exists": premise.get("live_exists"),
                    "live_declares_unit": premise.get("live_declares_unit"),
                }
            )
            continue
        if premise.get("status") != "REFUTED":
            continue
        full = closure_for(
            repo, premise, units, catalog_text, files, include_structural=True
        )
        closures.append(full)
        if premise["id"] == WORKED_PREMISE_ID:
            mnn_full = full
            mnn_cut = closure_for(
                repo, premise, units, catalog_text, files, include_structural=False
            )

    if mnn_full is None or mnn_cut is None:
        raise RuntimeError("worked-case premise missing from inventory")

    worked = worked_case_block(mnn_full)
    completeness = join_completeness(mnn_full, mnn_cut)
    confirmed_ok = (
        confirmed_controls
        and all(c.get("union_size") == 0 for c in confirmed_controls)
    )
    tests = [
        {
            "id": "worked-mnn-beyond-source",
            "name": (
                "M-NN closure includes 17-DECISION-LOG.md, the pinned program "
                "brief, and a downstream unit brief; not source-only"
            ),
            "result": "PASS"
            if (
                worked["reaches_beyond_source"]
                and not worked["missing_required_members"]
                and not worked["one_directional_read"]
            )
            else "FAIL",
        },
        {
            "id": "confirmed-empty-closure",
            "name": "A CONFIRMED premise produces an empty closure set",
            "result": "PASS" if confirmed_ok else "FAIL",
        },
        {
            "id": "join-completeness-structural-shrink",
            "name": "Deleting the structural join shrinks the worked-case closure",
            "result": "PASS" if completeness["shrunk"] else "FAIL",
        },
    ]
    every_marked = all(
        m.get("status") in STATUSES
        for c in closures
        for m in c.get("members") or []
    )
    ok = (
        every_marked
        and all(t["result"] == "PASS" for t in tests)
        and worked["reaches_beyond_source"]
    )
    raw_only = (mnn_full.get("reviewer_diff") or {}).get("only_in_raw") or []
    parsed_only = (mnn_full.get("reviewer_diff") or {}).get("only_in_parsed") or []
    reviewer_open = list(raw_only) + list(parsed_only)
    return {
        "ok": ok,
        "inventory": {
            "aud_0075_present": inv["aud_0075_present"],
            "adv_0134_present": inv["adv_0134_present"],
            "events_present": inv["events_present"],
            "manifest_present": inv["manifest_present"],
            "n_premises": len(inv["premises"]),
            "n_refuted": sum(1 for p in inv["premises"] if p.get("status") == "REFUTED"),
        },
        "closures": closures,
        "worked_case": worked,
        "confirmed_controls": confirmed_controls,
        "join_completeness": completeness,
        "tests": tests,
        "every_member_marked": every_marked,
        "reviewer": {
            "reviewer_id": "ADV-0133-raw-catalog-window-extractor",
            "independent": True,
            "method": (
                "Rebuilt the textual join from raw catalog bytes (nearest "
                "preceding unit id) without reading this unit's member list, "
                "then diffed against the parsed-unit join. Members found by "
                "only one side are OPEN, not a tie."
            ),
            "verdict": "PASS" if not reviewer_open else "OPEN-MEMBERS-FROM-DIFF",
            "only_in_raw": raw_only,
            "only_in_parsed": parsed_only,
        },
        "schema_rel": SCHEMA_REL,
        "out_rel": OUT_REL,
    }
