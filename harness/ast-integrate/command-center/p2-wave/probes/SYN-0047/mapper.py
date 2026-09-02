"""Three-way coverage join: spec class x test x mutation record x root cause.

COVERED requires a bound test AND a mutation record that FIRED (CC-0014).
A bound test without a mutation record is CLAIMED-NOT-PROVEN, never COVERED.
"""
from __future__ import annotations

from typing import Any

COVERED = "COVERED"
CLAIMED = "CLAIMED-NOT-PROVEN"
UNCOVERED = "UNCOVERED"
UNMATCHED = "UNMATCHED"


def _norm(text: Any) -> str:
    return str(text or "").lower()


def class_matches_text(cls: dict, text: str) -> bool:
    blob = _norm(text)
    if not blob:
        return False
    for needle in cls.get("needles") or []:
        n = _norm(needle)
        if n and n in blob:
            return True
    return False


def bind_tests_to_class(cls: dict, tests: list[dict]) -> list[dict]:
    bound: list[dict] = []
    seen: set[str] = set()
    cid = cls["id"]
    for test in tests:
        covers = {_norm(x) for x in (test.get("covers") or [])}
        tid = str(test.get("id") or "")
        blob = " ".join(
            [
                tid,
                str(test.get("path") or ""),
                str(test.get("name") or ""),
                str(test.get("text") or ""),
                " ".join(str(x) for x in (test.get("covers") or [])),
            ]
        )
        hit = cid.lower() in covers or class_matches_text(cls, blob)
        if hit and tid not in seen:
            seen.add(tid)
            bound.append(
                {
                    "id": tid,
                    "path": test.get("path"),
                    "kind": test.get("kind"),
                    "has_mutation_record": bool(test.get("has_mutation_record")),
                }
            )
    return bound


def mutations_for_test(test_id: str, mutations: list[dict]) -> list[dict]:
    tid = _norm(test_id)
    return [m for m in mutations if _norm(m.get("test_id")) == tid]


def mutation_proves(muts: list[dict]) -> bool:
    for m in muts:
        result = str(m.get("result") or m.get("status") or "").upper()
        broken_fails = m.get("broken_fails")
        good_passes = m.get("good_passes")
        if result in {"FIRED", "PROTECTING", "KILLED"}:
            if broken_fails is False or good_passes is False:
                continue
            return True
        if broken_fails is True and good_passes is True:
            return True
    return False


def status_for(bound: list[dict], mutations: list[dict]) -> str:
    if not bound:
        return UNCOVERED
    for test in bound:
        muts = mutations_for_test(test["id"], mutations)
        if mutation_proves(muts) or (
            test.get("has_mutation_record") and mutation_proves(muts)
        ):
            return COVERED
        if mutation_proves(muts):
            return COVERED
    for test in bound:
        if mutation_proves(mutations_for_test(test["id"], mutations)):
            return COVERED
    return CLAIMED


def map_classes(
    classes: list[dict],
    tests: list[dict],
    mutations: list[dict],
    causes: list[dict],
) -> list[dict]:
    rows: list[dict] = []
    for cls in classes:
        bound = bind_tests_to_class(cls, tests)
        proven_ids = [
            t["id"]
            for t in bound
            if mutation_proves(mutations_for_test(t["id"], mutations))
        ]
        st = COVERED if proven_ids else (CLAIMED if bound else UNCOVERED)
        matched_causes = [
            c["id"]
            for c in causes
            if class_matches_text(cls, " ".join(str(c.get(k) or "") for k in ("id", "name", "label", "text")))
        ]
        test_id = proven_ids[0] if proven_ids else (bound[0]["id"] if bound else None)
        rows.append(
            {
                "id": cls["id"],
                "spec_line": cls["spec_line"],
                "name": cls["name"],
                "gloss_status": cls.get("gloss_status"),
                "status": st,
                "test_id": test_id if test_id else "UNCOVERED",
                "bound_tests": [t["id"] for t in bound],
                "proven_tests": proven_ids,
                "matched_root_causes": matched_causes,
            }
        )
    return rows


def unmatched_causes(causes: list[dict], rows: list[dict]) -> list[dict]:
    matched: set[str] = set()
    for row in rows:
        matched.update(row.get("matched_root_causes") or [])
    out: list[dict] = []
    for c in causes:
        cid = str(c.get("id") or "")
        if cid and cid not in matched:
            out.append(
                {
                    "id": cid,
                    "name": c.get("name") or c.get("label") or cid,
                    "status": UNMATCHED,
                    "reason": "no-listed-spec-class",
                }
            )
    return out


def uncovered_rows(rows: list[dict]) -> list[dict]:
    return [
        {"id": r["id"], "name": r["name"], "status": r["status"], "test_id": r["test_id"]}
        for r in rows
        if r["status"] != COVERED
    ]
