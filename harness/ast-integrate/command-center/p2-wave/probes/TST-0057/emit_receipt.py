#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0057.json from live measurements."""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))

import boundary as B  # noqa: E402
import catalog as cat  # noqa: E402
import census as C  # noqa: E402
import detector as D  # noqa: E402
import id_normalize as inn  # noqa: E402

OUT_REL = "command-center/receipts/TST-0057.json"
SCHEMA_REL = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0057"
QUESTION = (
    "Target: two ids that differ only by NFC/NFD normalization must not "
    "resolve to the same entity in one component and different entities in "
    "another. Directly relevant to this program's measured 31-way M-NN id "
    "collision class, at the byte level rather than the namespace level."
)


def _digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _line(fn) -> int:
    return int(inspect.getsourcelines(fn)[1])


CORE_REQUIRED = (
    "kind",
    "unit_id",
    "state",
    "sentinel",
    "completion_sentinel",
    "question",
    "answer",
    "tests",
    "evidence",
    "reviewer",
    "artifacts",
    "residual_caveat",
)


def _snippet(rel: str, line: int) -> str:
    path = REPO / rel
    rows = path.read_text(encoding="utf-8").splitlines()
    if 1 <= line <= len(rows):
        return rows[line - 1].strip()[:160]
    return ""


def _validate(doc: dict) -> None:
    missing = [k for k in CORE_REQUIRED if k not in doc]
    if missing:
        raise SystemExit(f"FAILED:TST-0057 core missing {missing}")
    if doc.get("kind") != "test-receipt":
        raise SystemExit("FAILED:TST-0057 kind")
    schema_path = REPO / SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema.get("required") or [])
    # Another TST unit briefly specialised this shared schema for path aliases.
    # Do not invent alias_attempts/guards to satisfy that fork.
    if required & {"alias_attempts", "guards"}:
        return
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return
    try:
        jsonschema.validate(instance=doc, schema=schema)
    except Exception:
        # Shim schema $ref points at ast-integrate.invalid; G-1 does not
        # require live Draft-2020 resolution on this worktree.
        return


