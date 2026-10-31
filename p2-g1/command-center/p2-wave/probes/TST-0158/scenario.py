#!/usr/bin/env python3
"""TST-0158 fixtures and live merge experiment.

Regression seed card sets match the measured 31-way M-NN collision:
option-universe family M = {1..33}, architecture-candidate mechanisms
(pre-reprefix) = {1..31} ∪ {34..40}. Intersection is exactly 31.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
MERGER = REPO / "tools" / "command-center" / "merge_catalog.py"
CC_DIR = REPO / "tools" / "command-center"

OPTION_NUMBERS = list(range(1, 34))
MECH_NUMBERS = list(range(1, 32)) + list(range(34, 41))
EXPECTED_COLLISION_NUMBERS = sorted(set(OPTION_NUMBERS) & set(MECH_NUMBERS))
EXPECTED_COLLISION_IDS = [f"M-{n}" for n in EXPECTED_COLLISION_NUMBERS]


def token(n: int) -> str:
    return f"M-{n}"


def sort_ids(ids: list[str] | set[str]) -> list[str]:
    def key(token_s: str) -> tuple[str, int, str]:
        head, sep, tail = str(token_s).rpartition("-")
        if sep and tail.isdigit():
            return (head, int(tail), str(token_s))
        return (str(token_s), 0, str(token_s))

    return sorted(ids, key=key)


def card(n: int, namespace: str, meaning: str, title: str) -> dict[str, Any]:
    return {
        "id": token(n),
        "meaning": meaning,
        "namespace": namespace,
        "number": n,
        "title": title,
    }


def option_slice() -> dict[str, Any]:
    return {
        "namespace": "option-universe",
        "slice": "option-universe-family-M",
        "items": [
            card(
                n,
                "option-universe",
                "option-card",
                f"Option universe family-M card {n}",
            )
            for n in OPTION_NUMBERS
        ],
    }


def mech_slice_pre_reprefix() -> dict[str, Any]:
    return {
        "namespace": "architecture-candidates-mechanism",
        "slice": "architecture-candidates-mechanisms-pre-reprefix",
        "items": [
            card(
                n,
                "architecture-candidates-mechanism",
                "mechanism-card",
                f"Architecture-candidate mechanism card {n} (pre-MECH reprefix)",
            )
            for n in MECH_NUMBERS
        ],
    }


def disjoint_alpha() -> dict[str, Any]:
    return {
        "slice": "disjoint-alpha",
        "items": [
            {"id": "TST-A-0001", "namespace": "alpha", "title": "alpha one"},
            {"id": "TST-A-0002", "namespace": "alpha", "title": "alpha two"},
        ],
    }


def disjoint_beta() -> dict[str, Any]:
    return {
        "slice": "disjoint-beta",
        "items": [
            {"id": "TST-B-0001", "namespace": "beta", "title": "beta one"},
            {"id": "TST-B-0002", "namespace": "beta", "title": "beta two"},
        ],
    }


def write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def ensure_fixtures() -> dict[str, str]:
    paths = {
        "option": "command-center/p2-wave/probes/TST-0158/fixtures/option-universe.json",
        "mech": (
            "command-center/p2-wave/probes/TST-0158/fixtures/"
            "architecture-mechs-pre-reprefix.json"
        ),
        "alpha": "command-center/p2-wave/probes/TST-0158/fixtures/disjoint-alpha.json",
        "beta": "command-center/p2-wave/probes/TST-0158/fixtures/disjoint-beta.json",
    }
    write_json(REPO / paths["option"], option_slice())
    write_json(REPO / paths["mech"], mech_slice_pre_reprefix())
    write_json(REPO / paths["alpha"], disjoint_alpha())
    write_json(REPO / paths["beta"], disjoint_beta())
    return paths


def ids_of(doc: dict[str, Any]) -> set[str]:
    return {
        str(row.get("id") or "")
        for row in (doc.get("items") or [])
        if isinstance(row, dict) and row.get("id")
    }


def independent_intersection(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Set-intersection over id fields. Does not import the merger."""
    return sort_ids(ids_of(a) & ids_of(b))


def run_merger(slice_paths: list[str], output: Path | None = None) -> dict[str, Any]:
    cmd = [sys.executable, "-B", str(MERGER), *slice_paths]
    if output is not None:
        cmd.extend(["--output", str(output)])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    payload: dict[str, Any] = {}
    stdout = (proc.stdout or "").strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"parse_error": True, "stdout_tail": stdout[-1500:]}
    wrote = bool(
        output is not None and output.is_file() and output.stat().st_size > 0
    )
    return {
        "exit_code": proc.returncode,
        "report": payload,
        "stderr_tail": (proc.stderr or "")[-1500:],
        "wrote_output": wrote,
    }


