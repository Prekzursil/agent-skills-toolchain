#!/usr/bin/env python3
"""Probe 2: documented changes stay silent; rename is not a disposition change.

Independent of probe1's fail-set: this probe re-derives evidence field names
from the two JSON evidence maps (set algebra, not compare().fail) and joins
the renamed candidate through the reverse alias map. A mutant that alarms on
any classification change, or that omits the migration map, is shown red.
The reviewer also re-runs the silent pair (both-states control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import monitor as M  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0075-disposition-drift-monitor.json"
FIX = HERE / "fixtures"
DOC_SMOKE = "wf-doc-smoke"
DOC_PRESERVE = "wf-doc-preserve"
RENAME_OLD = "wf-rename-old"
RENAME_NEW = "wf-rename-new"
PLANTED = [
    "wf-silent-both",
    "wf-silent-reason-hole",
    "wf-silent-evidence-hole",
]


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0075-probe2 {msg}")
    return 1


def by_id(doc: dict) -> dict:
    return {str(c["id"]): c for c in doc["candidates"]}


def independent_fields(a: dict, b: dict) -> list[str]:
    """Set algebra on evidence maps. Does not call monitor.compare()."""
    e1 = a.get("evidence") if isinstance(a.get("evidence"), dict) else {}
    e2 = b.get("evidence") if isinstance(b.get("evidence"), dict) else {}
    keys = sorted(set(e1) | set(e2))
    return [k for k in keys if str(e1.get(k, "")) != str(e2.get(k, ""))]


def reverse_aliases(migration: dict) -> dict[str, str]:
    rev: dict[str, str] = {}
    for row in migration.get("aliases") or []:
        src = str(row.get("from") or "")
        dst = str(row.get("to") or "")
        if src and dst:
            rev[dst] = src
    return rev


def alarm_any(v1: dict, v2: dict, migration: dict) -> dict:
    """Mutant: any classification change is a fail, evidence+reason ignored."""
    result = M.compare(v1, v2, migration)
    silent = []
    for row in result["findings"]:
        if (
            row.get("v1_classification")
            and row.get("v2_classification")
            and row["v1_classification"] != row["v2_classification"]
        ):
            row["fail"] = True
            row["kind"] = M.KIND_SILENT
            silent.append(row["canonical_id"])
    result["silent_drift_ids"] = silent
    result["fail"] = bool(silent)
    return result


def main() -> int:
    v1p, v2p, mp = (
        FIX / "v1_baseline.json",
        FIX / "v2_documented.json",
        FIX / "id_migration_map.json",
    )
    v1 = M.load_json(v1p)
    v2 = M.load_json(v2p)
    migration = M.load_json(mp)
    left, right = by_id(v1), by_id(v2)

    smoke_fields = independent_fields(left[DOC_SMOKE], right[DOC_SMOKE])
    preserve_fields = independent_fields(left[DOC_PRESERVE], right[DOC_PRESERVE])
    print(f"independent_fields {DOC_SMOKE}={smoke_fields}")
    print(f"independent_fields {DOC_PRESERVE}={preserve_fields}")
    if smoke_fields != ["smoke_run"]:
        return fail(f"doc-smoke independent fields={smoke_fields}")
    if preserve_fields != ["preservation_proof"]:
        return fail(f"doc-preserve independent fields={preserve_fields}")
    if smoke_fields == preserve_fields:
        return fail("both documented rows reported the same evidence field")

    rev = reverse_aliases(migration)
    walked = rev.get(RENAME_NEW)
    print(f"reverse_alias {RENAME_NEW} -> {walked}")
    if walked != RENAME_OLD:
        return fail(f"reverse alias did not recover {RENAME_OLD}")
    if left[RENAME_OLD]["classification"] != right[RENAME_NEW]["classification"]:
        return fail("rename pair classifications differ; this is not a pure rename")

    if M.resolve_id("wf-rename-legacy", migration) != RENAME_NEW:
        return fail("transitive alias wf-rename-legacy did not resolve to wf-rename-new")

    live = M.compare(v1, v2, migration)
    print(
        "verbatim_silent fixture=v2_documented "
        f"fail={live['fail']} silent_drift_ids={live['silent_drift_ids']} "
        f"documented_ids={live['documented_ids']} "
        f"rename_only_ids={live['rename_only_ids']}"
    )
    if live["fail"] or live["silent_drift_ids"]:
        return fail(f"documented pair was not silent: {live['silent_drift_ids']}")
    if sorted(live["documented_ids"]) != sorted([DOC_SMOKE, DOC_PRESERVE]):
        return fail(f"documented_ids={live['documented_ids']}")

    by_c = {f["canonical_id"]: f for f in live["findings"]}
    if by_c[DOC_SMOKE]["evidence_fields_changed"] != ["smoke_run"]:
        return fail("monitor did not name smoke_run")
    if by_c[DOC_PRESERVE]["evidence_fields_changed"] != ["preservation_proof"]:
        return fail("monitor did not name preservation_proof")
    rename = by_c.get(RENAME_NEW)
    if rename is None or rename["kind"] != M.KIND_RENAME_ONLY:
        return fail(f"rename finding missing or wrong: {rename}")
    if rename["v1_id"] != RENAME_OLD or rename["v2_id"] != RENAME_NEW:
        return fail(f"rename ids {rename['v1_id']} -> {rename['v2_id']}")
    if rename["fail"]:
        return fail("rename was marked fail")

    no_map = M.compare(v1, v2, None)
    kinds = {f["canonical_id"]: f["kind"] for f in no_map["findings"]}
    print(f"without_map kinds={kinds}")
    if RENAME_NEW in no_map["rename_only_ids"] or RENAME_OLD in no_map["rename_only_ids"]:
        return fail("without-map run still emitted RENAME_ONLY; map was not required")
    if kinds.get(RENAME_OLD) != M.KIND_REMOVED or kinds.get(RENAME_NEW) != M.KIND_ADDED:
        return fail("without-map rename must appear as REMOVED+ADDED")

    mutant = alarm_any(v1, v2, migration)
    print(f"mutant-alarm-any silent_drift_ids={mutant['silent_drift_ids']}")
    if DOC_SMOKE not in mutant["silent_drift_ids"] or DOC_PRESERVE not in mutant["silent_drift_ids"]:
        return fail("alarm-any mutant did not flag documented rows")
    if not mutant["fail"]:
        return fail("alarm-any mutant stayed silent")

    silent_pair = M.compare_paths(
        FIX / "v1_baseline.json", FIX / "v2_silent.json", mp
    )
    print(
        "reviewer_both_states silent_pair "
        f"fail={silent_pair['fail']} ids={silent_pair['silent_drift_ids']}"
    )
    if sorted(silent_pair["silent_drift_ids"]) != sorted(PLANTED):
        return fail("reviewer re-run of silent pair missed plants")

    if not ART.is_file():
        return fail(f"artifact missing {ART}")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {st}")
    if "SUCCESS:WFA-0075" not in text:
        return fail("sentinel absent")
    recorded = doc.get("documented_pair") or {}
    if recorded.get("fail") is not False:
        return fail("artifact documented_pair.fail is not false")
    rec_fields = {
        row["canonical_id"]: row.get("evidence_fields_changed")
        for row in (recorded.get("findings") or [])
        if row.get("kind") == M.KIND_DOCUMENTED
    }
    if rec_fields.get(DOC_SMOKE) != ["smoke_run"]:
        return fail(f"artifact smoke fields={rec_fields.get(DOC_SMOKE)}")
    if rec_fields.get(DOC_PRESERVE) != ["preservation_proof"]:
        return fail(f"artifact preserve fields={rec_fields.get(DOC_PRESERVE)}")
    rename_rows = [
        row
        for row in (recorded.get("findings") or [])
        if row.get("kind") == M.KIND_RENAME_ONLY
    ]
    if not rename_rows:
        return fail("artifact missing RENAME_ONLY finding")

    print(
        "NEGATIVE-CONTROL v2_documented: documented classification changes "
        "with named evidence-field deltas plus reasons stay silent; rename "
        f"joined via map kind=RENAME_ONLY; independent fields smoke={smoke_fields} "
        f"preserve={preserve_fields}"
    )
    print("SUCCESS:WFA-0075-probe2 documented silent, rename joined, fields named")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
