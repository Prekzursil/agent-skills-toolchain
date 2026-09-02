#!/usr/bin/env python3
"""Option-ID coverage mapper for ARC-0111.

Partitions every selected option id into exactly one of:
  mapped | out_of_scope | superseded | unmapped
and reports namespace-ambiguous ids with ALL candidate resolutions,
left UNRESOLVED. Never guesses a namespace.

Totality is computed from independently built lists, not asserted in prose.
Unmapped is the remainder of the selected set after the three explicit
rulings; dropping an id from that remainder is the silently-dropped
failure this unit exists to catch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

EXPECTED_CONTRACTS = [f"ARC-{n:04d}" for n in range(78, 98)]

LIVE_SELECTED_CANDIDATES = (
    "command-center/OPTION-ID-RESOLUTION.json",
    "command-center/selected-option-ids.json",
    "07-OPTION-UNIVERSE.json",
    "command-center/sources/07-OPTION-UNIVERSE.json",
)

LIVE_UNIVERSE_CANDIDATES = (
    "07-OPTION-UNIVERSE.json",
    "command-center/sources/07-OPTION-UNIVERSE.json",
    "command-center/OPTION-ID-RESOLUTION.json",
)

LIVE_CONTRACT_DIR = "command-center/phase4/contracts"

# Catalog-stated namespaces. Used only when defining documents are absent,
# and only as documentation — never as a guessed binding for a live token.
CATALOG_STATED_NAMESPACES = (
    {
        "id": "option-universe",
        "defining_document": "07-OPTION-UNIVERSE",
        "note": "family M, 33 ids (catalog CC-0021 / AUD-0034)",
    },
    {
        "id": "mechanism",
        "defining_document": "13-ARCHITECTURE-CANDIDATES",
        "note": "38 cards, re-prefixed MECH-NN on 2026-08-07",
    },
    {
        "id": "research-harness",
        "defining_document": "wave3/ast-cc/skills/deep-research/SKILL.md",
        "note": "deliverable id Research Harness (M-16)",
    },
    {
        "id": "wave1-mission-grade",
        "defining_document": "wave1/REGISTER.md",
        "note": "single-digit M-1/M-3",
    },
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            token = item.strip()
        elif isinstance(item, Mapping) and isinstance(item.get("id"), str):
            token = item["id"].strip()
        else:
            continue
        if token and token not in seen:
            seen.add(token)
            out.append(token)
    return out


def load_namespaces(universe: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for ns in universe.get("namespaces") or []:
        if not isinstance(ns, Mapping):
            continue
        nid = str(ns.get("id") or "").strip()
        if not nid:
            continue
        ids = set(_as_str_list(ns.get("ids")))
        ids.update(_as_str_list(ns.get("historical_bare_ids")))
        rows.append(
            {
                "id": nid,
                "defining_document": str(ns.get("defining_document") or ""),
                "ids": sorted(ids),
            }
        )
    return rows


def resolve_token(token: str, namespaces: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Return RESOLVED / AMBIGUOUS / ABSENT. Never picks a winner when n>1."""
    token = token.strip()
    candidates = []
    for ns in namespaces:
        ids = ns.get("ids") or []
        if token in ids:
            candidates.append(
                {
                    "namespace": ns.get("id"),
                    "defining_document": ns.get("defining_document") or "",
                }
            )
    if len(candidates) == 0:
        return {
            "id": token,
            "status": "ABSENT",
            "namespace": None,
            "candidates": [],
        }
    if len(candidates) == 1:
        return {
            "id": token,
            "status": "RESOLVED",
            "namespace": candidates[0]["namespace"],
            "candidates": candidates,
        }
    return {
        "id": token,
        "status": "AMBIGUOUS",
        "namespace": None,
        "candidates": candidates,
    }


