"""Shared live measurements for IMP-0234 probes and receipt emit."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "blueprints" / "research"
sys.path.insert(0, str(LIB))

from contract import REQUIRED_ELEMENTS, register  # noqa: E402
from fingerprint import fingerprint, parameter_diff  # noqa: E402
from load import FLAGSHIP_IDS, load_corpus, load_library, register_library  # noqa: E402
from runtime import run_blueprint  # noqa: E402

ART_DIR = HERE / "artifacts"
RECEIPT_REL = "command-center/receipts/IMP-0234.json"
FLAGSHIP_MIN_BYTES = 256


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0234 {msg}")
    return 1


def with_renamed_ids(blueprint: dict, suffix: str = "_x") -> dict:
    bp = copy.deepcopy(blueprint)
    mapping = {s["id"]: s["id"] + suffix for s in bp["workflow"]["stages"]}
    for s in bp["workflow"]["stages"]:
        s["id"] = mapping[s["id"]]
    bp["workflow"]["edges"] = [[mapping[a], mapping[b]] for a, b in bp["workflow"]["edges"]]
    bp["id"] = bp["id"] + suffix
    wf_id = str(bp["workflow"].get("id") or "")
    if wf_id:
        bp["workflow"]["id"] = wf_id + suffix
    return bp


def prose_only_twin(blueprint: dict) -> dict:
    bp = copy.deepcopy(blueprint)
    bp["example"] = dict(bp["example"])
    bp["example"]["question"] = "REWORDED " + str(bp["example"].get("question"))
    bp["stopping_rules"] = dict(bp["stopping_rules"])
    bp["stopping_rules"]["documented"] = "REWORDED PROSE ONLY — same mechanism."
    return bp


def param_fork(blueprint: dict, source_quota: int) -> dict:
    bp = copy.deepcopy(blueprint)
    bp["declared_parameters"] = dict(bp["declared_parameters"])
    bp["declared_parameters"]["source_quota"] = source_quota
    return bp


def omission_matrix(blueprint: dict) -> list[dict[str, Any]]:
    rows = []
    for key, code in REQUIRED_ELEMENTS:
        mutant = copy.deepcopy(blueprint)
        mutant.pop(key, None)
        rec = register(mutant)
        rows.append(
            {
                "omitted": key,
                "expected_code": code,
                "got_code": rec["code"],
                "ok": rec["ok"],
                "distinct_hit": rec["code"] == code and rec["ok"] is False,
            }
        )
    return rows


def flagship_e2e(bp_id: str, lib: dict, corpus: list[dict]) -> dict[str, Any]:
    bp = lib[bp_id]
    out = ART_DIR / f"{bp_id}.e2e.json"
    run = run_blueprint(bp, corpus, out_path=out)
    path = ART_DIR / f"{bp_id}.e2e.json"
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    parsed = None
    parse_ok = False
    if exists and size > 0:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        parse_ok = isinstance(parsed, dict)
    neg_ok = bool(run["report"].get("negative_ids"))
    ledger_ok = bool(run["ledger"].get("empty_ledger_proven"))
    gate_ok = run["gate"]["fired"] is False
    post = (
        exists
        and size >= FLAGSHIP_MIN_BYTES
        and parse_ok
        and neg_ok
        and ledger_ok
        and gate_ok
        and bp.get("tier") == "flagship"
    )
    return {
        "blueprint_id": bp_id,
        "tier": bp.get("tier"),
        "path": f"command-center/p2-wave/probes/IMP-0234/artifacts/{bp_id}.e2e.json",
        "exists": exists,
        "bytes": size,
        "parse_ok": parse_ok,
        "negative_retained": neg_ok,
        "ledger_100": ledger_ok,
        "gate_silent": gate_ok,
        "gate": run["gate"],
        "counts": run["report"].get("counts"),
        "pass": post,
    }


def live_bundle() -> dict[str, Any]:
    lib = load_library()
    reg = register_library(lib)
    mixed = load_corpus("mixed")
    all_fav = load_corpus("all_favorable")
    sys_bp = lib["systematic-literature-review"]
    rap_bp = lib["rapid-literature-review"]
    diff = parameter_diff(sys_bp, rap_bp)
    fp_sys = fingerprint(sys_bp)
    fp_rap = fingerprint(rap_bp)
    fp_rename = fingerprint(with_renamed_ids(sys_bp))
    fp_prose = fingerprint(prose_only_twin(sys_bp))
    fp_param = fingerprint(param_fork(sys_bp, 7))
    omissions = omission_matrix(lib["deep-research"])
    run_bad = run_blueprint(lib["deep-research"], all_fav)
    run_good = run_blueprint(lib["deep-research"], mixed)
    run_skip = run_blueprint(lib["deep-research"], mixed, skip_contradiction_search=True)
    run_drop = run_blueprint(lib["deep-research"], mixed, drop_negative=True)
    e2e = {bp_id: flagship_e2e(bp_id, lib, mixed) for bp_id in FLAGSHIP_IDS}
    fps = {bp_id: fingerprint(lib[bp_id]) for bp_id in lib}
    return {
        "library_ids": list(lib),
        "registration": reg,
        "parameter_diff": diff,
        "fingerprints": fps,
        "systematic_fp": fp_sys,
        "rapid_fp": fp_rap,
        "rename_invariant": fp_rename == fp_sys,
        "prose_twin_same_fp": fp_prose == fp_sys,
        "param_fork_differs": fp_param != fp_sys,
        "fingerprints_differ": fp_sys != fp_rap,
        "parameter_diff_nonempty": bool(diff),
        "omissions": omissions,
        "omission_codes_distinct": len({r["expected_code"] for r in omissions}) == 6
        and all(r["distinct_hit"] for r in omissions),
        "gate_all_favorable": run_bad["gate"],
        "gate_mixed": run_good["gate"],
        "gate_skip_mixed": run_skip["gate"],
        "drop_negative": {
            "gate": run_drop["gate"],
            "ledger": run_drop["ledger"],
        },
        "flagship_e2e": e2e,
        "sys_params": dict(sys_bp["declared_parameters"]),
        "rap_params": dict(rap_bp["declared_parameters"]),
        "mixed_source_count": len(mixed),
        "all_favorable_source_count": len(all_fav),
    }
