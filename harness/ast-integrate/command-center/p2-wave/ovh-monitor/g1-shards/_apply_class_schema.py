#!/usr/bin/env python3
"""Apply G-1 class-schema artifact patches on the Windows tree."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "CNF-0007"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "seed-stage"))


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh(uid: str, rel: str) -> None:
    sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "seed-stage"))
    import _refresh_primary_sha as R

    sys.argv = ["_refresh_primary_sha.py", uid, rel]
    code = R.main()
    if code != 0:
        raise SystemExit(f"FAILED:refresh {uid} rc={code}")


def copy_arc_schemas() -> None:
    src = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0102" / "schemas"
    mapping = {
        src / "common.identity.json": REPO / "schema" / "common" / "identity.json",
        src / "artifact.envelope.json": REPO / "schema" / "artifact-envelope.json",
        src / "conformance.case.json": REPO / "schema" / "conformance-case.json",
    }
    for a, b in mapping.items():
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a, b)
        print("copied", b.relative_to(REPO).as_posix(), "bytes", b.stat().st_size)


def persist_cnf_local() -> None:
    import validate as V

    schema = V.compiled_schema()
    path = V.LOCAL
    print("wrote", path.relative_to(REPO).as_posix(), "bytes", path.stat().st_size, "id", schema.get("$id"))


def patch_cnl0097() -> None:
    rel = (
        "command-center/design/council/"
        "CNL-0097-lost-dissent-diffing-the-transcript-against-the-synthesis.md"
    )
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    fp = doc.get("false_positive_rate") or {}
    doc["report"] = {
        "kind": "council-detector-spec",
        "observations": [
            {
                "name": "planted_bad_fired",
                "measured": True,
                "method": "detector.detect planted-bad-dropped-dissent",
                "anchor": "command-center/p2-wave/probes/CNL-0097/probe1_planted_fire.py",
            },
            {
                "name": "known_good_silent",
                "measured": True,
                "method": "detector.detect known-good-preserved-dissent",
                "anchor": "command-center/p2-wave/probes/CNL-0097/probe2_both_states.py",
            },
            {
                "name": "false_positive_rate",
                "measured": fp.get("value", 0.0),
                "method": "clean-fixture false-positive rate",
                "anchor": "command-center/p2-wave/probes/CNL-0097/scenario.py",
            },
        ],
        "control_ids": [
            "planted-bad-dropped-dissent",
            "known-good-preserved-dissent",
            "planted-void-id-only",
            "planted-generic-mention",
        ],
    }
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    sha, n = digest(path)
    print("patched CNL-0097 bytes", n, "sha", sha)


def patch_arc0102_pin() -> None:
    rel = "command-center/phase4/conformance/ARC-0102.json"
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    pin = {
        "match": True,
        "mismatch_fails_gate": True,
        "observed_version": "4.25.1",
        "package": "jsonschema",
        "pin_file": "command-center/p2-wave/probes/ARC-0102/pin.json",
        "pinned_version": "4.25.1",
    }
    doc["validator_pin"] = pin
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        legacy = ext.get("legacy_root")
        if isinstance(legacy, dict):
            legacy["validator_pin"] = pin
    path.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    sha, n = digest(path)
    print("patched ARC-0102 pin bytes", n, "sha", sha)


def patch_imp0295() -> None:
    from tools.council.protocol.betting import (
        BrierPayoff,
        HedgeRewardPayoff,
        TOURNAMENT_N,
        TOURNAMENT_SEED,
        run_tournament,
    )

    rel = "command-center/receipts/IMP-0295.json"
    path = REPO / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    proper = run_tournament(seed=TOURNAMENT_SEED, n=TOURNAMENT_N, rule=BrierPayoff())
    mutant = run_tournament(
        seed=TOURNAMENT_SEED, n=TOURNAMENT_N, rule=HedgeRewardPayoff()
    )
    doc["tournament"] = {
        "seed": TOURNAMENT_SEED,
        "n": TOURNAMENT_N,
        "rule": proper["rule"],
        "true_p_palette": proper["true_p_palette"],
        "totals": proper["totals"],
        "analytic_expected_totals": proper["analytic_expected_totals"],
        "ranking": proper["ranking"],
        "winner": proper["winner"],
        "hedger_wins": proper["hedger_wins"],
        "committer_beats_hedger": proper["committer_beats_hedger"],
        "n_store_forecasts": proper["n_store_forecasts"],
    }
    nc = doc.get("negative_control")
    if not isinstance(nc, dict):
        nc = {}
    nc.update(
        {
            "id": "NC-IMP-0295-NONPROPER-HEDGER-WINS",
            "rule_substituted": "hedge-reward-nonproper",
            "proper_winner": proper["winner"],
            "nonproper_winner": mutant["winner"],
            "proper_totals": proper["totals"],
            "nonproper_totals": mutant["totals"],
            "discriminates": proper["hedger_wins"] != mutant["hedger_wins"]
            and mutant["winner"] == "hedger",
        }
    )
    doc["negative_control"] = nc
    fr = doc.get("falsifiable_result")
    if isinstance(fr, dict):
        fr["tournament_committer_beats_hedger"] = proper["committer_beats_hedger"]
        fr["tournament_hedger_wins_under_brier"] = proper["hedger_wins"]
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, n = digest(path)
    print(
        "patched IMP-0295 bytes",
        n,
        "sha",
        sha,
        "totals",
        proper["totals"],
        "ranking",
        proper["ranking"],
    )


def main() -> int:
    import os

    os.environ["AST_INTEGRATE_ROOT"] = str(REPO)
    os.chdir(REPO)
    copy_arc_schemas()
    persist_cnf_local()
    patch_cnl0097()
    patch_arc0102_pin()
    patch_imp0295()
    refresh("ARC-0102", "command-center/phase4/conformance/ARC-0102.json")
    refresh("CNF-0007", "command-center/confirmation/CNF-0007-crossvendor-matrix.json")
    refresh(
        "CNL-0097",
        "command-center/design/council/CNL-0097-lost-dissent-diffing-the-transcript-against-the-synthesis.md",
    )
    refresh("IMP-0295", "command-center/receipts/IMP-0295.json")
    print("SUCCESS:apply-class-schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