def load_contract(path: Path) -> dict[str, Any]:
    doc = _read_json(path)
    if not isinstance(doc, dict):
        return {
            "unit_id": path.stem,
            "path": path.as_posix(),
            "covers": [],
            "out_of_scope": [],
            "superseded": [],
            "clauses": [],
        }
    covers: list[str] = []
    clauses_out: list[dict[str, str]] = []
    for clause in doc.get("clauses") or []:
        if not isinstance(clause, Mapping):
            continue
        cid = str(clause.get("id") or "").strip()
        for oid in _as_str_list(clause.get("covers_option_ids")):
            covers.append(oid)
            clauses_out.append(
                {
                    "clause_id": cid or f"{path.stem}.anon",
                    "option_id": oid,
                    "contract": str(doc.get("unit_id") or path.stem),
                }
            )
    covers.extend(_as_str_list(doc.get("covers_option_ids")))
    oos = _as_str_list(doc.get("out_of_scope_option_ids"))
    superseded = _as_str_list(doc.get("superseded_option_ids"))
    # de-dupe covers preserving order
    seen: set[str] = set()
    covers_u: list[str] = []
    for oid in covers:
        if oid not in seen:
            seen.add(oid)
            covers_u.append(oid)
    return {
        "unit_id": str(doc.get("unit_id") or path.stem),
        "path": str(path),
        "covers": covers_u,
        "out_of_scope": oos,
        "superseded": superseded,
        "clauses": clauses_out,
    }


def load_contracts(contract_dir: Path) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    loaded: list[dict[str, Any]] = []
    present: list[str] = []
    absent: list[str] = []
    for uid in EXPECTED_CONTRACTS:
        path = contract_dir / f"{uid}.json"
        if path.is_file() and path.stat().st_size > 0:
            present.append(uid)
            loaded.append(load_contract(path))
        else:
            absent.append(uid)
    return loaded, present, absent


def selected_from_doc(doc: Any, default_source: str) -> tuple[list[str], str]:
    if not isinstance(doc, dict):
        return [], default_source
    for key in ("selected", "selected_ids", "selected_option_ids"):
        if key in doc:
            return _as_str_list(doc.get(key)), str(doc.get("source") or default_source)
    # 07-OPTION-UNIVERSE.json shape: options[] with selected=true
    options = doc.get("options")
    if isinstance(options, list):
        picked = []
        for row in options:
            if isinstance(row, Mapping) and row.get("selected") is True:
                oid = str(row.get("id") or "").strip()
                if oid:
                    picked.append(oid)
        if picked:
            return picked, default_source + "#options[selected=true]"
    return [], default_source


def load_fixture_inputs(fixture_dir: Path) -> dict[str, Any]:
    universe_path = fixture_dir / "option_universe.json"
    selected_path = fixture_dir / "selected_ids.json"
    contract_dir = fixture_dir / "contracts"
    universe = _read_json(universe_path) if universe_path.is_file() else {"namespaces": []}
    selected_doc = _read_json(selected_path) if selected_path.is_file() else {}
    selected, source = selected_from_doc(selected_doc, "fixture:selected-option-ids")
    contracts, present, absent = load_contracts(contract_dir)
    return {
        "mode": "fixture",
        "universe_path": universe_path.as_posix() if universe_path.is_file() else None,
        "selected_path": selected_path.as_posix() if selected_path.is_file() else None,
        "selected_source": source,
        "selected_status": "PRESENT" if selected else "EMPTY",
        "namespaces": load_namespaces(universe),
        "defining_documents_present": True,
        "selected": selected,
        "contracts": contracts,
        "contracts_present": present,
        "contracts_absent": absent,
        "contract_dir": contract_dir.as_posix(),
    }


