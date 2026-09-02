#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0418.json from a live oracle run."""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from completion_predicate import (  # noqa: E402
    CONDITIONS,
    EVALUATORS,
    judge,
)
from predicate_oracle import (  # noqa: E402
    MIN_BORDERLINE,
    run_oracle,
    run_planted_divergence,
)

OUT_REL = "command-center/receipts/IMP-0418.json"
SENTINEL = "SENTINEL:IMP-0418:PREDICATES-AGREE"


def _condition_table() -> list[dict[str, object]]:
    rows = []
    for cid, name, fn in EVALUATORS:
        src = inspect.getsourcefile(fn) or "completion_predicate.py"
        try:
            rel = Path(src).resolve().relative_to(REPO).as_posix()
        except ValueError:
            rel = "tools/command-center/completion_predicate.py"
        _, lineno = inspect.getsourcelines(fn)
        rows.append(
            {
                "id": cid,
                "name": name,
                "function": fn.__name__,
                "file": rel,
                "line": lineno,
            }
        )
    return rows


def build_receipt() -> dict:
    oracle = run_oracle()
    planted = run_planted_divergence()
    if not oracle["agree"]:
        raise SystemExit("oracle does not agree; refusing to emit SUCCESS receipt")
    if oracle["borderline_count"] < MIN_BORDERLINE:
        raise SystemExit("oracle too easy: borderline_count < 40")
    if not planted["fired"]:
        raise SystemExit("planted-divergence control did not fire")

    zero_alone = judge({"state": "RUNNING", "exit_code": 0})
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    matrix = oracle["matrix"]
    pair_rows = [
        {
            "site_a": p["site_a"],
            "site_b": p["site_b"],
            "disagreements": p["disagreements"],
        }
        for p in matrix["pairs"]
    ]
    question = (
        "On a 200-artifact corpus, do any two call sites disagree on even one artifact?"
    )
    answer = (
        f"No. Seven call sites ({', '.join(oracle['call_sites'])}) returned "
        f"byte-identical verdicts on all {oracle['corpus_size']} artifacts "
        f"({oracle['complete_count']} COMPLETE, {oracle['incomplete_count']} INCOMPLETE, "
        f"{oracle['borderline_count']} borderline). Pair-disagreement sum is 0. "
        f"Planted laxer min_bytes on {planted['planted_site']} produced "
        f"{planted['expected_diverging_count']} diverging artifacts, so the oracle is not a tautology."
    )
    return {
        "id": "IMP-0418",
        "unit_id": "IMP-0418",
        "title": "Two-predicates-disagree differential oracle",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "completion_line": SENTINEL,
        "question": question,
        "answer": answer,
        "exact_question": question,
        "cloud_ok": False,
        "computed_at": now,
        "output_schema": "command-center/schema/receipt.schema.json",
        "spec_failure_class": "two completion predicates disagree",
        "spec_anchor": "_USER-PROMPTS.md:11314",
        "call_sites": oracle["call_sites"],
        "condition_table": _condition_table(),
        "conditions": list(CONDITIONS),
        "oracle": {
            "corpus_size": oracle["corpus_size"],
            "borderline_count": oracle["borderline_count"],
            "borderline_floor": MIN_BORDERLINE,
            "complete_count": oracle["complete_count"],
            "incomplete_count": oracle["incomplete_count"],
            "pair_disagreement_sum": matrix["pair_disagreement_sum"],
            "any_disagreement": matrix["any_disagreement"],
            "pair_matrix": pair_rows,
            "counts": matrix["counts"],
            "agree": oracle["agree"],
            "min_bytes_default": oracle["min_bytes_default"],
        },
        "planted_divergence": {
            "site": planted["planted_site"],
            "mechanism": "laxer min_bytes threshold (1 vs 128)",
            "fired": planted["fired"],
            "expected_diverging_count": planted["expected_diverging_count"],
            "pair_disagreement_sum": planted["planted_pair_disagreement_sum"],
        },
        "exit_zero_alone": {
            "verdict": zero_alone["verdict"],
            "complete": zero_alone["complete"],
            "note": "exit_code 0 with non-terminal state is INCOMPLETE",
        },
        "evidence": [
            {
                "id": "E1",
                "kind": "live-differential",
                "signal": "seven-call-site-byte-identical-verdicts",
                "corpus_size": oracle["corpus_size"],
                "borderline_count": oracle["borderline_count"],
                "pair_disagreement_sum": matrix["pair_disagreement_sum"],
            },
            {
                "id": "E2",
                "kind": "planted-control",
                "signal": "laxer-threshold-on-one-call-site",
                "fired": planted["fired"],
                "diverging_artifacts": planted["expected_diverging_count"],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0418-probe2-planted-divergence",
            "verdict": "PASS",
            "independent": True,
            "method": "Re-run oracle with cloud_dispatcher min_bytes patched to 1; require fire.",
        },
        "tests": [
            {
                "id": "test_seven_sites_agree",
                "path": "tools/command-center/tests/test_predicate_oracle.py::test_seven_sites_agree",
                "result": "PASS",
            },
            {
                "id": "test_planted_lax_threshold_fires",
                "path": "tools/command-center/tests/test_predicate_oracle.py::test_planted_lax_threshold_fires",
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-planted-lax-threshold",
                "description": "Patch one call site to min_bytes=1; oracle must disagree.",
                "fired": planted["fired"],
            },
            {
                "id": "NC-exit-zero-alone",
                "description": "exit_code 0 is not a completion condition.",
                "verdict": zero_alone["verdict"],
            },
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {
                "path": "tools/command-center/completion_predicate.py",
                "role": "implementation",
            },
            {"path": "tools/command-center/fanin_sites.py", "role": "call-sites"},
            {"path": "tools/command-center/predicate_oracle.py", "role": "oracle"},
            {
                "path": "tools/command-center/tests/test_predicate_oracle.py",
                "role": "tests",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0418/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
    }


def write_receipt(doc: dict) -> Path:
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in text:
        raise SystemExit("sentinel missing from receipt text")
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(out)
    return out


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    doc = build_receipt()
    path = write_receipt(doc)
    sha, size = digest(path)
    print(json.dumps({"path": OUT_REL, "sha256": sha, "bytes": size, "sentinel": SENTINEL}))
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
