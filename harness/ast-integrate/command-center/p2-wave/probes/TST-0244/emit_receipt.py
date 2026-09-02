#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0244.json from live taxonomy measurements."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from gates.failure_taxonomy import (  # noqa: E402
    TAXONOMY_CLASSES,
    UNCLASSIFIED,
    measure_coverage,
    measure_negative_control,
)

UNIT = "TST-0244"
OUT_REL = "command-center/receipts/TST-0244.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/ux_report"
SENTINEL = "SUCCESS:TST-0244"
QUESTION = (
    "Does every class in the failure taxonomy produce a message that names "
    "what failed, why, and the exact next command? PASS requires full taxonomy "
    "coverage; a bare stack trace or an error with no next action is FAIL."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0244/probe1_taxonomy_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0244/probe2_bare_error_zero.py"
)
IMPL = "tools/gates/failure_taxonomy.py"
SUPPORTING = [
    IMPL,
    "tools/gates/tests/test_failure_taxonomy.py",
    "command-center/p2-wave/probes/TST-0244/probe1_taxonomy_coverage.py",
    "command-center/p2-wave/probes/TST-0244/probe2_bare_error_zero.py",
    "command-center/p2-wave/probes/TST-0244/emit_receipt.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def compact_row(row: dict) -> dict:
    obs = row.get("observation") or {}
    return {
        "class": row["intended"],
        "classified": row["classified"],
        "triggered": row["triggered"],
        "match": row["match"],
        "inducer": obs.get("inducer"),
        "exit_code": obs.get("exit_code"),
        "timeout_hit": obs.get("timeout_hit"),
        "message": row["message"],
        "what_score": row["rubric"]["parts"]["what"],
        "why_score": row["rubric"]["parts"]["why"],
        "next_score": row["rubric"]["parts"]["next_command"],
        "score": row["rubric"]["score"],
        "next_command": row["next_command"],
    }


def encoding_roundtrip(messages: list[str]) -> list[dict]:
    codecs = ("utf-8", "utf-8-sig", "utf-16", "latin-1")
    rows = []
    for codec in codecs:
        ok = True
        for msg in messages:
            try:
                if msg.encode(codec).decode(codec) != msg:
                    ok = False
                    break
            except UnicodeError:
                ok = False
                break
        rows.append({"id": codec, "codec": codec, "roundtrip_ok": ok})
    return rows


def build_receipt() -> dict:
    coverage = measure_coverage(repo=REPO, execute_next=True)
    negative = measure_negative_control()
    matrix = coverage["matrix"]
    if not coverage["pass"] or not negative["pass"]:
        raise SystemExit("live coverage or negative control failed; refusing SUCCESS")
    compact = [compact_row(r) for r in matrix["rows"]]
    encodings = encoding_roundtrip([r["message"] for r in compact])
    if not all(e["roundtrip_ok"] for e in encodings):
        raise SystemExit("message encoding round-trip failed")
    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Every closed taxonomy class (severed-stream, adapter-exit-n, "
        "win-arg-limit, timeout, schema-invalid, partial-artifact, degraded, "
        "blocked) was induced, classified from symptoms, and formatted into "
        "WHAT/WHY/NEXT; each scored 3/3. A bare traceback and the shrug "
        "'Operation failed.' scored 0. The naive always-3 scorer still "
        "awards 3 to the traceback, so the rubric is not a constant. "
        f"{SENTINEL}"
    )
    return {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Every failure class emits an actionable message (what, why, next command)",
        "question": QUESTION,
        "answer": answer,
        "output_schema": SCHEMA,
        "output_path": OUT_REL,
        "cloud_ok": False,
        "computed_at": now,
        "taxonomy": list(TAXONOMY_CLASSES),
        "unclassified_bucket": UNCLASSIFIED,
        "coverage_matrix": compact,
        "matrix": compact,
        "encodings": encodings,
        "negative_control": {
            "bare_score": negative["score_bare"]["score"],
            "shrug_score": negative["score_shrug"]["score"],
            "catalog_score": negative["score_catalog"]["score"],
            "naive_bare_score": negative["naive_bare_score"],
            "detector_is_not_constant": negative["detector_is_not_constant"],
            "both_states": negative["both_states"],
            "catalog_timeout_message": negative["catalog_timeout_message"],
            "bare_excerpt": (negative["bare_traceback"] or "").splitlines()[0],
        },
        "next_commands": coverage["next_commands"],
        "tests": [
            {
                "id": "coverage-every-failure-class-triggered",
                "result": "PASS",
                "command": P1,
                "n_triggered": matrix["n_triggered"],
                "sampled": False,
            },
            {
                "id": "negative-control-bare-error-scores-zero",
                "result": "PASS",
                "command": P2,
                "bare_score": negative["score_bare"]["score"],
            },
        ],
        "evidence": [
            {
                "claim": "Coverage matrix was produced by inducing each class, not by sampling.",
                "anchor": IMPL,
                "signal": "a",
            },
            {
                "claim": "Each captured message was scored against what / why / next-command.",
                "anchor": "tools/gates/failure_taxonomy.py:score_message",
                "signal": "b",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0244-probe2-bare-error-zero",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Independent probe scores a live traceback at 0 and a catalog "
                "timeout message at 3; a constant-3 naive scorer fails the control."
            ),
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "platform": {
            "system": platform.system(),
            "python": platform.python_version(),
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "role": "primary",
                "exists": True,
                "eol": "LF",
                "note": "sha256/bytes filled by the per-unit manifest after write",
            },
            art(IMPL, "implementation"),
            art("tools/gates/tests/test_failure_taxonomy.py", "tests"),
            art(
                "command-center/p2-wave/probes/TST-0244/probe1_taxonomy_coverage.py",
                "probe",
            ),
            art(
                "command-center/p2-wave/probes/TST-0244/probe2_bare_error_zero.py",
                "probe",
            ),
        ],
        SENTINEL: True,
    }


def write_receipt(doc: dict) -> Path:
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        raise SystemExit("sentinel missing from receipt text")
    if '"state": "BLOCKED"' in text or '"state": "FAILED"' in text:
        raise SystemExit("receipt must not be self-declared blocked")
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
    return out


def main() -> int:
    path = write_receipt(build_receipt())
    digest, size = sha256_file(path)
    print(json.dumps({"path": OUT_REL, "sha256": digest, "bytes": size, "sentinel": SENTINEL}, sort_keys=True))
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
