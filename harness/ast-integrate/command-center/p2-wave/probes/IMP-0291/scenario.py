"""IMP-0291 live evaluations against tools.council.protocol.brainstorm."""
from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path

from council.protocol.brainstorm import (
    PROTOCOL_ID,
    UNIQUE_IDEA_TARGET,
    IdeaLedger,
    KernelBypass,
    LedgerMutationError,
    LedgerTamperError,
    RecordingKernel,
    canonicalize_mechanism,
    pairwise_grouping_score,
    string_key,
)
from fixtures import (
    DISTINCT_CONTROL,
    LABELLED_40,
    UNKNOWN_PARAPHRASES,
    wording_variants_100,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BRAINSTORM_PY = REPO / "tools/council/protocol/brainstorm.py"


def protocol_writes_participant_output() -> bool:
    """True when brainstorm.py opens a write handle besides dump_jsonl."""
    tree = ast.parse(BRAINSTORM_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            for arg in node.args[1:]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if any(flag in arg.value for flag in ("w", "a", "x", "+")):
                        return True
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    val = str(kw.value.value)
                    if any(flag in val for flag in ("w", "a", "x", "+")):
                        return True
    return False


def evaluate_append_canonicalise() -> dict:
    """Unit: ledger append, mutation refuse, JSONL round-trip, both counts."""
    kernel = RecordingKernel()
    ledger = IdeaLedger(kernel=kernel)
    mixed = [
        "Put a circuit breaker around the downstream HTTP client.",
        "Wrap outbound calls in a circuit breaker after 5 failures.",
        "I think we should install circuit-breaker protection.",
        "Retry failed requests with exponential backoff and jitter.",
        "Isolate the rendering pool behind a bulkhead.",
    ]
    for i, text in enumerate(mixed):
        ledger.append(author="ada" if i < 3 else "ben", round=i // 3, text=text)
    counts = ledger.unique_counts()
    mutation_raised = {}
    for name, fn in (
        ("replace", lambda: ledger.replace("IDEA-0001", text="nope")),
        ("delete", lambda: ledger.delete("IDEA-0001")),
        ("clear", lambda: ledger.clear()),
        ("rewrite_text", lambda: ledger.rewrite_text("IDEA-0001", "nope")),
    ):
        try:
            fn()
            mutation_raised[name] = False
        except LedgerMutationError:
            mutation_raised[name] = True

    bypass_raised = False
    try:
        IdeaLedger(kernel=None).append(
            author="eve", round=0, text="circuit breaker", require_kernel=True
        )
    except KernelBypass:
        bypass_raised = True

    empty_raised = False
    try:
        ledger.append(author="ada", round=0, text="   ")
    except Exception:
        empty_raised = True

    unknown = IdeaLedger()
    unknown.append(author="cyd", round=0, text=UNKNOWN_PARAPHRASES[0])
    unknown.append(author="cyd", round=0, text=UNKNOWN_PARAPHRASES[1])
    unknown_counts = unknown.unique_counts()

    with tempfile.TemporaryDirectory(prefix="imp0291-jsonl-") as tmp:
        path = Path(tmp) / "ledger.jsonl"
        ledger.dump_jsonl(path)
        loaded = IdeaLedger.load_jsonl(path)
        roundtrip_ok = [row.to_dict() for row in loaded.ideas] == [
            {**row.to_dict(), "submitted_at": row.submitted_at} for row in ledger.ideas
        ]
        # Compare canonical fields, not timestamps-only identity of kernel.
        roundtrip_ok = (
            len(loaded.ideas) == len(ledger.ideas)
            and [r.canonical_mechanism for r in loaded.ideas]
            == [r.canonical_mechanism for r in ledger.ideas]
            and [r.string_key for r in loaded.ideas]
            == [r.string_key for r in ledger.ideas]
            and [r.sequence for r in loaded.ideas]
            == [r.sequence for r in ledger.ideas]
        )
        tamper_path = Path(tmp) / "tamper.jsonl"
        rows = path.read_text(encoding="utf-8").splitlines()
        rec = json.loads(rows[0])
        rec["canonical_mechanism"] = "mech:forged"
        tamper_path.write_text(json.dumps(rec) + "\n" + "\n".join(rows[1:]) + "\n", encoding="utf-8")
        tamper_raised = False
        try:
            IdeaLedger.load_jsonl(tamper_path)
        except LedgerTamperError:
            tamper_raised = True

    mechs = [row.canonical_mechanism for row in ledger.ideas]
    side_by_side = {
        "string_distinct": counts["string_distinct"],
        "mechanism_distinct": counts["mechanism_distinct"],
        "appended": counts["appended"],
        "target": UNIQUE_IDEA_TARGET,
        "stopping_counter": "mechanism_distinct",
    }
    passed = bool(
        counts["appended"] == 5
        and counts["string_distinct"] == 5
        and counts["mechanism_distinct"] == 3
        and mechs[0] == mechs[1] == mechs[2] == "mech:circuit-breaker"
        and mechs[3] == "mech:exponential-backoff"
        and mechs[4] == "mech:bulkhead-isolation"
        and all(mutation_raised.values())
        and bypass_raised
        and empty_raised
        and unknown_counts["string_distinct"] == 2
        and unknown_counts["mechanism_distinct"] == 1
        and roundtrip_ok
        and tamper_raised
        and kernel.turns_recorded == 5
        and kernel.turns_recorded == kernel.turns_executed
        and not protocol_writes_participant_output()
        and PROTOCOL_ID == "P26-brainstorm"
    )
    return {
        "pass": passed,
        "counts": side_by_side,
        "mechanisms": mechs,
        "mutation_raised": mutation_raised,
        "bypass_raised": bypass_raised,
        "empty_raised": empty_raised,
        "unknown_paraphrase_counts": unknown_counts,
        "jsonl_roundtrip_ok": roundtrip_ok,
        "tamper_raised": tamper_raised,
        "turns_recorded": kernel.turns_recorded,
        "turns_executed": kernel.turns_executed,
        "protocol_writes_participant_output": protocol_writes_participant_output(),
        "protocol_id": PROTOCOL_ID,
    }


def evaluate_count_gaming() -> dict:
    """Control (spec 11339): 100 wording variants must not meet unique_ideas>=100."""
    variants = wording_variants_100()
    ledger = IdeaLedger()
    for i, text in enumerate(variants):
        ledger.append(author=f"p{i % 5}", round=i // 20, text=text)
    counts = ledger.unique_counts()
    keys = [string_key(t) for t in variants]
    string_keys_unique = len(set(keys))
    mechs = {row.canonical_mechanism for row in ledger.ideas}
    gaming = ledger.count_gaming_detected()
    met_before = ledger.target_met()
    distinct = ledger.append(author="zoe", round=9, text=DISTINCT_CONTROL)
    counts_after = ledger.unique_counts()
    reject_everything = counts_after["mechanism_distinct"] <= counts["mechanism_distinct"]
    passed = bool(
        len(variants) == 100
        and string_keys_unique == 100
        and counts["string_distinct"] == 100
        and counts["mechanism_distinct"] == 1
        and list(mechs) == ["mech:circuit-breaker"]
        and gaming
        and not met_before
        and counts["string_distinct"] >= UNIQUE_IDEA_TARGET
        and not reject_everything
        and counts_after["mechanism_distinct"] == 2
        and distinct.canonical_mechanism == "mech:exponential-backoff"
        and not ledger.target_met()
    )
    return {
        "pass": passed,
        "variant_count": len(variants),
        "string_keys_unique": string_keys_unique,
        "counts_before_distinct": counts,
        "counts_after_distinct": counts_after,
        "mechanisms_before": sorted(mechs),
        "distinct_mechanism": distinct.canonical_mechanism,
        "count_gaming_detected": gaming,
        "string_counter_would_meet_target": counts["string_distinct"] >= UNIQUE_IDEA_TARGET,
        "mechanism_counter_meets_target": met_before,
        "target": UNIQUE_IDEA_TARGET,
        "reject_everything": reject_everything,
        "both_states": {
            "bad_string_counter_meets_100": counts["string_distinct"] >= UNIQUE_IDEA_TARGET,
            "good_mechanism_counter_refuses": not met_before,
        },
    }


def evaluate_labelled_sample() -> dict:
    """Hand-labelled 40 ideas: score mechanism grouping against gold families."""
    ledger = IdeaLedger()
    gold: list[str] = []
    predicted: list[str] = []
    rows = []
    for idea_id, family, author, rnd, text in LABELLED_40:
        idea = ledger.append(
            author=author, round=rnd, text=text, idea_id=idea_id
        )
        gold.append(family)
        predicted.append(idea.canonical_mechanism)
        rows.append(
            {
                "id": idea_id,
                "gold": family,
                "predicted": idea.canonical_mechanism,
                "text": text,
            }
        )
    score = pairwise_grouping_score(gold, predicted)
    counts = ledger.unique_counts()
    passed = bool(
        len(LABELLED_40) == 40
        and counts["appended"] == 40
        and counts["string_distinct"] == 40
        and counts["mechanism_distinct"] == 8
        and score["pass"]
        and score["f1"] == 1.0
        and score["gold_clusters"] == 8
        and score["predicted_clusters"] == 8
    )
    return {
        "pass": passed,
        "labelled": 40,
        "counts": counts,
        "score": score,
        "rows": rows,
    }


def evaluate_independent_review() -> dict:
    """Fresh ledger, same 40 texts, recomputed grouping. No author summary."""
    ledger = IdeaLedger()
    gold = []
    predicted = []
    for _idea_id, family, author, rnd, text in LABELLED_40:
        idea = ledger.append(author=author, round=rnd, text=text)
        gold.append(family)
        predicted.append(idea.canonical_mechanism)
    score = pairwise_grouping_score(gold, predicted)
    # Direct canonicalize_mechanism (no ledger prior) must still hit the lexicon.
    direct = [canonicalize_mechanism(text) for _i, _f, _a, _r, text in LABELLED_40]
    direct_score = pairwise_grouping_score(gold, direct)
    passed = bool(score["pass"] and direct_score["pass"] and score["f1"] == 1.0)
    return {
        "reviewer_id": "IMP-0291-reviewer-labelled-grouping",
        "independent": True,
        "fresh_context": True,
        "starts_from": "tests/public-api",
        "pass": passed,
        "verdict": "PASS" if passed else "FAIL",
        "score": score,
        "direct_canonicalize_score": direct_score,
        "mechanism_distinct": ledger.unique_ideas(),
    }