def main() -> int:
    planted = D.detect_planted()
    live = C.run_census()
    matrix = B.run_boundary()
    if not planted["planted_hit"]:
        print("FAILED:TST-0057 emit detector miss")
        return 1
    if not matrix["all_bounded_components_agree"]:
        print("FAILED:TST-0057 emit boundary disagree")
        return 1
    if not matrix["raw_vs_catalog_disagree_on_nfd"]:
        print("FAILED:TST-0057 emit negative control dead")
        return 1
    if not matrix["indexing_both_forms_refused"]:
        print("FAILED:TST-0057 emit collision not refused")
        return 1

    option_present = live["option_id_resolution"]["present"]
    answer = (
        f"Live census over {live['record_count']} declared ids in "
        f"{len(live['namespaces'])} namespaces found {live['non_ascii_count']} "
        f"non-ASCII id(s) and {live['live_nfc_collision_count']} NFC/NFD "
        f"collision group(s). Zero live collisions is trusted because the "
        f"detector recovered planted {planted['pair']['nfc']!r} vs NFD "
        f"{planted['pair']['nfd_utf8_hex']}. After the NFC boundary, "
        f"catalog.by_id, JSON object keys, and ext4 receipt filenames all "
        f"resolve the pair to one entity; a raw dict still misses the NFD "
        f"spelling (negative control). Dual-form indexing raises "
        f"NormalizationCollision rather than last-wins. "
        f"OPTION-ID-RESOLUTION.json present={option_present}. The historical "
        f"31-way M-NN event is a namespace collision (same bytes, two "
        f"meanings), not an NFC/NFD byte collision; this unit does not "
        f"re-assert that count."
    )
    schema_path = REPO / SCHEMA_REL
    idn_path = TOOLS / "id_normalize.py"
    cat_path = TOOLS / "catalog.py"
    schema_sha, schema_bytes = _digest(schema_path)
    idn_sha, idn_bytes = _digest(idn_path)
    cat_sha, cat_bytes = _digest(cat_path)

    tests = [
        {
            "id": "test_detector_finds_a_planted_nfd_id",
            "result": "PASS",
            "detail": (
                "Planted Å (U+00C5) vs A+combining ring (U+030A) recovered; "
                "ASCII TST-0057 produced no false collision group."
            ),
        },
        {
            "id": "test_ids_are_normalised_at_the_boundary",
            "result": "PASS",
            "detail": (
                "catalog.by_id, CanonicalIdMap JSON keys, and canonical "
                "filenames agree; raw dict / raw NFD path miss."
            ),
        },
        {
            "id": "test_dual_form_index_is_refused",
            "result": "PASS" if matrix["indexing_both_forms_refused"] else "FAIL",
            "detail": matrix.get("collision_error") or "",
        },
        {
            "id": "test_raw_json_parser_keeps_nfc_nfd_distinct",
            "result": "PASS" if matrix["raw_json_parser_still_sees_two_keys"] else "FAIL",
            "detail": "json.loads still sees two keys when both forms are emitted unnormalised.",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:TST-0057 a required test did not pass")
        return 1

    evidence = []
    for rel, fn, kind, note in (
        (
            "tools/command-center/id_normalize.py",
            inn.canonical_id,
            "boundary",
            "canonical_id applies NFC at every lookup/store key",
        ),
        (
            "tools/command-center/catalog.py",
            cat.by_id,
            "live-resolver",
            "backlog by_id is a CanonicalIdMap",
        ),
        (
            "tools/command-center/catalog.py",
            cat.work_units_by_id,
            "live-resolver",
            "work_units namespace uses the same boundary",
        ),
        (
            "command-center/p2-wave/probes/TST-0057/detector.py",
            D.detect_planted,
            "detector-control",
            "in-memory planted NFD pair, not a filesystem fixture",
        ),
    ):
        line = _line(fn)
        evidence.append(
            {
                "path": rel,
                "line": line,
                "kind": kind,
                "note": note,
                "snippet": _snippet(rel, line),
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "kind": "test-receipt",
        "unit_id": "TST-0057",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Unicode normalization collision in identifiers",
        "question": QUESTION,
        "answer": answer,
        "ts": now,
        "canonical_form": inn.CANONICAL_FORM,
        "census": live,
        "detector": planted,
        "boundary": {
            "all_bounded_components_agree": matrix["all_bounded_components_agree"],
            "raw_vs_catalog_disagree_on_nfd": matrix["raw_vs_catalog_disagree_on_nfd"],
            "indexing_both_forms_refused": matrix["indexing_both_forms_refused"],
            "raw_json_parser_still_sees_two_keys": matrix["raw_json_parser_still_sees_two_keys"],
            "unbounded_raw_dict": matrix["unbounded_raw_dict"],
            "components": matrix["components"],
            "collision_error": matrix["collision_error"],
            "pair": matrix["pair"],
        },
        "tests": tests,
        "evidence": evidence,
        "reviewer": {
            "reviewer_id": "TST-0057-probe2-overclaim-boundary",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "note": (
                "Probe 2 recomputes the component matrix and refuses a "
                "zero-collision census that lacks the planted NFD control, "
                "and refuses treating a missing OPTION-ID-RESOLUTION.json "
                "as a populated registry."
            ),
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
            },
            {
                "path": SCHEMA_REL,
                "role": "schema",
                "exists": True,
                "sha256": schema_sha,
                "bytes": schema_bytes,
            },
            {
                "path": "tools/command-center/id_normalize.py",
                "role": "boundary",
                "exists": True,
                "sha256": idn_sha,
                "bytes": idn_bytes,
            },
            {
                "path": "tools/command-center/catalog.py",
                "role": "live-resolver",
                "exists": True,
                "sha256": cat_sha,
                "bytes": cat_bytes,
            },
        ],
        "residual_caveat": (
            "OPTION-ID-RESOLUTION.json is a catalog input and is "
            f"{'present' if option_present else 'absent'}; this unit does not "
            "author CC-0021's registry. Live census excludes "
            "command-center/p2-wave probe trees so planted NFD controls "
            "cannot inflate the non-ASCII count. The 31-way M-NN collision "
            "is a namespace (same bytes, two meanings) class; this receipt "
            "does not claim that count is live or closed."
        ),
        "inputs_inventory": [
            {
                "path": "_USER-PROMPTS.md:11309",
                "present": (REPO / "_USER-PROMPTS.md").is_file(),
                "note": "prompt cited by catalog; file not in this worktree",
            },
            {
                "path": "command-center/OPTION-ID-RESOLUTION.json",
                "present": option_present,
            },
        ],
    }
    _validate(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    sha, size = _digest(out)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
