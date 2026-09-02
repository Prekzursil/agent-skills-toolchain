#!/usr/bin/env python3
"""Probe 1: labelled-set precision/recall is computed live and matches the artifact."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
from common import is_x_0_0  # noqa: E402
from load_run import best_silent, gold_flag, live  # noqa: E402

ART = REPO / C.OUTPUT_REL
SCHEMA = REPO / C.SCHEMA_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0141-probe1 {msg}")
    return 1


def ast_forbids_import(path: Path, banned: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == banned or alias.name.startswith(banned + "."):
                    return False
        if isinstance(node, ast.ImportFrom):
            if node.module == banned or (node.module or "").startswith(banned + "."):
                return False
    return True


def meas(doc: dict, mid: str):
    for row in doc.get("measurements") or []:
        if row.get("id") == mid:
            return row.get("value")
    return None


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != C.UNIT_ID:
        return fail(f"unit_id={doc.get('unit_id')}")
    if doc.get("report_kind") != "measurement-run":
        return fail(f"report_kind={doc.get('report_kind')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        return fail(f"schema {errors[0].message}")

    corpus, assigned, ev = live()
    notes = corpus["notes"]
    best = best_silent(ev)
    if len(notes) != C.N_NOTES:
        return fail(f"n_notes={len(notes)}")
    if meas(doc, "labelled-set-size") != len(notes):
        return fail("labelled-set-size mismatch")

    labels = {r["id"]: r for r in assigned["labels"]}
    for note in notes:
        if gold_flag(labels[note["id"]]) != is_x_0_0(tuple(note["semver"])):
            return fail(f"gold not from X.0.0 tag {note['id']}")
    if not ast_forbids_import(HERE / "labels.py", "detector"):
        return fail("labels.py imports detector")
    if not ast_forbids_import(HERE / "detector.py", "labels"):
        return fail("detector.py imports labels")

    n_pos = sum(1 for r in assigned["labels"] if gold_flag(r))
    if meas(doc, "gold-positive-count") != n_pos:
        return fail("gold-positive-count mismatch")
    if n_pos < 10:
        return fail("too few gold positives")

    if not best:
        return fail("no silent combo")
    live_prec = float(best["precision"])
    live_rec = float(best["recall"])
    live_f1 = float(best["f1"])
    if abs(float(meas(doc, "best-combo-precision")) - live_prec) > 1e-9:
        return fail(f"precision mismatch live={live_prec} art={meas(doc, 'best-combo-precision')}")
    if abs(float(meas(doc, "best-combo-recall")) - live_rec) > 1e-9:
        return fail(f"recall mismatch live={live_rec} art={meas(doc, 'best-combo-recall')}")
    if abs(float(meas(doc, "best-combo-f1")) - live_f1) > 1e-9:
        return fail("f1 mismatch")
    art_combo = (doc.get("detector") or {}).get("best_combo_silent_on_controls")
    if list(art_combo or []) != list(best.get("combo") or []):
        return fail(f"combo mismatch live={best.get('combo')} art={art_combo}")
    if meas(doc, "best-combo-tp") != int(best["tp"]):
        return fail("tp mismatch")
    if meas(doc, "best-combo-fp") != int(best["fp"]):
        return fail("fp mismatch")
    if meas(doc, "best-combo-fn") != int(best["fn"]):
        return fail("fn mismatch")

    print(
        f"n={len(notes)} gold_pos={n_pos} combo={best['combo']} "
        f"precision={live_prec} recall={live_rec} f1={live_f1} "
        f"tp={best['tp']} fp={best['fp']} fn={best['fn']}"
    )
    print("SUCCESS:RES-0141-probe1 labelled-set precision/recall computed live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
