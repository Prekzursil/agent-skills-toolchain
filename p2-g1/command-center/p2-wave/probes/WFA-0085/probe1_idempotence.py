#!/usr/bin/env python3
"""Probe 1: full-sweep idempotence, content-hash UPDATE, adjudication preserve."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema

from corpus import EXPECTED_STABLE_IDS, N_UNIQUE  # noqa: E402
from scenarios import run_adjudication, run_content_update, run_idempotence  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0085-incremental-discovery-resume.json"
SCHEMA = HERE / "regression_fixture.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0085-probe1 {msg}")
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
    if doc.get("record_type") != "RegressionFixture":
        return fail("record_type")
    jsonschema.validate(doc, json.loads(SCHEMA.read_text(encoding="utf-8")))
    print("schema_valid=True")

    with tempfile.TemporaryDirectory(prefix="wfa0085-p1-") as tmp:
        root = Path(tmp)
        idem = run_idempotence(root / "idem")
        upd = run_content_update(root / "upd")
        adj = run_adjudication(root / "adj")

    print(
        f"idempotent byte_identical={idem['byte_identical']} "
        f"new_records={idem['new_records']} n={idem['n_records']} "
        f"sha={idem['sha256_first'][:12]}"
    )
    print(
        f"content_update duplicated={upd['duplicated']} "
        f"kind={upd['evidence_kind']} fields={upd['delta_fields']} "
        f"n={upd['n_records_after']}"
    )
    print(
        f"adjudication preserved={adj['preserved']} "
        f"content_updated={adj['content_updated']} n={adj['n_records']}"
    )

    if not idem["byte_identical"] or idem["new_records"] != 0:
        return fail("idempotence")
    if idem["n_records"] != N_UNIQUE or not idem["ids_match_expected"]:
        return fail(f"unique ids {idem['ids']} != {EXPECTED_STABLE_IDS}")
    if upd["duplicated"] or not upd["update_applied"] or upd["delta_fields"] != ["body"]:
        return fail("content-update")
    if upd["n_records_after"] != N_UNIQUE:
        return fail("content-update duplicated rows")
    if not adj["preserved"] or not adj["content_updated"] or adj["duplicated"]:
        return fail("adjudication")

    ea = doc.get("evidence_a") or {}
    if ea.get("byte_identical") is not True or ea.get("new_records") != 0:
        return fail("artifact evidence_a mismatch")
    if doc.get("content_update", {}).get("duplicated") is not False:
        return fail("artifact content_update.duplicated")
    if doc.get("adjudication", {}).get("preserved") is not True:
        return fail("artifact adjudication.preserved")
    if not all(c.get("pass") for c in doc.get("cases") or [] if c.get("id") in {"C1", "C2", "C3"}):
        return fail("artifact cases C1-C3")

    print("SUCCESS:WFA-0085-probe1 idempotence update adjudication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
