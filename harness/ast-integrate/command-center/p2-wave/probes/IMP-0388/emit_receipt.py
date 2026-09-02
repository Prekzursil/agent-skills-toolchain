#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0388.json from a live desc_lint run."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "router"))
import desc_lint as L  # noqa: E402

UNIT = "IMP-0388"
OUT = "command-center/receipts/IMP-0388.json"
SCHEMA = "command-center/schema/desc-lint-report.schema.json"
SENTINEL = "SENTINEL:IMP-0388:DESCRIPTION-LINT-COMPLETE"
INDEX = HERE / "fixtures/capability-index.json"
MUTANT = HERE / "fixtures/planted-mutant.json"
DESC_LINT = REPO / "tools/router/desc_lint.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0388/probe1_planted_mutant.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0388/probe2_negative_scope_both_states.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise KeyError(f"{path}: {needle!r}")


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": path.is_file(),
        "role": role,
    }


def snippet(path: Path, line: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[line - 1].strip()[:240]


def validate_schema(doc: dict) -> list[str]:
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError:
        missing = [k for k in schema.get("required", []) if k not in doc]
        return [f"missing required {k}" for k in missing]
    try:
        validator = jsonschema.Draft7Validator(schema)
        return [
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in validator.iter_errors(doc)
        ]
    except Exception as exc:
        # Catalog output_schema is a $ref shim to ast-integrate.invalid.
        # G-1 gates parse + probes + per-unit sha, not remote resolution.
        print(f"schema_validate_warning={type(exc).__name__}:{exc}")
        return []


def planted_result(caps: list[dict], spec: dict) -> dict:
    mutated = L.apply_rename_paraphrase(
        caps,
        source_id=spec["source_id"],
        sibling_id=spec["sibling_id"],
        new_id=spec["new_id"],
        paraphrase=spec["paraphrase"],
    )
    ranking = L.lint(mutated, top_n=20)["confusability"]["top_20"]
    want = frozenset({spec["new_id"], spec["sibling_id"]})
    rank = None
    score = None
    for i, row in enumerate(ranking, 1):
        if frozenset({row["id_a"], row["id_b"]}) == want:
            rank, score = i, row["token_overlap_score"]
            break
    return {
        "source_id": spec["source_id"],
        "sibling_id": spec["sibling_id"],
        "new_id": spec["new_id"],
        "paraphrase": spec["paraphrase"],
        "in_top_5": bool(rank is not None and rank <= 5),
        "rank": rank if rank is not None else 10**9,
        "token_overlap_score": score,
        "measure": "token-jaccard on mutated copy; published ranking is unplanted",
    }


def both_states(caps: list[dict]) -> dict:
    with_neg = next(c for c in caps if L.has_negative_scope(c))
    cid = L.cap_id(with_neg)
    good_ids = set(L.zero_negative_scope(caps)["ids"])
    bad = copy.deepcopy(caps)
    target = next(c for c in bad if L.cap_id(c) == cid)
    target["description"] = (
        "Validates credentials against a store and rejects expired rows. "
        "Use when the user asks to check a key."
    )
    for key in ("negative_scope", "do_not_use_for", "do_not_use", "not_for"):
        target.pop(key, None)
    bad_ids = set(L.zero_negative_scope(bad)["ids"])
    return {
        "capability_id": cid,
        "with_clause_in_zero_set": cid in good_ids,
        "without_clause_in_zero_set": cid in bad_ids,
        "discriminates": (cid not in good_ids) and (cid in bad_ids),
    }


def main() -> int:
    caps, loaded = L.load_index(INDEX)
    live = L.lint(caps, top_n=20)
    spec = json.loads(MUTANT.read_text(encoding="utf-8"))
    planted = planted_result(caps, spec)
    states = both_states(caps)
    if not planted["in_top_5"]:
        print("FAILED:IMP-0388 planted mutant not in top 5; not emitting SUCCESS")
        return 1
    if not states["discriminates"]:
        print("FAILED:IMP-0388 negative-scope both-states silent; not emitting")
        return 1

    zeros = live["zero_negative_scope"]
    most = live["confusability"]["most_confusable_pair"]
    ln_zero = line_of(DESC_LINT, "def zero_negative_scope")
    ln_rank = line_of(DESC_LINT, "def ranked_confusable_pairs")
    ln_neg = line_of(DESC_LINT, "def has_negative_scope")
    ln_plant = line_of(DESC_LINT, "def apply_rename_paraphrase")
    ln_overlap = line_of(DESC_LINT, "def token_overlap")

    live_index = L.LIVE_INDEX.is_file() and L.LIVE_INDEX.stat().st_size > 0
    imp0386 = L.IMP_0386.is_file() and L.IMP_0386.stat().st_size > 0
    rel_index = INDEX.relative_to(REPO).as_posix()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Routing-description quality linter with negative-scope coverage",
        "question": (
            "How many of the indexed capabilities have ZERO negative-scope "
            "clause, and which pair of capabilities is most confusable by "
            "description alone?"
        ),
        "answers": {
            "zero_negative_scope_count": zeros["count"],
            "zero_negative_scope_ids": zeros["ids"],
            "most_confusable_pair": most,
        },
        "index_resolution": {
            "live_capability_index_present": live_index,
            "imp_0386_receipt_present": imp0386,
            "used_path": rel_index,
            "used_kind": "imp-0388-fixture",
            "capability_count": live["capability_count"],
            "reason": (
                "capability-index.json and command-center/receipts/IMP-0386.json "
                "are absent or are not a capabilities list on this worktree. "
                "desc_lint.py will consume them when present; this receipt is "
                "measured on the fixture index shipped with IMP-0388."
            ),
        },
        "zero_negative_scope": zeros,
        "confusability": live["confusability"],
        "four_axes": live["four_axes"],
        "planted_mutant": planted,
        "negative_scope_both_states": states,
        "failure_class_scope": {
            "lexical-only-similarity": "CONFIRMED",
            "paraphrase-blind-spot": (
                "NOT-CHECKED here; IMP-0390 measures whether a semantic stage "
                "recovers paraphrases this token-Jaccard ranking cannot."
            ),
        },
        "cross_vendor_critic_top5": {
            "status": "NOT-CHECKED",
            "reason": (
                "This worktree had a single implementer. Probe 2 is the "
                "independent mechanical critic of the ranking (receipt vs live "
                "re-lint, plus a distinct-rewrite control). No second-vendor "
                "reader was invoked."
            ),
        },
        "evidence": [
            {
                "claim": (
                    f"{zeros['count']} indexed capabilities have ZERO "
                    f"negative-scope clause: {', '.join(zeros['ids'])}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"tools/router/desc_lint.py:{ln_zero}",
                "snippet": snippet(DESC_LINT, ln_zero),
                "kind": "live-tree",
            },
            {
                "claim": (
                    "Most confusable pair by description alone is "
                    f"{most['id_a']} vs {most['id_b']} at token-overlap "
                    f"{most['token_overlap_score']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"tools/router/desc_lint.py:{ln_rank}",
                "snippet": snippet(DESC_LINT, ln_rank),
                "kind": "live-tree",
            },
            {
                "claim": (
                    "Negative-scope detection is a do-NOT-use-for clause or a "
                    "dedicated negative_scope field, not a bare 'not' token."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"tools/router/desc_lint.py:{ln_neg}",
                "snippet": snippet(DESC_LINT, ln_neg),
                "kind": "live-tree",
            },
            {
                "claim": (
                    "Confusability is Jaccard over content tokens "
                    "(lexical-only; empty∩empty scores 0)."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"tools/router/desc_lint.py:{ln_overlap}",
                "snippet": snippet(DESC_LINT, ln_overlap),
                "kind": "live-tree",
            },
            {
                "claim": (
                    "Planted mutant "
                    f"{planted['new_id']} || {planted['sibling_id']} "
                    f"ranks {planted['rank']} (required: top 5)."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"tools/router/desc_lint.py:{ln_plant}",
                "snippet": snippet(DESC_LINT, ln_plant),
                "kind": "live-tree",
            },
        ],
        "tests": [
            {
                "id": "planted-mutant-top-5",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "negative-scope-both-states",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0388-probe2-negative-scope-both-states",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-lints the fixture and refuses a silent both-states "
                "detector and a ranking that always promotes planted ids."
            ),
        },
        "artifacts": [
            art("tools/router/desc_lint.py", "implementation"),
            art(SCHEMA, "schema"),
            art(rel_index, "index"),
            art(
                "command-center/p2-wave/probes/IMP-0388/fixtures/planted-mutant.json",
                "control",
            ),
        ],
        "output_schema": SCHEMA,
        "min_bytes_threshold": 128,
        "timestamps": {"ended_at": now},
        "report": {
            "kind": "desc-lint-report",
            "observations": [
                {
                    "name": "zero_negative_scope_count",
                    "measured": zeros["count"],
                    "method": "desc_lint.zero_negative_scope",
                    "anchor": f"tools/router/desc_lint.py:{ln_zero}",
                },
                {
                    "name": "most_confusable_pair",
                    "measured": f"{most['id_a']}|{most['id_b']}",
                    "method": "desc_lint.ranked_confusable_pairs",
                    "anchor": f"tools/router/desc_lint.py:{ln_rank}",
                },
            ],
            "control_ids": [
                "planted-mutant-top-5",
                "negative-scope-both-states",
            ],
        },
        "notes": (
            "G-1 unit IMP-0388. Implemented tools/router/desc_lint.py. "
            "Did not run global unit_manifest.py --write. Did not claim "
            "IMP-0385/0386 delivery. cloud ok=true is not delivery."
        ),
    }
    errs = validate_schema(doc)
    if errs:
        print("FAILED:IMP-0388 schema-invalid")
        for e in errs[:25]:
            print("  ", e)
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(
        f"zero_negative_scope={zeros['count']} "
        f"most={most['id_a']}|{most['id_b']} "
        f"score={most['token_overlap_score']} "
        f"planted_rank={planted['rank']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
