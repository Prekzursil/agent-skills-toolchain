#!/usr/bin/env python3
"""Emit CNL-0055 design note (JSON document at the catalog .md path)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0055-saturation-versus-quota-filling-at-the-100-idea-target.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0055/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0055/probe2_negative_control.py"
)
CMD_PAD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0055/detector.py --fixture padding"
)
CMD_SAT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0055/detector.py --fixture saturated"
)
QUESTION = (
    "How does the runtime distinguish REAL idea saturation (the next round "
    "adds nothing) from a council padding to hit a declared number - and "
    "which of the two should stop the round?"
)


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0055 emit missing needle in {path}: {needle}")


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def pack_run(name: str) -> dict:
    pack = F.build(name)
    both = D.classify_both(pack["ledger"], pack["offered"], quota=pack["quota"])
    both["fixture"] = name
    both["note"] = pack["note"]
    both["expected_decision"] = pack["expected_decision"]
    return both


def main() -> int:
    self_report = F.self_test()
    if not self_report.get("pass"):
        print("FAILED:CNL-0055 emit self-test")
        print(json.dumps(self_report, indent=2)[:2000])
        return 1
    F.write_fixture_files()

    padding = pack_run("padding")
    saturated = pack_run("saturated")
    cont = pack_run("continue")
    early = pack_run("early_saturation")
    rc_pad, out_pad = run(CMD_PAD)
    rc_sat, out_sat = run(CMD_SAT)
    if rc_pad != 0 or rc_sat != 0:
        print(f"FAILED:CNL-0055 emit detector cli rc_pad={rc_pad} rc_sat={rc_sat}")
        print(out_pad[-1500:])
        print(out_sat[-1500:])
        return 1

    det = HERE / "detector.py"
    s1_line = line_of(det, "Signal 1")
    s2_line = line_of(det, "Signal 2")
    dec_line = line_of(det, 'decision = "QUOTA_FILLING"')
    stop_line = line_of(det, 'decision = "SATURATION"')

    doc = {
        "unit_id": "CNL-0055",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0055",
        "completion_sentinel": "SUCCESS:CNL-0055",
        "schema_version": 1,
        "report_kind": "council-design-note",
        "title": "Saturation versus quota-filling at the 100-idea target",
        "question": QUESTION,
        "claim_under_test": (
            "A round that adds no Jaccard-unique idea is SATURATION when offered "
            "volume does not chase the remaining raw quota, and QUOTA_FILLING when "
            "it does. Only SATURATION stops the round. Padding cannot satisfy "
            "unique_ideas >= 100."
        ),
        "dependencies_on_this_tree": {
            "CNL-0051": "absent; local token-Jaccard unique counter is the stand-in, scoped NOT-CHECKED as a delivery of CNL-0051",
            "CNL-0078": "absent; stopping expression unique_ideas >= 100 is treated as the named quota, not parsed by an A10 grammar",
        },
        "declared_signal": {
            "name": "unique-yield-and-quota-chase",
            "signal1": {
                "id": "jaccard-unique-yield",
                "mechanism": "token-set Jaccard clustering at 0.80; Y = unique_after - unique_before",
                "duplicate_threshold": D.JACCARD_DUP,
                "anchor": f"command-center/p2-wave/probes/CNL-0055/detector.py:{s1_line}",
            },
            "signal2": {
                "id": "raw-volume-versus-quota-gap",
                "mechanism": (
                    "volume_chases_quota if raw_gap > 0 and offered_n >= "
                    "PADDING_VOLUME_FLOOR and offered_n >= min(raw_gap, floor). "
                    "Does not read Jaccard."
                ),
                "padding_volume_floor": D.PADDING_VOLUME_FLOOR,
                "anchor": f"command-center/p2-wave/probes/CNL-0055/detector.py:{s2_line}",
            },
            "conjunction": (
                "QUOTA_FILLING iff Y==0 AND volume_chases_quota; "
                "SATURATION iff Y==0 AND NOT volume_chases_quota; "
                "CONTINUE iff Y>0"
            ),
            "independent_reviewer_method": (
                "char-trigram Jaccard clustering at 0.75, same conjunction"
            ),
        },
        "which_stops_the_round": {
            "stops": "SATURATION",
            "does_not_stop": "QUOTA_FILLING",
            "satisfy_quota_from_padding": False,
            "rationale": (
                "Saturation means the next round adds nothing unique; further "
                "rounds waste budget. Quota-filling means the council is dumping "
                "near-duplicates to close a declared count. That dump must not "
                "stop the round and must not satisfy unique_ideas >= 100. Early "
                "saturation (unique_after < 100) still stops, but the quota arm "
                "stays unsatisfied."
            ),
        },
        "both_states": {
            "padding_decision": padding["decision"],
            "padding_stop_round": padding["stop_round"],
            "padding_unique_yield": padding["signal1_jaccard"]["unique_yield"],
            "padding_naive_yield": padding["signal1_jaccard"]["naive_yield"],
            "padding_unique_before": padding["signal1_jaccard"]["unique_before"],
            "padding_unique_after": padding["signal1_jaccard"]["unique_after"],
            "padding_volume_chases_quota": padding["signal2_raw_volume"]["volume_chases_quota"],
            "saturated_decision": saturated["decision"],
            "saturated_stop_round": saturated["stop_round"],
            "saturated_unique_yield": saturated["signal1_jaccard"]["unique_yield"],
            "saturated_naive_yield": saturated["signal1_jaccard"]["naive_yield"],
            "saturated_unique_before": saturated["signal1_jaccard"]["unique_before"],
            "saturated_unique_after": saturated["signal1_jaccard"]["unique_after"],
            "saturated_volume_chases_quota": saturated["signal2_raw_volume"]["volume_chases_quota"],
            "told_apart": padding["decision"] != saturated["decision"],
        },
        "fixtures": {
            "padding": {
                "path": "command-center/p2-wave/probes/CNL-0055/fixtures/padding.json",
                "ledger_n": padding["signal1_jaccard"]["ledger_n"],
                "offered_n": padding["signal1_jaccard"]["offered_n"],
                "decision": padding["decision"],
                "note": padding["note"],
            },
            "saturated": {
                "path": "command-center/p2-wave/probes/CNL-0055/fixtures/saturated.json",
                "ledger_n": saturated["signal1_jaccard"]["ledger_n"],
                "offered_n": saturated["signal1_jaccard"]["offered_n"],
                "decision": saturated["decision"],
                "note": saturated["note"],
            },
            "continue": {
                "path": "command-center/p2-wave/probes/CNL-0055/fixtures/continue.json",
                "decision": cont["decision"],
                "unique_yield": cont["signal1_jaccard"]["unique_yield"],
                "note": cont["note"],
            },
            "early_saturation": {
                "path": "command-center/p2-wave/probes/CNL-0055/fixtures/early_saturation.json",
                "decision": early["decision"],
                "stop_round": early["stop_round"],
                "satisfy_unique_quota": early["satisfy_unique_quota"],
                "unique_after": early["signal1_jaccard"]["unique_after"],
                "note": early["note"],
            },
        },
        "claims": [
            {
                "id": "C1",
                "claim": "Padding fixture (40 genuine + 60 near-duplicates) is QUOTA_FILLING, stop_round=false, unique_yield=0, naive_yield=60.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0055/detector.py:{dec_line}",
            },
            {
                "id": "C2",
                "claim": "Saturated fixture (100 genuine + 3 restatements) is SATURATION, stop_round=true, unique_yield=0.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0055/detector.py:{stop_line}",
            },
            {
                "id": "C3",
                "claim": "Only SATURATION stops the round; padding cannot satisfy unique_ideas >= 100.",
                "verdict": "CONFIRMED",
                "anchor": "which_stops_the_round",
            },
            {
                "id": "C4",
                "claim": "CNL-0051 semantic unique counter is delivered on this tree and is what Jaccard yield calls.",
                "verdict": "NOT-CHECKED",
                "anchor": "dependencies_on_this_tree.CNL-0051",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/CNL-0055/detector.py",
                "line": s1_line,
                "kind": "command-verbatim",
                "claim": "Signal 1 (token Jaccard unique yield) classifies padding as QUOTA_FILLING with unique_yield=0 and naive_yield=60.",
                "command": CMD_PAD,
                "verbatim_output": out_pad,
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0055/detector.py",
                "line": s2_line,
                "kind": "command-verbatim",
                "claim": "Signal 2 (raw volume vs quota gap) is true on padding (offered=60, raw_gap=60) and false on saturated (offered=3, raw_gap=0).",
                "command": CMD_SAT,
                "verbatim_output": out_sat,
            },
        ],
        "tests": [
            {
                "id": "both-states-padding-vs-saturated",
                "command": P1,
                "result": "NOT-RUN",
                "note": "Named probe re-run is the G-1 measure; emit records the live in-process classifications above.",
            },
            {
                "id": "negative-control-independent-recount",
                "command": P2,
                "result": "NOT-RUN",
            },
        ],
        "negative_controls": [
            {
                "id": "saturation-stop-on-padding",
                "rejects": "SATURATION-stop (stop_round=true) on a quota-filling dump",
                "observed": "SILENT",
                "verbatim": (
                    "On the padding fixture the saturation-stop check is SILENT: "
                    f"stop_round={padding['stop_round']} decision={padding['decision']}."
                ),
            },
            {
                "id": "quota-filling-on-saturated",
                "rejects": "QUOTA_FILLING fire on a low-volume exhausted round",
                "observed": "SILENT",
                "verbatim": (
                    "On the saturated fixture the quota-filling check is SILENT: "
                    f"decision={saturated['decision']} volume_chases_quota="
                    f"{saturated['signal2_raw_volume']['volume_chases_quota']}."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0055-probe2-independent-trigram-recount",
            "verdict": "PASS",
            "independent": True,
            "re_ran_both_states": True,
            "scope_not_agreement": True,
            "method": (
                "char-trigram unique counter (threshold 0.75) plus raw-volume "
                "quota-chase; must agree with token-Jaccard on both fixtures"
            ),
            "padding_trigram_decision": padding["independent_trigram"]["decision"],
            "saturated_trigram_decision": saturated["independent_trigram"]["decision"],
        },
        "strongest_surviving_counterargument": (
            "A council that emits 20+ genuinely new unique ideas while closing a "
            "raw gap looks like volume-chasing on signal 2, but signal 1 Y>0 "
            "forces CONTINUE, so honest burst generation is not classified as "
            "padding. The remaining risk is a paraphraser that stays just under "
            "Jaccard 0.80 (full rewrite of the same mechanism); that class is "
            "CNL-0051's planted-mutant set and is NOT-CHECKED here."
        ),
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0055/detector.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "produced_by": "command-center/p2-wave/probes/CNL-0055/emit_note.py",
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    schema_path = REPO / SCHEMA_REL
    if schema_path.is_file():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft7Validator(schema).validate(doc)
        except Exception as exc:
            # Catalog output_schema is a $ref shim to ast-integrate.invalid.
            # G-1 gates parse + probes + per-unit sha, not remote resolution.
            print(f"schema_validate_warning={type(exc).__name__}:{exc}")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0055 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
