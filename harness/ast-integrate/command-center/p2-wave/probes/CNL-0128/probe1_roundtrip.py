#!/usr/bin/env python3
"""Probe 1: all five catalog goals round-trip; CLI/SDK/builder parity.

A goal that cannot round-trip is a named gap. This probe fails if any
of the five is a gap, or if the three surfaces emit different specs.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import builder as B  # noqa: E402
import goals as GO  # noqa: E402
import spec as S  # noqa: E402
import surfaces as SUR  # noqa: E402

OUT = HERE / "probe1-roundtrip.raw.json"
ART = REPO / (
    "command-center/design/council/"
    "CNL-0128-cli-sdk-and-structured-builder-ergonomics-including-invali.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0128-probe1 {msg}")
    return 1


def main() -> int:
    GO.dump_fixture(REPO)
    quote = GO.catalog_quote(REPO)
    if quote["missing_on_catalog"]:
        return fail(f"catalog missing phrases {quote['missing_on_catalog']}")
    if quote["line"] < 1:
        return fail("catalog line missing")

    rows = []
    gaps = []
    for goal in GO.GOALS:
        rt = B.round_trip(goal["phrase"], surface="builder")
        sdk = SUR.sdk_build(goal["phrase"])
        cli = B.build_from_goal(goal["phrase"], surface="cli")
        typed = B.build_from_answers({"goal_id": goal["id"]}, surface="builder")
        if not (rt.get("ok") and sdk.get("ok") and cli.get("ok") and typed.get("ok")):
            gaps.append(goal["id"])
            rows.append({"id": goal["id"], "round_trip": False, "rt": rt})
            continue
        c_sdk = SUR.canonical(sdk["spec"])
        c_cli = SUR.canonical(cli["spec"])
        c_typed = SUR.canonical(typed["spec"])
        same = c_sdk == c_cli == c_typed
        token_ok = rt.get("round_trip") is True
        row = {
            "id": goal["id"],
            "phrase": goal["phrase"],
            "stopping_expr": sdk["spec"]["stopping_expr"],
            "restatement": rt["restatement"],
            "surface_parity": same,
            "round_trip": token_ok,
            "named_gap": not (same and token_ok),
            "errors": S.validate(sdk["spec"]),
        }
        if row["named_gap"] or row["errors"]:
            gaps.append(goal["id"])
        rows.append(row)
        print(
            f"roundtrip {goal['id']} expr={row['stopping_expr']!r} "
            f"parity={same} tokens={token_ok}"
        )
        print(f"  restatement: {row['restatement']}")

    # CLI subprocess: one live argv path (G1).
    cmd = [
        sys.executable,
        "-B",
        str(HERE / "surfaces.py"),
        "build",
        "--goal",
        GO.GOALS[0]["phrase"],
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if proc.returncode != 0:
        return fail(f"cli G1 exit {proc.returncode} stderr={proc.stderr[-400:]}")
    if "Traceback" in (proc.stdout + proc.stderr):
        return fail("cli G1 printed a traceback")
    if "unique_ideas >= 100" not in proc.stdout:
        return fail("cli G1 missing stopping_expr")

    if gaps:
        return fail(f"named gaps {gaps}")

    payload = {
        "probe": "probe1-roundtrip",
        "unit_id": "CNL-0128",
        "catalog_anchor": f"{quote['path']}:{quote['line']}",
        "spec_line": GO.SPEC_LINE,
        "n_goals": len(rows),
        "gaps": gaps,
        "rows": rows,
        "cli_g1_exit": proc.returncode,
        "pass": True,
    }
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:CNL-0128" not in ART.read_text(encoding="utf-8"):
            return fail("artifact sentinel absent")
        claimed = doc.get("round_trips") or []
        if len(claimed) != 5:
            return fail(f"artifact round_trips n={len(claimed)}")
        payload["artifact_ok"] = True

    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"catalog_anchor={quote['path']}:{quote['line']} n=5 gaps=0")
    print("SUCCESS:CNL-0128-probe1 five goals round-trip with surface parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
