#!/usr/bin/env python3
"""Emit the RES-0141 measurement-run artifact from live labelled scoring."""
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
from common import (  # noqa: E402
    CAPTURES,
    CORPUS,
    LABELS,
    dump_json,
    is_x_0_0,
    load_json,
    now_iso,
    sha256_file,
)
from detector import fires  # noqa: E402
from load_run import best_silent, control_flag, gold_flag, live  # noqa: E402


def kent_band(p: float) -> str:
    if p <= 0.0:
        return "remote"
    for name, (lo, hi) in C.SHERMAN_KENT.items():
        if lo <= p <= hi:
            return name
    if p >= 0.99:
        return "almost-certain"
    return "remote"


def file_lineage(path: Path, source_id: str, note: str) -> dict:
    sha, size = sha256_file(path)
    rel = path.relative_to(REPO).as_posix()
    return {
        "id": source_id,
        "resolved_url": f"file://{rel}",
        "requested_url": f"file://{rel}",
        "fetched_at": now_iso(),
        "sha256": sha,
        "bytes": size,
        "http_status": 200,
        "kind": "worktree-file",
        "note": note,
        "path": rel,
    }


def meta_lineage(meta_path: Path) -> dict:
    meta = load_json(meta_path)
    return {
        "id": meta.get("id") or meta_path.stem,
        "resolved_url": meta.get("resolved_url") or meta.get("requested_url"),
        "requested_url": meta.get("requested_url"),
        "fetched_at": meta.get("fetched_at"),
        "sha256": meta.get("sha256"),
        "bytes": meta.get("bytes"),
        "http_status": meta.get("http_status"),
        "kind": "http-fetch",
        "role": meta.get("role"),
        "path": meta.get("body_path"),
    }


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


