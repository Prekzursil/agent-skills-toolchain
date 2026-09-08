#!/usr/bin/env python3
"""Probe 1: planted-mutant control — per-class detection rates."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
GATE = REPO / "tools/command-center/mechanism_dedup_gate.py"
FIXTURES = PROBE / "fixtures/planted-mutants.json"
OUT_JSON = PROBE / "probe1-mutants.json"
OUT_RAW = PROBE / "probe1-mutants.raw.txt"


def main() -> int:
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(GATE),
            "--fixtures",
            str(FIXTURES),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = (proc.stdout or "") + (proc.stderr or "")
    OUT_RAW.write_text(raw, encoding="utf-8")
    if proc.returncode != 0:
        OUT_JSON.write_text(
            json.dumps({"ok": False, "rc": proc.returncode, "raw_tail": raw[-2000:]}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(raw)
        return proc.returncode

    report = json.loads(proc.stdout)
    per = report["per_class_detection"]
    summary = {
        "ok": bool(report.get("ok")) and all(v["detection_rate"] == 1.0 for v in per.values()),
        "per_class_detection_rate": {
            k: v["detection_rate"] for k, v in sorted(per.items())
        },
        "per_class_verdict": {k: v["verdict"] for k, v in sorted(per.items())},
        "per_class_scores": {
            k: {
                "lexical_jaccard": v["lexical_jaccard"],
                "embedding_cosine": v["embedding_cosine"],
                "lexical_fire": v["lexical_fire"],
                "embedding_fire": v["embedding_fire"],
                "error_direction": v["error_direction"],
            }
            for k, v in sorted(per.items())
        },
        "full_rewrite_lexical_band": per["full_rewrite"]["lexical_jaccard"],
        "full_rewrite_defeats_lexical": (
            per["full_rewrite"]["lexical_jaccard"] <= 0.24
            and not per["full_rewrite"]["lexical_fire"]
            and per["full_rewrite"]["embedding_fire"]
        ),
        "gate": report.get("gate"),
        "embedding_method": report.get("embedding_method"),
        "thresholds": {
            "lexical": report["lexical_threshold"],
            "embedding": report["embedding_threshold"],
        },
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
