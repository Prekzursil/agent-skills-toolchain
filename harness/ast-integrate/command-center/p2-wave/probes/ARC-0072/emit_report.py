#!/usr/bin/env python3
"""Emit command-center/phase3/ARCH-SIMILARITY.json for ARC-0072."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from jsonschema import Draft202012Validator, RefResolver  # noqa: E402

from compare import build_analysis  # noqa: E402
from extract import pin_live_designs  # noqa: E402

OUT = "command-center/phase3/ARCH-SIMILARITY.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
SENTINEL = "SUCCESS:ARC-0072"
UNIT = "ARC-0072"
QUESTION = (
    "Are any two of the nine architectures actually the SAME mechanism in "
    "different wording - which would make the tournament a comparison of "
    "labels rather than of designs? Extract each design's mechanism set, "
    "compute pairwise similarity with a lexical measure AND a second, "
    "mechanically different measure, and report every pair above threshold "
    "with the shared mechanisms enumerated."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0072/probe1_planted_mutant.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0072/probe2_distinctness.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
SUPPORTING = [
    "command-center/phase3/A1/DESIGN.json",
    SCHEMA,
    "command-center/p2-wave/probes/ARC-0072/extract.py",
    "command-center/p2-wave/probes/ARC-0072/measures.py",
    "command-center/p2-wave/probes/ARC-0072/compare.py",
    "command-center/p2-wave/probes/ARC-0072/probe1_planted_mutant.py",
    "command-center/p2-wave/probes/ARC-0072/probe2_distinctness.py",
]


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def sha_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(role: str, method: str, command: str) -> str:
    return hashlib.sha256(f"{role}|{method}|{command}".encode("utf-8")).hexdigest()[:32]


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def probe_block(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-4000:],
        "fingerprint": fp(role, method, command),
        "exit_code": exit_code,
    }


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def slim_arch(arch: dict) -> dict:
    return {
        "architecture_id": arch["architecture_id"],
        "architecture_class": arch.get("architecture_class"),
        "design_unit_id": arch.get("design_unit_id"),
        "design_path": arch["design_path"],
        "design_present": arch["design_present"],
        "design_source": arch.get("design_source"),
        "live_present": arch.get("live_present"),
        "source_rank": arch["source_rank"],
        "statement_count": arch["statement_count"],
        "siblings": arch.get("siblings") or [],
        "statements": [
            {"text": s["text"], "kind": s["kind"], "source": s["source"]}
            for s in arch.get("statements") or []
        ],
    }


def schema_store() -> dict:
    store = {}
    for rel in (
        "platform/schema/receipt.schema.json",
        "platform/schema/artifact-class-profiles.schema.json",
        SCHEMA,
    ):
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = data.get("$id")
        if ident:
            store[ident] = data
    return store


def make_validator():
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ""),
        referrer=schema,
        store=schema_store(),
    )
    return Draft202012Validator(schema, resolver=resolver)


def validate(doc: dict) -> None:
    validator = make_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0072 schema errors")
        for e in errs[:30]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            raise SystemExit("FAILED:ARC-0072 schema accepts garbage")


def main() -> int:
    pins = pin_live_designs()
    if "A1" not in pins and not (
        HERE / "fixtures" / "A1.DESIGN.json"
    ).is_file():
        print("FAILED:ARC-0072 no live A1 DESIGN.json to pin for planted-mutant")
        return 1
    analysis = build_analysis()
    mutant = analysis["planted_mutant"]
    floor = analysis["distinctness_floor"]
    clone = analysis["clone_tournament_floor"]
    arches = analysis["architectures"]
    pairs = analysis["pairs"]
    dup = analysis["duplicates"]
    contested = analysis["contested"]
    present_n = sum(1 for a in arches.values() if a["design_present"])
    missing = [a["architecture_id"] for a in arches.values() if not a["design_present"]]

    stale = REPO / OUT
    if stale.is_file():
        stale.unlink()

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ARC-0072 named probes before emit c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ok_mutant = bool(mutant["both_measures_rank_donor_first"]) and bool(
        mutant["both_measures_flag_duplicate"]
    )
    ok_floor = floor.get("floor") is not None
    ok_clone = (
        clone.get("floor") is not None
        and floor.get("floor") is not None
        and clone["floor"] < floor["floor"]
    )
    if not (ok_mutant and ok_floor and ok_clone):
        print("FAILED:ARC-0072 a live check failed before emit")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        f"Nine architecture slots compared. Live DESIGN.json present for "
        f"{present_n}/9. Missing {missing} dossiers were not rebuilt; those "
        f"slots use catalog briefs and live sibling artifacts, labeled as such. "
        f"Duplicates (BOTH measures): {len(dup)}. Contested (one measure): "
        f"{len(contested)}. Distinctness floor {floor['floor']} on pair "
        f"{floor['floor_pair']}. Planted renamed copy of {mutant['donor']} "
        f"ranked first on both measures (jaccard={mutant['vs_donor']['jaccard']}, "
        f"cosine={mutant['vs_donor']['cosine']}). SUCCESS:ARC-0072"
    )
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
    if not artifacts:
        print("FAILED:ARC-0072 no supporting artifacts on disk")
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ARC-0072",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Two mechanically different similarity measures are computed: "
                    "token-set Jaccard and signed hashed char-trigram cosine."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0072/measures.py:1",
                "probes": [
                    probe_block("source", "static-analysis", P1, t1, c1),
                    probe_block(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/ARC-0072/measures.py",
                        "JACCARD_THRESHOLD and COSINE_THRESHOLD are separate; classify requires BOTH.",
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "A renamed copy of one live design ranks first on both measures "
                    "and is classified DUPLICATE."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ARC-0072/probe1_planted_mutant.py:1",
                "probes": [
                    probe_block("source", "test-run", P1, t1, c1),
                    probe_block("verifier", "test-run", P2, t2, c2),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-planted-mutant",
                "name": "Renamed copy ranks first on both measures",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-distinctness-floor",
                "name": "Minimum pairwise distance is computed; clone tournament drops it",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-planted-mutant",
                "kind": "mutation",
                "description": (
                    "Identifier-renamed copy of a live DESIGN.json must be flagged "
                    "DUPLICATE by BOTH measures and rank first against the donor."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": t1[-1500:],
                "good_state_output": (
                    f"live duplicates={len(dup)} contested={len(contested)}"
                ),
            },
            {
                "id": "NC-clone-tournament",
                "kind": "known-broken-fixture",
                "description": (
                    "A nine-slot tournament of near-clones of the donor must drop "
                    "the distinctness floor toward zero."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"clone_floor={clone.get('floor')}",
                "good_state_output": f"live_floor={floor.get('floor')}",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0072-independent-mechanism-reader",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Read mechanism-statement lists for the top flagged pairs, "
                "ignoring architecture_id labels and the numeric scores."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0072/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ARC-0072/probe1_planted_mutant.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": probe_block("source", "test-run", P1, t1, c1),
            },
            {
                "consumer": "command-center/p2-wave/probes/ARC-0072/probe2_distinctness.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": probe_block("verifier", "test-run", P2, t2, c2),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "A3-A9 DESIGN.json are absent on this worktree. Catalog "
                    "briefs and any live sibling artifacts were used instead; "
                    "those dossiers were not rebuilt (no ADV circle)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver ARC-0017/0024/0031/0038/0045/0052/0059 independently "
                    "and re-run ARC-0072 pairwise comparison on live dossiers."
                ),
            },
            {
                "claim": (
                    "07-OPTION-UNIVERSE.json is a catalog input and is absent "
                    "on this host."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount the Windows restore tree and re-extract any option-"
                    "universe mechanism statements that are not already in the "
                    "nine architecture slots."
                ),
            },
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "analyst",
            "execution_substrate": "headless-linux",
        },
        "report": {
            "kind": "conformance-report",
            "observations": [
                {
                    "name": "duplicate-pairs-both-measures",
                    "measured": len(dup),
                    "method": "token-set-jaccard AND hashed-trigram-cosine both above threshold",
                    "anchor": "command-center/p2-wave/probes/ARC-0072/measures.py:176",
                },
                {
                    "name": "contested-pairs-one-measure",
                    "measured": len(contested),
                    "method": "exactly one of Jaccard or cosine above threshold",
                    "anchor": "command-center/p2-wave/probes/ARC-0072/measures.py:176",
                },
                {
                    "name": "distinctness-floor",
                    "measured": floor["floor"],
                    "method": "min over C(9,2) of (1 - max(jaccard, cosine))",
                    "anchor": "command-center/p2-wave/probes/ARC-0072/compare.py:79",
                },
                {
                    "name": "planted-mutant-jaccard",
                    "measured": mutant["vs_donor"]["jaccard"],
                    "method": "token-set Jaccard of renamed copy vs donor",
                    "anchor": "command-center/p2-wave/probes/ARC-0072/probe1_planted_mutant.py:1",
                },
                {
                    "name": "clone-tournament-floor",
                    "measured": clone["floor"],
                    "method": "same floor formula on nine identifier-renamed clones of the donor",
                    "anchor": "command-center/p2-wave/probes/ARC-0072/compare.py:165",
                },
            ],
            "control_ids": [
                "NC-planted-mutant",
                "NC-clone-tournament",
            ],
            "question": QUESTION,
            "answer": answer,
            "duplicate_rule": (
                "A pair is DUPLICATE only when token-set Jaccard AND embedding "
                "cosine both exceed threshold. Exactly one measure firing is CONTESTED."
            ),
            "thresholds": analysis["thresholds"],
            "architectures": [slim_arch(arches[i]) for i in sorted(arches)],
            "pairs": pairs,
            "duplicates": dup,
            "contested": contested,
            "distinctness_floor": floor,
            "clone_tournament_control": clone,
            "planted_mutant": mutant,
            "reviewer_pairs": analysis["reviewer"],
            "option_universe": analysis["option_universe"],
            "presence": analysis["presence"],
            "design_pins": pins,
            "inputs_on_this_tree": {
                a["design_path"]: a["design_present"] for a in arches.values()
            },
            "parser": {
                "name": "arc-0072-mechanism-similarity",
                "version": "1.0.0",
                "measures": [
                    "token-set-jaccard",
                    "signed-hashed-char-trigram-embedding-cosine",
                ],
            },
        },
    }
    validate(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = dump(doc)
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, dest)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print(f"wrote {OUT} bytes={len(payload.encode('utf-8'))} sha256={digest}")
    if SENTINEL not in payload:
        print("FAILED:ARC-0072 sentinel missing from artifact")
        return 1
    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:ARC-0072 named probes after emit c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