def load_live_inputs(repo: Path) -> dict[str, Any]:
    selected: list[str] = []
    selected_source = "NEVER_FILLED"
    selected_status = "NEVER_FILLED"
    selected_path = None
    for rel in LIVE_SELECTED_CANDIDATES:
        path = repo / rel
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        try:
            doc = _read_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        picked, src = selected_from_doc(doc, rel)
        if picked:
            selected = picked
            selected_source = src
            selected_status = "PRESENT"
            selected_path = rel
            break
        # File exists but has no selected list — keep looking.
        selected_path = selected_path or rel

    namespaces: list[dict[str, Any]] = []
    universe_path = None
    for rel in LIVE_UNIVERSE_CANDIDATES:
        path = repo / rel
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        try:
            doc = _read_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict) and doc.get("namespaces"):
            namespaces = load_namespaces(doc)
            universe_path = rel
            break

    contract_dir = repo / LIVE_CONTRACT_DIR
    contracts, present, absent = load_contracts(contract_dir)
    return {
        "mode": "live",
        "universe_path": universe_path,
        "selected_path": selected_path,
        "selected_source": selected_source,
        "selected_status": selected_status,
        "namespaces": namespaces,
        "defining_documents_present": bool(namespaces),
        "selected": selected,
        "contracts": contracts,
        "contracts_present": present,
        "contracts_absent": absent,
        "contract_dir": LIVE_CONTRACT_DIR,
        "never_filled_citation": (
            "command-center/WORK-UNIT-CATALOG.json item R-A03: "
            "Prompt-Two selected option IDs (:10514) were never filled"
        ),
    }


def _index_contract_rulings(
    contracts: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, list[dict[str, str]]], set[str], set[str]]:
    covers: dict[str, list[dict[str, str]]] = {}
    oos: set[str] = set()
    superseded: set[str] = set()
    for con in contracts:
        uid = str(con.get("unit_id") or "")
        path = str(con.get("path") or "")
        for clause in con.get("clauses") or []:
            oid = clause.get("option_id")
            if not oid:
                continue
            covers.setdefault(oid, []).append(
                {
                    "contract": clause.get("contract") or uid,
                    "clause_id": clause.get("clause_id") or "",
                    "path": path,
                }
            )
        for oid in con.get("out_of_scope") or []:
            oos.add(oid)
        for oid in con.get("superseded") or []:
            superseded.add(oid)
    return covers, oos, superseded


def classify(inputs: Mapping[str, Any]) -> dict[str, Any]:
    selected = list(inputs.get("selected") or [])
    namespaces = list(inputs.get("namespaces") or [])
    covers, oos_set, superseded_set = _index_contract_rulings(inputs.get("contracts") or [])

    resolutions = [resolve_token(oid, namespaces) for oid in selected]
    ambiguous = [r for r in resolutions if r["status"] == "AMBIGUOUS"]
    ambiguous_ids = {r["id"] for r in ambiguous}

    mapped: list[dict[str, Any]] = []
    out_of_scope: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for res in resolutions:
        oid = res["id"]
        flags: list[str] = []
        if oid in superseded_set:
            flags.append("superseded")
        if oid in oos_set:
            flags.append("out_of_scope")
        # Ambiguous ids are never mapped: binding a clause would guess a card.
        if oid in covers and oid not in ambiguous_ids:
            flags.append("mapped")
        row = {
            "id": oid,
            "resolution": res["status"],
            "namespace": res["namespace"],
            "candidates": res["candidates"],
        }
        if len(flags) > 1:
            conflicts.append({**row, "flags": flags})
            unmapped.append(
                {
                    **row,
                    "reason": "conflict-unmapped",
                    "flags": flags,
                }
            )
        elif flags == ["superseded"]:
            superseded.append(
                {
                    **row,
                    "ruling": "superseded",
                }
            )
        elif flags == ["out_of_scope"]:
            out_of_scope.append({**row, "ruling": "out_of_scope"})
        elif flags == ["mapped"]:
            mapped.append({**row, "clauses": covers[oid]})
        else:
            reason = "ambiguous-unresolved" if oid in ambiguous_ids else "no-contract-clause"
            extra: dict[str, Any] = {**row, "reason": reason}
            if oid in covers and oid in ambiguous_ids:
                extra["clauses_ignored_because_ambiguous"] = covers[oid]
            unmapped.append(extra)

    mapped_ids = [r["id"] for r in mapped]
    oos_ids = [r["id"] for r in out_of_scope]
    sup_ids = [r["id"] for r in superseded]
    unm_ids = [r["id"] for r in unmapped]
    totality = compute_totality(selected, mapped_ids, oos_ids, sup_ids, unm_ids, conflicts)

    return {
        "mode": inputs.get("mode"),
        "selected_source": inputs.get("selected_source"),
        "selected_status": inputs.get("selected_status"),
        "selected_path": inputs.get("selected_path"),
        "universe_path": inputs.get("universe_path"),
        "defining_documents_present": inputs.get("defining_documents_present"),
        "contract_dir": inputs.get("contract_dir"),
        "contracts_present": list(inputs.get("contracts_present") or []),
        "contracts_absent": list(inputs.get("contracts_absent") or []),
        "never_filled_citation": inputs.get("never_filled_citation"),
        "selected": selected,
        "selected_count": len(selected),
        "resolutions": resolutions,
        "mapped": mapped,
        "out_of_scope": out_of_scope,
        "superseded": superseded,
        "unmapped": unmapped,
        "ambiguous": ambiguous,
        "conflicts": conflicts,
        "totality": totality,
        "catalog_stated_namespaces": list(CATALOG_STATED_NAMESPACES),
        "namespaces_loaded": [
            {"id": ns["id"], "id_count": len(ns["ids"]), "defining_document": ns["defining_document"]}
            for ns in namespaces
        ],
    }


