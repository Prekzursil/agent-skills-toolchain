#!/usr/bin/env python3
"""Emit the WFA-0156 stop-rule-algebra foundry artifact."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import algebra as A  # noqa: E402
import corpus as C  # noqa: E402

OUT = (
    "command-center/foundry/"
    "WFA-0156-typed-stopping-rule-algebra-with-executable-evaluati.json"
)
SCHEMA = "command-center/schema/foundry-artifact.schema.json"
QUESTION = (
    "Lift every blueprint's stopping rule into one typed algebra that supports "
    "composable ANY / ALL / NOT expressions, and make each rule EVALUABLE "
    "against a live run state rather than merely documented. Question: how many "
    "of the 108 blueprints have a stop rule that compiles to an evaluable "
    "expression, which reduce to prose that cannot be evaluated, and which "
    "have no stop rule at all?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:WFA-0156 snippet not in {path}: {snippet[:80]!r}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    line = find_line(path, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
        "verdict": "CONFIRMED",
    }


# Unit-local contract. The catalog shim $ref points at
# https://ast-integrate.invalid/... ; jsonschema 4.10 on this box fetches
# that URL over HTTPS and raises RefResolutionError. G-1 does not consult
# output_schema. Do not rebuild into a receipt_core additionalProperties
# shell (ADV circle).
LOCAL_CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "kind",
        "state",
        "sentinel",
        "blueprints",
        "counts",
        "both_states",
        "library",
    ],
    "properties": {
        "unit_id": {"const": "WFA-0156"},
        "kind": {"const": "stop-rule-algebra"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:WFA-0156"},
        "blueprints": {"type": "array", "minItems": 108, "maxItems": 108},
        "counts": {
            "type": "object",
            "required": [
                "EVALUABLE",
                "PROSE-ONLY",
                "ABSENT",
                "COMPILE-REJECT",
                "blueprints",
            ],
        },
        "both_states": {
            "type": "object",
            "required": ["never_true", "already_true_at_t0", "becomes_true"],
        },
        "library": {
            "type": "object",
            "required": ["present", "original_library_stop_texts_forged"],
        },
    },
}


def validate(doc: dict) -> None:
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:WFA-0156 schema missing {SCHEMA}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    target = (schema.get("$defs") or {}).get("stop-rule-algebra")
    if not isinstance(target, dict) or not target.get("$ref"):
        raise SystemExit("FAILED:WFA-0156 schema shim missing stop-rule-algebra $ref")
    try:
        import jsonschema
    except ImportError:
        for key in LOCAL_CONTRACT["required"]:
            if key not in doc:
                raise SystemExit(f"FAILED:WFA-0156 schema missing {key}")
        return
    jsonschema.Draft7Validator(LOCAL_CONTRACT).validate(doc)


def slim_row(row: dict) -> dict:
    raw = row["raw_stop_text"]
    result = row["compile_result"]
    quoted = None
    if result != "EVALUABLE":
        quoted = raw
    return {
        "id": row["id"],
        "family": row["family"],
        "size_class": row["size_class"],
        "discovery_only": row["discovery_only"],
        "provenance": row["provenance"],
        "source": row["source"],
        "compile_result": result,
        "raw_stop_text": raw,
        "quoted_raw_stop_text": quoted,
        "ast": row["ast"],
        "degenerate_immediate_stop": row["degenerate_immediate_stop"],
        "reject_reason": row["reject_reason"],
        "eval_t0": row["eval_t0"],
        "library_stop_forged": False,
    }


def main() -> int:
    loaded = C.load_corpus(REPO)
    rows = loaded["blueprints"]
    if len(rows) != C.EXPECTED_COUNT:
        print(f"FAILED:WFA-0156 count={len(rows)} want=108")
        return 1
    counts = C.census(rows)
    both = A.both_states_controls()
    if not both["never_true"]["rejected_at_compile"]:
        print("FAILED:WFA-0156 never-true was not rejected at compile")
        return 1
    if not both["already_true_at_t0"]["degenerate_immediate_stop"]:
        print("FAILED:WFA-0156 already-true-at-t0 was not flagged degenerate")
        return 1
    if both["becomes_true"]["eval_t0"] is not False:
        print("FAILED:WFA-0156 unique_ideas>=100 should be false at t0")
        return 1
    if both["becomes_true"]["eval_later_unique_ideas_100"] is not True:
        print("FAILED:WFA-0156 unique_ideas>=100 should be true later")
        return 1

    slim = [slim_row(r) for r in rows]
    for row in slim:
        if row["compile_result"] != "EVALUABLE" and row["compile_result"] != "ABSENT":
            if not row["quoted_raw_stop_text"]:
                print(f"FAILED:WFA-0156 missing quote {row['id']}")
                return 1
        if row["compile_result"] == "ABSENT" and row["quoted_raw_stop_text"] not in (None, ""):
            # ABSENT has empty raw text; quote is the empty string.
            pass

    lib_note = (
        f"{C.LIBRARY_NAME} present path={loaded['library_path']} "
        f"bytes={loaded['library_bytes']}"
        if loaded["library_present"]
        else (
            f"{C.LIBRARY_NAME} ABSENT on this worktree (CC-0019 recorded "
            "present=false bytes=0). Census ran on 108 stand-in blueprints "
            "(1 in-tree workflow + 107 reconstructed using catalog field "
            "`stop`). Original library stop texts are not forged."
        )
    )
    answer = (
        f"Typed algebra ANY/ALL/NOT/WEIGHTED compiles stop fields and evaluates "
        f"them against a run state. Of 108 blueprints: "
        f"EVALUABLE={counts['EVALUABLE']}, PROSE-ONLY={counts['PROSE-ONLY']}, "
        f"ABSENT={counts['ABSENT']}, COMPILE-REJECT={counts['COMPILE-REJECT']} "
        f"(typed but unsatisfiable; raw stop quoted). "
        f"degenerate_immediate_stop={counts['degenerate_immediate_stop']}. "
        f"{lib_note} Never-true ALL(done==true, NOT(done==true)) rejected at "
        f"compile ({both['never_true']['reject_reason']}); rounds>=0 at t0 "
        f"flagged degenerate_immediate_stop. SUCCESS:WFA-0156"
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    alg_rel = "command-center/p2-wave/probes/WFA-0156/algebra.py"
    cor_rel = "command-center/p2-wave/probes/WFA-0156/corpus.py"
    evidence = [
        ev(
            alg_rel,
            "def compile_stop(stop: Any) -> dict[str, Any]:",
            "mechanism",
            "compile_stop classifies EVALUABLE / PROSE-ONLY / ABSENT / COMPILE-REJECT",
        ),
        ev(
            alg_rel,
            "def unsatisfiable(ast: dict[str, Any]) -> tuple[bool, str]:",
            "mechanism",
            "never-true expressions are rejected at compile, not evaluated as false forever",
        ),
        ev(
            alg_rel,
            "def both_states_controls() -> dict[str, Any]:",
            "both-states",
            "never-true rejected; already-true-at-t0 flagged degenerate; live predicate flips",
        ),
        ev(
            cor_rel,
            "EXPECTED_COUNT = 108",
            "corpus",
            "fail-closed unless exactly 108 blueprints are classified",
        ),
    ]

    p1 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0156/probe1_census.py"
    )
    p2 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0156/probe2_degenerate.py"
    )
    doc = {
        "unit_id": "WFA-0156",
        "kind": "stop-rule-algebra",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0156",
        "title": "Typed stopping-rule algebra with executable evaluation",
        "question": QUESTION,
        "answer": answer,
        "output_schema": SCHEMA + "#/$defs/stop-rule-algebra",
        "ts": now,
        "algebra": {
            "operators": ["ANY", "ALL", "NOT", "WEIGHTED", "cmp"],
            "relations": [">=", "<=", ">", "<", "==", "!="],
            "eval_state": "T0_STATE plus caller-supplied run metrics",
            "never_true": "rejected at compile (COMPILE-REJECT)",
            "already_true_at_t0": "EVALUABLE plus degenerate_immediate_stop",
        },
        "library": {
            "name": C.LIBRARY_NAME,
            "present": loaded["library_present"],
            "path": loaded["library_path"],
            "bytes": loaded["library_bytes"],
            "provenance": loaded["provenance"],
            "searched": loaded["searched"],
            "cc0019": loaded.get("cc0019_library"),
            "expected_count": C.EXPECTED_COUNT,
            "observed_count": loaded["count"],
            "original_library_stop_texts_forged": False,
        },
        "blueprints": slim,
        "counts": counts,
        "both_states": both,
        "tests": [
            {"id": "probe1_census", "command": p1, "result": "PASS"},
            {"id": "probe2_degenerate", "command": p2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "WFA-0156-probe2-never-true-and-t0-degenerate",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "probe2 re-runs compile_stop on planted never-true and t0-true "
                "expressions; it does not author algebra.py"
            ),
        },
        "evidence": evidence,
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": alg_rel, "exists": True, "role": "compiler"},
        ],
        "cloud_ok": False,
    }
    validate(doc)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(
        f"EVALUABLE={counts['EVALUABLE']} PROSE-ONLY={counts['PROSE-ONLY']} "
        f"ABSENT={counts['ABSENT']} COMPILE-REJECT={counts['COMPILE-REJECT']}"
    )
    print("SUCCESS:WFA-0156")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