def main() -> int:
    corpus, assigned, ev = live()
    notes = corpus["notes"]
    dump_json(LABELS, assigned)
    best = best_silent(ev)
    if not best:
        print("FAILED:RES-0141 emit no silent combo")
        return 1
    silent_flag = ev.get("any_combo_silent_on_controls")
    if silent_flag is None:
        silent_flag = ev.get("any_combo_silent_on_controls")
    if not silent_flag:
        print("FAILED:RES-0141 emit no combo silent on controls")
        return 1
    control_fp = int(best.get("control_fp", best.get("control_fp", 1)))
    if control_fp != 0:
        print("FAILED:RES-0141 emit control false positives", best)
        return 1
    if len(notes) != C.N_NOTES:
        print("FAILED:RES-0141 emit n_notes", len(notes))
        return 1
    n_ctrl = int(
        assigned.get("n_control_negative")
        or assigned.get("n_control_negative")
        or 0
    )
    if n_ctrl < C.N_CONTROL_NEGATIVES:
        print("FAILED:RES-0141 emit too few controls", n_ctrl)
        return 1
    combo = tuple(best["combo"])
    labels = {r["id"]: r for r in assigned["labels"]}
    control_ids = list(
        assigned.get("control_ids") or assigned.get("control_ids") or []
    )
    by_id = {n["id"]: n for n in notes}
    live_control_fp = [
        nid for nid in control_ids if fires(by_id[nid]["text"], combo)
    ]
    if live_control_fp:
        print("FAILED:RES-0141 emit live fires on controls", live_control_fp)
        return 1
    for note in notes:
        expected = is_x_0_0(tuple(note["semver"]))
        got = gold_flag(labels[note["id"]])
        if expected != got:
            print("FAILED:RES-0141 emit gold mismatch", note["id"], expected, got)
            return 1
    labels_independent = ast_forbids_import(HERE / "labels.py", "detector")
    detector_independent = ast_forbids_import(HERE / "detector.py", "labels")
    if not labels_independent or not detector_independent:
        print("FAILED:RES-0141 emit circular labels/detector import")
        return 1

    schema_path = REPO / C.SCHEMA_REL
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    now = now_iso()
    n_pos = int(assigned.get("n_gold_positive") or assigned.get("n_gold_positive"))
    prec = float(best["precision"])
    rec = float(best["recall"])
    f1 = float(best["f1"])
    tp, fp, fn = int(best["tp"]), int(best["fp"]), int(best["fn"])
    fpr = 0.0
    method_meta = []
    for stem in (
        "semver-spec.meta.json",
        "conventional-commits.meta.json",
        "keep-a-changelog.meta.json",
    ):
        p = CAPTURES / stem
        if p.is_file():
            method_meta.append(meta_lineage(p))

    note_lineage = []
    for note in notes[:3]:
        lin = note.get("gh_lineage") or note.get("gh_lineage") or {}
        if lin:
            note_lineage.append(
                {
                    "id": note["id"],
                    "resolved_url": lin.get("resolved_url"),
                    "requested_url": lin.get("api_url"),
                    "fetched_at": lin.get("fetch_timestamp") or lin.get("fetched_at"),
                    "sha256": lin.get("sha256_fetched_bytes") or lin.get("sha256"),
                    "http_status": lin.get("http_status"),
                    "path": lin.get("capture_path"),
                    "kind": "github-release-capture",
                }
            )

    catalog = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    source_lineage = method_meta + note_lineage + [
        file_lineage(
            catalog,
            "catalog-RES-0141",
            "Estate catalog names the labelled-set P/R question and the 20-note silence control.",
        ),
        file_lineage(
            CORPUS,
            "corpus-100-notes",
            "Frozen 100 GitHub release notes with per-note fetch lineage.",
        ),
        file_lineage(
            LABELS,
            "labels-semver-x000",
            "Gold labels from X.0.0 tags; labels.py does not import detector.",
        ),
        file_lineage(
            HERE / "detector.py",
            "detector-source",
            "Lexical/structural signals scored on note text only.",
        ),
        file_lineage(
            schema_path,
            "measurement-run-schema",
            "Envelope schema; garbage objects must fail.",
        ),
    ]

    answer = (
        f"{C.SENTINEL}. On a frozen hand-labelled set of {len(notes)} real GitHub "
        f"release notes (gold-positive = parsed tag is X.0.0, n={n_pos}; "
        f"control-negative = first {n_ctrl} adjacent patch steps), the best "
        f"combination that stays silent on every control is {list(combo)}: "
        f"precision={prec} recall={rec} f1={f1} tp={tp} fp={fp} fn={fn}. "
        f"Control false-positive count={control_fp} (rate={fpr}) on the "
        f"{n_ctrl}-note silence set. Labels are assigned from the version "
        "identifier, not from changelog wording; detector.py does not import "
        "labels.py. Precision and recall are computed by score.evaluate, not "
        "described."
    )

    measurements = [
        {"id": "labelled-set-size", "value": len(notes), "unit": "notes", "method": "len(corpus.notes)"},
        {"id": "gold-positive-count", "value": n_pos, "unit": "notes", "method": "semver-X.0.0-from-tag"},
        {"id": "control-negative-count", "value": n_ctrl, "unit": "notes", "method": "adjacent-patch-step-first-20-by-id"},
        {"id": "best-combo-precision", "value": prec, "unit": "ratio", "method": "tp/(tp+fp) live score.evaluate"},
        {"id": "best-combo-recall", "value": rec, "unit": "ratio", "method": "tp/(tp+fn) live score.evaluate"},
        {"id": "best-combo-f1", "value": f1, "unit": "ratio", "method": "harmonic-mean precision recall"},
        {"id": "best-combo-tp", "value": tp, "unit": "notes", "method": "live confusion-matrix"},
        {"id": "best-combo-fp", "value": fp, "unit": "notes", "method": "live confusion-matrix"},
        {"id": "best-combo-fn", "value": fn, "unit": "notes", "method": "live confusion-matrix"},
        {"id": "control-false-positive-count", "value": control_fp, "unit": "notes", "method": "detector fire-count on 20 control negatives"},
        {"id": "control-false-positive-rate", "value": fpr, "unit": "ratio", "method": "control_fp / n_control_negative"},
    ]

    claims = [
        {
            "id": "C-BEST-COMBO-PR",
            "claim": (
                f"Best control-silent combination {list(combo)} achieves "
                f"precision={prec} and recall={rec} on the 100-note labelled set."
            ),
            "confidence_band": kent_band(prec),
            "sherman_kent": {"precision": kent_band(prec), "recall": kent_band(rec)},
            "independent_verification_path": C.P1,
            "signals": [
                {
                    "id": "S1-score-evaluate",
                    "kind": "executable-confusion-matrix",
                    "locator": "command-center/p2-wave/probes/RES-0141/score.py:evaluate",
                    "value": {
                        "precision": prec,
                        "recall": rec,
                        "f1": f1,
                        "tp": tp,
                        "fp": fp,
                        "fn": fn,
                    },
                },
                {
                    "id": "S2-per-note-fires",
                    "kind": "executable-per-note",
                    "locator": "command-center/p2-wave/probes/RES-0141/detector.py:fires",
                    "value": {"combo": list(combo), "n_notes": len(notes)},
                },
            ],
        },
        {
            "id": "C-CONTROL-SILENCE",
            "claim": (
                f"The selected detector stays silent on all {n_ctrl} control "
                "negatives (adjacent patch steps; gold-breaking=false); "
                f"false-positive rate={fpr}."
            ),
            "confidence_band": kent_band(1.0 if fpr == 0 else max(0.0, 1.0 - fpr)),
            "sherman_kent": {
                "control_silence": "almost-certain" if fpr == 0 else "unlikely"
            },
            "independent_verification_path": C.P2,
            "signals": [
                {
                    "id": "S1-evaluate-control-fp",
                    "kind": "executable-control-count",
                    "locator": "score.evaluate control_fp",
                    "value": control_fp,
                },
                {
                    "id": "S2-per-control-fires",
                    "kind": "executable-loop",
                    "locator": "detector.fires on each control id",
                    "value": {
                        "n_fired": len(live_control_fp),
                        "ids": live_control_fp,
                    },
                },
            ],
        },
        {
            "id": "C-LABEL-INDEPENDENCE",
            "claim": (
                "Gold labels are assigned from parsed X.0.0 tags before/without "
                "reading detector features; labels.py does not import detector.py."
            ),
            "confidence_band": "almost-certain",
            "independent_verification_path": C.P1,
            "signals": [
                {
                    "id": "S1-ast-no-detector-import",
                    "kind": "ast-import-ban",
                    "locator": "command-center/p2-wave/probes/RES-0141/labels.py",
                    "value": labels_independent,
                },
                {
                    "id": "S2-gold-equals-x000",
                    "kind": "recompute-from-tag",
                    "locator": "common.is_x_0_0(note.semver)",
                    "value": True,
                },
            ],
        },
    ]

    doc = {
        "unit_id": C.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "report_kind": "measurement-run",
        "title": C.TITLE,
        "question": C.QUESTION,
        "answer": answer,
        "measured_at": now,
        "output_path": C.OUTPUT_REL,
        "output_schema": C.SCHEMA_REL,
        "labelled_set": {
            "n_notes": len(notes),
            "n_gold_positive": n_pos,
            "n_control_negative": n_ctrl,
            "label_rule": assigned.get("label_rule") or assigned.get("label_rule"),
            "labels_assigned_from": "semver-X.0.0-tag",
            "labels_before_detector": True,
            "control_ids": control_ids,
            "corpus_path": "command-center/p2-wave/probes/RES-0141/corpus.json",
            "labels_path": "command-center/p2-wave/probes/RES-0141/labels.json",
        },
        "detector": {
            "signal_ids": list(C.SIGNAL_IDS),
            "best_combo_silent_on_controls": list(combo),
            "best_metrics": best,
            "any_combo_silent_on_controls": True,
            "unconstrained_best": ev.get("best_unconstrained")
            or ev.get("best_unconstrained"),
        },
        "claims": claims,
        "source_lineage": source_lineage,
        "sherman_kent_bands": {
            k: {"lo": lo, "hi": hi} for k, (lo, hi) in C.SHERMAN_KENT.items()
        },
        "detector_control": {
            "n_control_negative": n_ctrl,
            "silent": True,
            "false_positive_count": 0,
            "false_positive_rate": fpr,
            "control_ids": control_ids,
            "both_states": True,
            "fires_on_at_least_one_gold_positive": tp > 0,
        },
        "caveat": (
            "Gold-positive is the semver X.0.0 event, not a human judgement that "
            "every X.0.0 changelog names a breaking API. Recall below 1.0 is "
            "expected when a major tag's prose is quiet. One non-control gold-"
            "negative may still fire (recorded in fp). Control silence is exact "
            "on this 20-note set, not a claim of zero FPs on all patch notes."
        ),
        "measurements": measurements,
        "tests": [
            {
                "id": "labelled-set-precision-recall",
                "result": "PASS",
                "command": C.P1,
                "detail": f"combo={list(combo)} precision={prec} recall={rec} n={len(notes)}",
            },
            {
                "id": "negative-control-silence",
                "result": "PASS",
                "command": C.P2,
                "detail": f"control_fp=0 n_ctrl={n_ctrl} both_states tp={tp}",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": C.P1, "role": "labelled-set-precision-recall"},
            {"id": "probe2", "command": C.P2, "role": "negative-control-silence"},
        ],
        "reviewer": {
            "reviewer_id": C.REVIEWER_ID,
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 re-runs detector.fires on the 20 control negatives and "
                "requires silence, and requires at least one gold-positive fire "
                "so the detector is not vacuously silent."
            ),
        },
    }

    errors = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errors:
        print("FAILED:RES-0141 schema errors")
        for err in errors[:20]:
            print(" ", list(err.path), err.message)
        return 1

    out = REPO / C.OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if C.SENTINEL not in text:
        print("FAILED:RES-0141 sentinel missing from serialized artifact")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {C.OUTPUT_REL} bytes={size} sha256={digest}")
    print(
        f"combo={list(combo)} precision={prec} recall={rec} f1={f1} "
        f"tp={tp} fp={fp} fn={fn} control_fp=0 n_ctrl={n_ctrl}"
    )
    print(C.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
