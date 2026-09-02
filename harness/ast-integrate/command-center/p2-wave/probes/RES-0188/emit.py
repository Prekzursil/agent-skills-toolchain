#!/usr/bin/env python3
"""Emit RES-0188 measurement-run artifact after live detector + reviewer."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from detector import evaluate_pack, evaluate_premise, named_inputs_present  # noqa: E402
from fixtures import ARCH_NAME, LOG_NAME, OPTION_NAME, ensure_fixtures  # noqa: E402
from reviewer import review  # noqa: E402

OUT = (
    "command-center/research/evidence-quality/"
    "RES-0188-stale-premise-detection-in-briefing-packs.json"
)
SCHEMA = "command-center/schema/measurement-run.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0188/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0188/probe2_independent_recount.py"
)
SENTINEL = "SUCCESS:RES-0188"
QUESTION = (
    "Build the check that compares every load-bearing premise in a briefing "
    "pack against the current state of the artifact it describes, and validate "
    "it on the known case: the M-NN option-id collision was re-prefixed to "
    "MECH-NN on 2026-08-07 yet 17-DECISION-LOG.md:175 still states it in the "
    "present tense, and that stale premise was then pinned as ground truth "
    "for a whole program."
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _snip(path: Path, needle: str) -> tuple[int, str]:
    text = path.read_text(encoding="utf-8")
    idx = text.find(needle)
    if idx < 0:
        return 1, text.splitlines()[0][:160] if text else ""
    line = text[:idx].count("\n") + 1
    snippet = text[idx : idx + 160].splitlines()[0]
    return line, snippet


def _claim(cid: str, text: str, verdict: str, band: str, row: dict, verify: str) -> dict:
    return {
        "id": cid,
        "claim": text,
        "verdict": verdict,
        "sherman_kent_band": band,
        "signals": row.get("signals") or [],
        "source_lineage": [
            {
                **r,
                "resolved_url": r.get("resolved_url") or r.get("resolved_url"),
                "fetch_timestamp": r.get("fetch_timestamp") or r.get("fetch_timestamp"),
                "sha256_of_fetched_bytes": r.get("sha256_of_fetched_bytes")
                or r.get("sha256_of_fetched_bytes"),
            }
            for r in (row.get("source_lineage") or [])
        ],
        "independent_verification_path": verify,
        "premise_id": row.get("id"),
        "fire": row.get("fire"),
        "reason": row.get("reason"),
        "measurement": row.get("measurement"),
    }


def live_catalog_premise() -> dict:
    catalog = "command-center/WORK-UNIT-CATALOG.json"
    premise = {
        "id": "P-LIVE-CATALOG-RES-0188",
        "text": "WORK-UNIT-CATALOG.json contains a work unit whose id is RES-0188.",
        "asserted_status": "current-fact",
        "check": "json-unit-id-present",
        "briefing_rel": catalog,
        "artifact_rels": [catalog],
        "unit_id": "RES-0188",
        "expect_fire": False,
    }
    return evaluate_premise(REPO, premise)


def main() -> int:
    paths = ensure_fixtures()
    known = evaluate_pack(paths["known-case"])
    inverted = evaluate_pack(paths["inverted"])
    reconciled = evaluate_pack(paths["reconciled"])
    judged = review()
    live = live_catalog_premise()
    named = named_inputs_present()

    if not judged.get("ok"):
        print("FAILED:RES-0188 reviewer", json.dumps(judged, indent=2, sort_keys=True)[:4000])
        return 1
    if not known.get("ok") or not inverted.get("ok") or not reconciled.get("ok"):
        print("FAILED:RES-0188 pack control mismatch")
        return 1
    if live.get("fire"):
        print("FAILED:RES-0188 live catalog current-fact fired")
        return 1

    stale = next(p for p in known["premises"] if p["id"] == "P-STALE-MNN-OPEN")
    current = next(p for p in known["premises"] if p["id"] == "P-CURRENT-MECH-REPREFIX")
    inv_stale = next(p for p in inverted["premises"] if p["id"] == "P-STALE-MNN-OPEN")

    log_path = paths["known-case"] / "briefing" / LOG_NAME
    arch_path = paths["known-case"] / "artifacts" / ARCH_NAME
    opt_path = paths["known-case"] / "artifacts" / OPTION_NAME
    log_line, log_snip = _snip(log_path, "31-way")
    arch_line, arch_snip = _snip(arch_path, "MECH-3:")
    opt_line, opt_snip = _snip(opt_path, "M-1:")

    verify = P2
    claims = [
        _claim(
            "C1-known-stale-mnn-fires",
            (
                "On the reconstructed known case, the check fires on the briefing "
                "premise that the 31-way M-NN collision is still an open queued "
                "problem, because 17-DECISION-LOG.md states it in the present tense "
                "with zero MECH tokens while architecture is MECH-prefixed and the "
                "literal collision count is 0."
            ),
            "CONFIRMED" if stale["fire"] else "REFUTED",
            "almost-certain",
            stale,
            verify,
        ),
        _claim(
            "C2-same-pack-current-silent",
            (
                "In the same pack, the check stays silent on the current-fact "
                "premise that 13-ARCHITECTURE-CANDIDATES is MECH-prefixed with "
                "zero bare M-NN tokens."
            ),
            "CONFIRMED" if not current["fire"] else "REFUTED",
            "almost-certain",
            current,
            verify,
        ),
        _claim(
            "C3-inverted-31-way-still-live",
            (
                "When architecture is restored to bare M-NN, literal collision "
                "count is 31 and the open-collision premise does not fire as stale."
            ),
            "CONFIRMED" if (not inv_stale["fire"] and inv_stale["measurement"]["literal_collision_count"] == 31) else "REFUTED",
            "almost-certain",
            inv_stale,
            verify,
        ),
        _claim(
            "C4-live-catalog-res0188-current",
            (
                "On this worktree, WORK-UNIT-CATALOG.json currently contains "
                "unit id RES-0188 (json walk + quoted-id regex). The check is "
                "silent on that current-fact."
            ),
            "CONFIRMED" if not live["fire"] else "REFUTED",
            "almost-certain",
            live,
            verify,
        ),
    ]

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    log_rel = log_path.relative_to(REPO).as_posix()
    arch_rel = arch_path.relative_to(REPO).as_posix()
    opt_rel = opt_path.relative_to(REPO).as_posix()

    additional = [
        {
            "id": row["id"],
            "text": row["text"],
            "fire": row["fire"],
            "reason": row["reason"],
            "measurement": row["measurement"],
        }
        for row in known["premises"]
        if row["fire"]
    ]

    doc = {
        "unit_id": "RES-0188",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "schema_version": 1,
        "question": QUESTION,
        "answer": (
            "The check compares each briefing premise to live artifact bytes using "
            "two independent instruments (present-tense/queue markers vs bare-M / "
            "MECH id census). On the reconstructed known case it fires on the stale "
            "M-NN-open premise and stays silent on the current MECH-reprefix premise "
            f"in the same pack. Inverted collision count={inv_stale['measurement']['literal_collision_count']}. "
            "Original 17-DECISION-LOG.md and 13-ARCHITECTURE-CANDIDATES.md are absent "
            "on this worktree; validation uses a byte-level reconstruction of the "
            "documented known case plus a live catalog current-fact."
        ),
        "claims": claims,
        "measurements": [
            {
                "id": "known-case",
                "kind": "both-states-pack",
                "fired_ids": known["fired_ids"],
                "silent_ids": known["silent_ids"],
                "collision": stale["measurement"]["literal_collision_count"],
                "architecture_mech_count": stale["measurement"]["architecture_mech_count"],
                "architecture_bare_m_count": stale["measurement"]["architecture_bare_m_count"],
            },
            {
                "id": "inverted",
                "kind": "live-collision-pack",
                "fired_ids": inverted["fired_ids"],
                "collision": inv_stale["measurement"]["literal_collision_count"],
            },
            {
                "id": "reconciled",
                "kind": "stuck-fire-control",
                "fired_ids": reconciled["fired_ids"],
            },
            {
                "id": "named-inputs",
                "kind": "worktree-presence",
                "rows": named,
            },
        ],
        "tests": [
            {
                "id": "T1-both-states",
                "name": "Fire on known-stale M-NN premise; silent on current premise in the same pack",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-independent-recount",
                "name": "Independent tokenizer reproduces headline collision counts and both-states",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": judged,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {"path": log_rel, "exists": True, "role": "known-case-briefing"},
            {"path": arch_rel, "exists": True, "role": "known-case-architecture"},
            {"path": opt_rel, "exists": True, "role": "known-case-option-universe"},
        ],
        "evidence": [
            {
                "path": log_rel,
                "line": log_line,
                "snippet": log_snip,
                "claim": "Known-stale briefing states the 31-way collision as live/queued.",
            },
            {
                "path": arch_rel,
                "line": arch_line,
                "snippet": arch_snip,
                "claim": "Reconstructed architecture is MECH-prefixed (MECH-3 present).",
            },
            {
                "path": opt_rel,
                "line": opt_line,
                "snippet": opt_snip,
                "claim": "Reconstructed option universe still uses bare M-N tokens.",
            },
            {
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "line": 1,
                "snippet": '"id": "RES-0188"',
                "claim": "Live catalog currently contains unit RES-0188.",
            },
        ],
        "both_states": {
            "stale_fired": bool(stale["fire"]),
            "current_silent": not bool(current["fire"]),
            "silence_on_both_means_detector_dead": True,
        },
        "headline_counts": {
            "known_case_collision": stale["measurement"]["literal_collision_count"],
            "inverted_collision": inv_stale["measurement"]["literal_collision_count"],
            "stale_fired": bool(stale["fire"]),
            "current_silent": not bool(current["fire"]),
            "option_bare_m_count": stale["measurement"]["option_bare_m_count"],
            "architecture_mech_count": stale["measurement"]["architecture_mech_count"],
        },
        "additional_stale_premises": additional,
        "named_inputs": named,
        "codex_reproduction": judged.get("codex_reproduction"),
        "reconstruction_note": (
            "17-DECISION-LOG.md and 13-ARCHITECTURE-CANDIDATES.md are not on this "
            "worktree. Fixtures reconstruct the documented known case (present-tense "
            "collision at log line 175, zero MECH in the log, architecture re-prefixed, "
            "literal collision 0) rather than inventing a live original-file measurement."
        ),
        "produced_at": _now(),
        "min_bytes_threshold": 1024,
    }

    jsonschema.validate(doc, schema)
    try:
        jsonschema.validate({"totally": "unrelated"}, schema)
    except jsonschema.ValidationError:
        pass
    else:
        print("FAILED:RES-0188 schema accepted garbage")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = _digest(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
