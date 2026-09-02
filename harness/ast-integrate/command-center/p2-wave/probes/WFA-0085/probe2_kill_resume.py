#!/usr/bin/env python3
"""Probe 2: SIGKILL mid-sweep, resume, compare to uninterrupted; append control."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema

from corpus import N_UNIQUE  # noqa: E402
from scenarios import run_kill_resume, run_naive  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0085-incremental-discovery-resume.json"
SCHEMA = HERE / "regression_fixture.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0085-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0085" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    print("schema_valid=True")

    garbage = {"totally": "unrelated", "passing_tests": 999999}
    rejected = False
    try:
        jsonschema.validate(garbage, json.loads(SCHEMA.read_text(encoding="utf-8")))
    except jsonschema.ValidationError:
        rejected = True
    if not rejected:
        return fail("schema accepts garbage")
    print("schema_rejects_garbage=True")

    with tempfile.TemporaryDirectory(prefix="wfa0085-p2-") as tmp:
        root = Path(tmp)
        kr = run_kill_resume(root / "kr")
        naive = run_naive(root / "naive")

    print(
        f"kill_executed={kr['kill_executed']} signal={kr['kill_signal']} "
        f"rc={kr['child_returncode']} at_kill={kr['records_at_kill']} "
        f"resume={kr['n_records_resume']} clean={kr['n_records_uninterrupted']} "
        f"equal={kr['record_set_equal']}"
    )
    print(
        f"naive n={naive['n_records']} unique={naive['n_unique_ids']} "
        f"duplicates={naive['duplicates']} ids={naive['duplicate_ids']}"
    )

    if not kr["kill_executed"] or kr["kill_signal"] != "SIGKILL":
        return fail("kill not executed")
    if kr["child_returncode"] not in (-9,):
        return fail(f"returncode {kr['child_returncode']}")
    if kr["sources_at_kill"] != 4 or kr["records_at_kill"] != 4:
        return fail("checkpoint at kill")
    if not kr["record_set_equal"] or not kr["per_cell_equal"] or not kr["ids_equal"]:
        return fail("resume != uninterrupted")
    if not kr["no_lost_record"] or not kr["no_duplicate"]:
        return fail("lost or duplicate after resume")
    if kr["n_records_resume"] != N_UNIQUE:
        return fail("resume unique count")
    if not naive["duplicates"] or naive["n_records"] <= N_UNIQUE:
        return fail("naive append did not duplicate (control inverted)")
    if naive["n_unique_ids"] != N_UNIQUE:
        return fail("naive unique mismatch")

    eb = doc.get("evidence_b") or {}
    if eb.get("kill_executed") is not True or eb.get("record_set_equal") is not True:
        return fail("artifact evidence_b mismatch")
    bs = doc.get("both_states") or {}
    if bs.get("append_duplicates") is not True or bs.get("merge_silent_on_collision") is not True:
        return fail("artifact both_states")
    if bs.get("merge_unique") != N_UNIQUE or bs.get("append_rows") != naive["n_records"]:
        return fail("artifact both_states counts")

    print("SUCCESS:WFA-0085-probe2 kill-and-resume naive-append-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