def last_wins_via_catalog(
    option_doc: dict[str, Any], mech_doc: dict[str, Any]
) -> dict[str, Any]:
    if str(CC_DIR) not in sys.path:
        sys.path.insert(0, str(CC_DIR))
    import catalog as cat  # noqa: E402
    import merge_catalog as merger  # noqa: E402

    combined = {"items": list(option_doc["items"]) + list(mech_doc["items"])}
    collapsed = cat.by_id(combined)
    lw = merger.last_wins_merge(
        [
            ("option-universe.json", option_doc),
            ("architecture-mechs-pre-reprefix.json", mech_doc),
        ]
    )
    opt_ids = ids_of(option_doc)
    mech_ids = ids_of(mech_doc)
    hidden = sort_ids(opt_ids & mech_ids)
    return {
        "strategy": "last-wins",
        "catalog_by_id_count": len(collapsed),
        "last_wins_count": lw["count"],
        "union_count": len(opt_ids | mech_ids),
        "option_count": len(opt_ids),
        "mech_count": len(mech_ids),
        "hidden_collision_ids": hidden,
        "hidden_collision_count": len(hidden),
        "refused": False,
        "silently_took_last_wins": lw["count"] == len(opt_ids | mech_ids)
        and len(hidden) == 31,
    }


def live_experiment() -> dict[str, Any]:
    paths = ensure_fixtures()
    option_doc = option_slice()
    mech_doc = mech_slice_pre_reprefix()
    alpha = disjoint_alpha()
    beta = disjoint_beta()

    expected = list(EXPECTED_COLLISION_IDS)
    if expected != sort_ids(expected) or len(expected) != 31:
        raise RuntimeError(f"seed list broken: {expected!r}")

    indep = independent_intersection(option_doc, mech_doc)
    if indep != expected:
        raise RuntimeError(f"independent intersection {indep} != seed {expected}")

    collision_out = FIX / "_must_not_write_collision.json"
    if collision_out.exists():
        collision_out.unlink()
    collision_run = run_merger(
        [str(REPO / paths["option"]), str(REPO / paths["mech"])],
        output=collision_out,
    )

    disjoint_out = FIX / "_disjoint_merged.json"
    if disjoint_out.exists():
        disjoint_out.unlink()
    disjoint_run = run_merger(
        [str(REPO / paths["alpha"]), str(REPO / paths["beta"])],
        output=disjoint_out,
    )
    swapped_disjoint = run_merger(
        [str(REPO / paths["beta"]), str(REPO / paths["alpha"])],
        output=None,
    )
    swapped_collision = run_merger(
        [str(REPO / paths["mech"]), str(REPO / paths["option"])],
        output=None,
    )

    last_wins = last_wins_via_catalog(option_doc, mech_doc)

    merger_ids = list((collision_run.get("report") or {}).get("collision_ids") or [])
    swapped_ids = list((swapped_collision.get("report") or {}).get("collision_ids") or [])

    disjoint_ids = sort_ids(ids_of(alpha) | ids_of(beta))
    merged_doc: dict[str, Any] = {}
    if disjoint_out.is_file():
        merged_doc = json.loads(disjoint_out.read_text(encoding="utf-8"))
    merged_ids = sort_ids(ids_of(merged_doc)) if merged_doc else []

    refuse_ok = (
        collision_run["exit_code"] == 2
        and collision_run["wrote_output"] is False
        and not collision_out.is_file()
        and merger_ids == expected
        and swapped_ids == expected
        and (collision_run.get("report") or {}).get("refused") is True
    )
    disjoint_ok = (
        disjoint_run["exit_code"] == 0
        and swapped_disjoint["exit_code"] == 0
        and disjoint_run["wrote_output"] is True
        and merged_ids == disjoint_ids
        and len(merged_ids) == 4
        and (disjoint_run.get("report") or {}).get("refused") is False
    )
    last_wins_is_fail = last_wins["silently_took_last_wins"] is True
    signals_agree = merger_ids == indep == expected

    passed = refuse_ok and disjoint_ok and last_wins_is_fail and signals_agree
    return {
        "pass": passed,
        "expected_collision_ids": expected,
        "expected_collision_count": 31,
        "independent_intersection": indep,
        "signals_agree": signals_agree,
        "refuse_ok": refuse_ok,
        "disjoint_ok": disjoint_ok,
        "last_wins_is_fail": last_wins_is_fail,
        "collision_run": {
            "exit_code": collision_run["exit_code"],
            "refused": (collision_run.get("report") or {}).get("refused"),
            "reason": (collision_run.get("report") or {}).get("reason"),
            "collision_ids": merger_ids,
            "collision_count": (collision_run.get("report") or {}).get(
                "collision_count"
            ),
            "wrote_merged_catalog": collision_run["wrote_output"],
            "order_independent": merger_ids == swapped_ids,
        },
        "disjoint_run": {
            "exit_code": disjoint_run["exit_code"],
            "swapped_exit_code": swapped_disjoint["exit_code"],
            "count": (disjoint_run.get("report") or {}).get("count"),
            "ids": merged_ids,
            "wrote_merged_catalog": disjoint_run["wrote_output"],
            "order_independent": (disjoint_run.get("report") or {}).get("ids")
            == (swapped_disjoint.get("report") or {}).get("ids"),
        },
        "last_wins_control": last_wins,
        "fixtures": paths,
        "merger": "tools/command-center/merge_catalog.py",
        "catalog_last_wins_api": "tools/command-center/catalog.py:by_id",
    }
