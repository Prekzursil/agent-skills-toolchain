#!/usr/bin/env python3
"""Probe 1: reconstruct ranking and quality scores from `why` output alone.

Independent arithmetic: millipoint BM25 and quality weights are reimplemented
here and are not imported from the library. The live `why` command is invoked
as a subprocess so the printed JSON is the evidence, not an in-process handle.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WHY = REPO / "tools" / "marketplace" / "explain.py"
SCALE = 1000
K1 = 1200
B = 750


def independent_sat(tf: int, dl: int, avgdl: int) -> int:
    if tf <= 0:
        return 0
    avgdl = max(avgdl, 1)
    length = (SCALE - B) + (B * dl) // avgdl
    numerator = tf * (K1 + SCALE) * SCALE * SCALE
    denominator = tf * SCALE * SCALE + K1 * length
    return numerator // denominator


def independent_idf(n_docs: int, df: int) -> int:
    return ((n_docs - df + 1) * SCALE) // max(df, 1)


def run_why(subject: str, package: str, query: str | None = None) -> dict:
    cmd = [
        sys.executable,
        "-B",
        str(WHY),
        "why",
        subject,
        "--package",
        package,
    ]
    if query is not None:
        cmd.extend(["--query", query])
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"why exit {proc.returncode}: {(proc.stdout or '') + (proc.stderr or '')}"
        )
    first = (proc.stdout or "").splitlines()[0]
    return json.loads(first)


def main() -> int:
    report = run_why("search", "pkg.alpha", "json lint")
    ranking_rep = report.get("ranking") or {}
    mismatches = []
    reconstructed = 0
    for row in ranking_rep.get("components") or []:
        sat = independent_sat(int(row["tf_weighted"]), int(row["dl"]), int(row["avgdl"]))
        idf = independent_idf(int(row["N"]), int(row["df"]))
        value = (idf * sat) // SCALE
        reconstructed += value
        if value != int(row["value"]):
            mismatches.append(
                {
                    "id": row.get("id"),
                    "printed": row.get("value"),
                    "recomputed": value,
                    "idf": idf,
                    "sat": sat,
                }
            )
        if sat != int(row["sat_milli"]) or idf != int(row["idf_milli"]):
            mismatches.append(
                {
                    "id": row.get("id"),
                    "kind": "printed-intermediates",
                    "sat_printed": row.get("sat_milli"),
                    "sat_recomputed": sat,
                    "idf_printed": row.get("idf_milli"),
                    "idf_recomputed": idf,
                }
            )

    quality_rep = report.get("quality") or {}
    q_sum = 0
    for row in quality_rep.get("components") or []:
        value = (int(row["weight"]) * int(row["measurement"])) // SCALE
        q_sum += value
        if value != int(row["value"]):
            mismatches.append(
                {
                    "id": row.get("id"),
                    "kind": "quality",
                    "printed": row.get("value"),
                    "recomputed": value,
                }
            )

    payload = {
        "pass": (
            not mismatches
            and reconstructed == int(ranking_rep.get("score_milli") or -1)
            and reconstructed == int(ranking_rep.get("sum_components") or -1)
            and reconstructed > 0
            and q_sum == int(quality_rep.get("score_milli") or -1)
            and q_sum == int(quality_rep.get("sum_components") or -1)
            and len(ranking_rep.get("components") or []) >= 2
        ),
        "probe": "probe1-reconstruct-score",
        "quality_recomputed": q_sum,
        "quality_printed": quality_rep.get("score_milli"),
        "ranking_printed": ranking_rep.get("score_milli"),
        "ranking_recomputed": reconstructed,
        "ranking_terms": [
            {"id": row.get("id"), "value": row.get("value")}
            for row in ranking_rep.get("components") or []
        ],
        "mismatches": mismatches,
        "unit_id": "IMP-0105",
        "why_command": True,
    }
    print(json.dumps(payload, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0105-probe1 reconstruction mismatch")
        return 1
    print(
        "SUCCESS:IMP-0105-probe1 reconstructed ranking "
        f"{reconstructed} and quality {q_sum} from why output"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
