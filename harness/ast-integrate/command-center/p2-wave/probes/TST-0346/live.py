"""Load live requirement and test inventories from declared structured sources.

Does not invent requirement ids or test ids by reading catalog prose, spec
markdown, or comments. Missing inventories are named; completeness is
questioned rather than silently defaulted to "fully covered".
"""
from __future__ import annotations

import json
from pathlib import Path

from matrix import compute_matrix, lists_are_the_deliverable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CC0024_CANDIDATES = (
    "command-center/receipts/CC-0024.json",
    "command-center/requirements/CC-0024.json",
    "command-center/requirements/inventory.json",
)
TEST_REGISTRY_CANDIDATES = (
    "command-center/TEST-REGISTRY.json",
    "TEST-REGISTRY.json",
)
TST0326_CANDIDATES = (
    "command-center/receipts/TST-0326.json",
)
CLAIM_REGISTRY_CANDIDATES = (
    "command-center/CLAIM-REGISTRY.json",
)


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _first_present(rels: tuple[str, ...]) -> tuple[str | None, object]:
    for rel in rels:
        path = REPO / rel
        if path.is_file() and path.stat().st_size > 0:
            return rel, _load_json(path)
    return None, None


def _ids_from_sequence(seq, keys: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    if not isinstance(seq, list):
        return out
    for item in seq:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
            continue
        if not isinstance(item, dict):
            continue
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
                break
    return out


def extract_requirement_ids(doc) -> list[str]:
    if not isinstance(doc, dict):
        return []
    for key in ("requirement_ids", "ids"):
        raw = doc.get(key)
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
    for key in ("requirements", "requirement_records", "records", "items"):
        ids = _ids_from_sequence(
            doc.get(key),
            ("id", "requirement_id", "req_id", "requirement"),
        )
        if ids:
            return ids
    evidence = doc.get("evidence")
    if isinstance(evidence, dict):
        nested = extract_requirement_ids(evidence)
        if nested:
            return nested
    return []


def extract_test_ids(doc) -> list[str]:
    if not isinstance(doc, dict):
        return []
    for key in ("test_ids", "discovered_test_ids", "ids"):
        raw = doc.get(key)
        if isinstance(raw, list) and raw and all(not isinstance(x, dict) for x in raw):
            return [str(x).strip() for x in raw if str(x).strip()]
    collected: list[str] = []
    for key in ("tests", "entries", "items"):
        collected.extend(
            _ids_from_sequence(doc.get(key), ("id", "test_id", "nodeid", "name"))
        )
    for suite in doc.get("suites") or []:
        if not isinstance(suite, dict):
            continue
        collected.extend(
            _ids_from_sequence(suite.get("tests"), ("id", "test_id", "name", "nodeid"))
        )
        path = suite.get("path")
        if isinstance(path, str) and path.strip():
            collected.append(path.strip())
        name = suite.get("id") or suite.get("name")
        if isinstance(name, str) and name.strip() and not suite.get("tests"):
            collected.append(name.strip())
    for inv in doc.get("invariants") or []:
        if not isinstance(inv, dict):
            continue
        tests = inv.get("tests")
        if isinstance(tests, list):
            collected.extend(str(t).strip() for t in tests if str(t).strip())
    evidence = doc.get("evidence")
    if isinstance(evidence, dict):
        collected.extend(extract_test_ids(evidence))
        for key in ("orphans", "ghosts", "discovered_ids", "registry_ids"):
            collected.extend(
                str(x).strip()
                for x in (evidence.get(key) or [])
                if str(x).strip() and not isinstance(x, dict)
            )
    return [x for x in collected if x]


def extract_declared_links(doc) -> list[tuple[str, str]]:
    if not isinstance(doc, dict):
        return []
    pairs: list[tuple[str, str]] = []
    for key in ("links", "bindings", "requirement_test_links", "trace_links"):
        raw = doc.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                req, test = str(item[0]).strip(), str(item[1]).strip()
                if req and test:
                    pairs.append((req, test))
            elif isinstance(item, dict):
                req = str(
                    item.get("requirement_id")
                    or item.get("req_id")
                    or item.get("requirement")
                    or ""
                ).strip()
                test = str(item.get("test_id") or item.get("test") or "").strip()
                if req and test:
                    pairs.append((req, test))
    for inv in doc.get("invariants") or []:
        if not isinstance(inv, dict):
            continue
        req = str(inv.get("id") or inv.get("requirement_id") or "").strip()
        tests = inv.get("tests")
        if req and isinstance(tests, list):
            for test in tests:
                t = str(test).strip()
                if t:
                    pairs.append((req, t))
    evidence = doc.get("evidence")
    if isinstance(evidence, dict):
        pairs.extend(extract_declared_links(evidence))
    return pairs


def extract_invariant_test_pairs(doc) -> list[dict]:
    """TEST-REGISTRY TI-* rows are invariants, not CC-0024 owner requirements."""
    pairs: list[dict] = []
    if not isinstance(doc, dict):
        return pairs
    for inv in doc.get("invariants") or []:
        if not isinstance(inv, dict):
            continue
        iid = str(inv.get("id") or "").strip()
        tests = inv.get("tests")
        if not iid or not isinstance(tests, list):
            continue
        for test in tests:
            t = str(test).strip()
            if t:
                pairs.append({"invariant_id": iid, "test_id": t})
    return pairs


def _cc0024_extractor_fallback() -> tuple[list[str], dict]:
    """Read-only: CC-0024 extract.py over its existing fixture. Does not write."""
    extract_py = REPO / "command-center/p2-wave/probes/CC-0024/extract.py"
    fixture = REPO / "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
    meta = {
        "extractor": "command-center/p2-wave/probes/CC-0024/extract.py",
        "fixture": "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md",
        "used": False,
        "ids": [],
        "reason": None,
    }
    if not extract_py.is_file() or not fixture.is_file():
        meta["reason"] = "extractor or fixture absent"
        return [], meta
    import importlib.util

    spec = importlib.util.spec_from_file_location("cc0024_extract_tst0346", extract_py)
    if spec is None or spec.loader is None:
        meta["reason"] = "importlib failed to load extract.py"
        return [], meta
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    lines = mod._read_numbered(fixture)
    result = mod.extract_from_lines(lines, units=[])
    ids: list[str] = []
    for rec in result.get("requirements") or []:
        if isinstance(rec, dict):
            rid = str(rec.get("id") or "").strip()
            if rid:
                ids.append(rid)
    meta["used"] = True
    meta["ids"] = list(ids)
    meta["floor_recall_passed"] = bool((result.get("floor_recall") or {}).get("passed"))
    meta["reason"] = (
        "Published CC-0024 receipt is absent; requirement ids taken from the "
        "CC-0024 extractor over its on-disk fixture. Completeness is questioned "
        "because this is not command-center/receipts/CC-0024.json."
    )
    return ids, meta


def claim_probe_census(doc) -> dict:
    """Related join only. Claims are not owner-requirement records."""
    claims = []
    if isinstance(doc, dict):
        raw = doc.get("claims")
        if isinstance(raw, list):
            claims = [c for c in raw if isinstance(c, dict)]
    rows = []
    for claim in claims:
        cid = str(claim.get("id") or "").strip()
        if not cid:
            continue
        probe = str(
            claim.get("settling_probe") or claim.get("source_probe") or ""
        ).strip()
        rows.append(
            {
                "claim_id": cid,
                "has_declared_probe": bool(probe),
                "probe": probe or None,
            }
        )
    with_probe = sorted(r["claim_id"] for r in rows if r["has_declared_probe"])
    without_probe = sorted(r["claim_id"] for r in rows if not r["has_declared_probe"])
    return {
        "axis": "claim-to-probe (not requirement-to-test)",
        "claim_ids": sorted(r["claim_id"] for r in rows),
        "claims_with_declared_probe": with_probe,
        "claims_without_declared_probe": without_probe,
        "folded_into_requirement_test_matrix": False,
        "rows": rows,
    }


def load_live() -> dict:
    cc_rel, cc_doc = _first_present(CC0024_CANDIDATES)
    tr_rel, tr_doc = _first_present(TEST_REGISTRY_CANDIDATES)
    d_rel, d_doc = _first_present(TST0326_CANDIDATES)
    cr_rel, cr_doc = _first_present(CLAIM_REGISTRY_CANDIDATES)

    missing: list[str] = []
    sources: dict[str, dict] = {}

    def note(
        name: str, rel: str | None, candidates: tuple[str, ...], present: bool
    ) -> None:
        sources[name] = {
            "candidates": list(candidates),
            "path": rel,
            "present": present,
        }
        if not present:
            missing.append(f"{name} absent (looked for {list(candidates)})")

    note("CC-0024-requirement-inventory", cc_rel, CC0024_CANDIDATES, cc_rel is not None)
    note("TEST-REGISTRY", tr_rel, TEST_REGISTRY_CANDIDATES, tr_rel is not None)
    note("TST-0326-discovery", d_rel, TST0326_CANDIDATES, d_rel is not None)
    note("CLAIM-REGISTRY", cr_rel, CLAIM_REGISTRY_CANDIDATES, cr_rel is not None)

    requirements: list[str] = []
    tests: list[str] = []
    links: list[tuple[str, str]] = []
    if isinstance(cc_doc, dict):
        requirements.extend(extract_requirement_ids(cc_doc))
        links.extend(extract_declared_links(cc_doc))

    fallback_ids, fallback_meta = ([], {})
    if not requirements:
        fallback_ids, fallback_meta = _cc0024_extractor_fallback()
        requirements.extend(fallback_ids)
        sources["CC-0024-extractor-fallback"] = fallback_meta

    invariant_pairs: list[dict] = []
    if isinstance(tr_doc, dict):
        tests.extend(extract_test_ids(tr_doc))
        invariant_pairs = extract_invariant_test_pairs(tr_doc)
        # TI-* invariant rows are not owner-requirement records. Keep them off
        # the requirement×test join so they cannot mint REQ ids or valid links.
    if isinstance(d_doc, dict):
        tests.extend(extract_test_ids(d_doc))
        links.extend(extract_declared_links(d_doc))

    cc_receipt_absent = cc_rel is None
    test_inventory_absent = tr_rel is None and d_rel is None
    completeness_questioned = cc_receipt_absent or test_inventory_absent
    reasons = list(missing)
    if cc_receipt_absent:
        reasons.append(
            "Requirement inventory completeness is questioned: "
            "command-center/receipts/CC-0024.json is absent. "
            "Ids below come from the CC-0024 extractor fixture fallback when "
            "that file exists; they are not minted from catalog tests_required "
            "prose."
        )
    if test_inventory_absent:
        reasons.append(
            "Test inventory completeness is questioned: TEST-REGISTRY.json and "
            "TST-0326 discovery output are both absent, so this unit will not "
            "mint test ids from catalog tests_required prose."
        )
    elif d_rel is None:
        reasons.append(
            "TST-0326 discovery receipt is absent; live test ids are the "
            "TEST-REGISTRY named tests and suite paths only, not a full "
            "on-disk discovery walk."
        )

    matrix = compute_matrix(requirements, tests, links)
    claims = (
        claim_probe_census(cr_doc)
        if isinstance(cr_doc, dict)
        else {
            "axis": "claim-to-probe (not requirement-to-test)",
            "claim_ids": [],
            "claims_with_declared_probe": [],
            "claims_without_declared_probe": [],
            "folded_into_requirement_test_matrix": False,
            "rows": [],
        }
    )
    invariant_census = {
        "axis": "TEST-REGISTRY-invariant-to-test (not requirement-to-test)",
        "pairs": invariant_pairs,
        "invariant_ids": sorted({p["invariant_id"] for p in invariant_pairs}),
        "folded_into_requirement_test_matrix": False,
    }

    owner_decision_needed = []
    if matrix["untested_requirements"]:
        owner_decision_needed.append("coverage-hole:untested-requirements")
    if matrix["untraced_tests"]:
        owner_decision_needed.append(
            "dead-weight-or-undocumented-requirement:untraced-tests"
        )
    if completeness_questioned:
        owner_decision_needed.append("inventory-completeness:named-inputs-absent")

    return {
        "claim_to_probe_census": claims,
        "completeness_questioned": completeness_questioned,
        "completeness_reasons": reasons,
        "invariant_to_test_census": invariant_census,
        "lists_are_the_deliverable": lists_are_the_deliverable(matrix),
        "matrix": matrix,
        "missing_inputs": missing,
        "owner_decision_needed": owner_decision_needed,
        "silent_default_used": False,
        "sources": sources,
    }