def compute_totality(
    selected: list[str],
    mapped: list[str],
    out_of_scope: list[str],
    superseded: list[str],
    unmapped: list[str],
    conflicts: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Independent arithmetic. Unmapped is a list, not 'the rest' asserted in prose.

    A report that drops a selected id from every list fails. A report that
    puts an id in two lists fails disjointness.
    """
    n_m = len(mapped)
    n_o = len(out_of_scope)
    n_s = len(superseded)
    n_u = len(unmapped)
    n_sel = len(selected)
    summed = n_m + n_o + n_s + n_u
    bags = {
        "mapped": mapped,
        "out_of_scope": out_of_scope,
        "superseded": superseded,
        "unmapped": unmapped,
    }
    overlaps: list[dict[str, Any]] = []
    names = list(bags.keys())
    for i, a in enumerate(names):
        sa = set(bags[a])
        for b in names[i + 1 :]:
            both = sorted(sa.intersection(bags[b]))
            if both:
                overlaps.append({"a": a, "b": b, "ids": both})
    union = []
    seen: set[str] = set()
    for name in names:
        for oid in bags[name]:
            if oid not in seen:
                seen.add(oid)
                union.append(oid)
    missing = [oid for oid in selected if oid not in seen]
    extra = [oid for oid in union if oid not in set(selected)]
    holds = (
        summed == n_sel
        and not overlaps
        and not missing
        and not extra
        and not (conflicts or [])
        and len(union) == n_sel
    )
    return {
        "mapped_count": n_m,
        "out_of_scope_count": n_o,
        "superseded_count": n_s,
        "unmapped_count": n_u,
        "selected_count": n_sel,
        "sum": summed,
        "equation": (
            f"{n_m} mapped + {n_o} out_of_scope + {n_s} superseded + "
            f"{n_u} unmapped = {summed} (selected={n_sel})"
        ),
        "holds": holds,
        "overlaps": overlaps,
        "missing_from_buckets": missing,
        "extra_not_selected": extra,
        "conflict_count": len(conflicts or []),
        "computed": True,
    }


def drop_unmapped_mutant(report: Mapping[str, Any]) -> dict[str, Any]:
    """Both-states bad control: omit one unmapped id so totality must fail."""
    selected = list(report.get("selected") or [])
    mapped = [r["id"] for r in report.get("mapped") or []]
    oos = [r["id"] for r in report.get("out_of_scope") or []]
    sup = [r["id"] for r in report.get("superseded") or []]
    unm = [r["id"] for r in report.get("unmapped") or []]
    if not unm:
        raise ValueError("need at least one unmapped id to plant a silent drop")
    dropped = unm[0]
    unm_bad = unm[1:]
    totality = compute_totality(selected, mapped, oos, sup, unm_bad)
    return {"dropped": dropped, "totality": totality}


def fixture_dir(here: Path) -> Path:
    return here / "fixtures"


def run_fixture(here: Path) -> dict[str, Any]:
    return classify(load_fixture_inputs(fixture_dir(here)))


def run_live(repo: Path) -> dict[str, Any]:
    return classify(load_live_inputs(repo))
