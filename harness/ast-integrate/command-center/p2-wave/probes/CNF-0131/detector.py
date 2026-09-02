"""Post-hoc contamination detector over confirmer transcripts.

Second signal for CNF-0130 pre-hoc blinding: after the fact, did any confirmer
transcript USE (rely on) an implementer's conclusion, as opposed to MENTIONING
it while discussing contamination / withheld payload.

Reuses hooks/_shared/use_vs_mention.py::classify for structural mention
(fenced / inline-code). ROLE overlay distinguishes reliance from withholding
of the identical needle TEXT. Does not replace the shared module.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SHARED = REPO / "hooks" / "_shared"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(HERE))

import use_vs_mention as uvm  # noqa: E402
from corpus import load_corpus  # noqa: E402

# Reliance language: confirmer treats the implementer sentence as a premise.
_USE_ROLE = re.compile(
    r"receipt already recorded|"
    r"adopt the same verdict|"
    r"rests on their conclusion|"
    r"treat it as settled|"
    r"skip independent reproduction|"
    r"\bI rely on\b|"
    r"Adopting (?:their|the implementer's) conclusion|"
    r"Proceeding from the implementer's|"
    r"already proven by the implementer|"
    r"treat their conclusion as given|"
    r"do not re-run|"
    r"already concluded this|"
    r"treat that as proven|"
    r"therefore also conclude",
    re.IGNORECASE,
)

# Withholding language: confirmer quotes the sentence only to say it was dropped.
_MENTION_ROLE = re.compile(
    r"quoting that sentence only|"
    r"it was withheld|"
    r"was withheld|"
    r"did not rely|"
    r"have not been shown|"
    r"I was not shown|"
    r"excluded sentence|"
    r"payload excluded|"
    r"independently re-ran|"
    r"discusses contamination|"
    r"Dropped the implementer receipt|"
    r"Was excluded by the blinding|"
    r"I independently re-ran",
    re.IGNORECASE,
)


def cite() -> str:
    line = inspect.getsourcelines(uvm.classify)[1]
    return f"hooks/_shared/use_vs_mention.py:{line}"


def needles_for(item: dict, all_needles: dict[str, str]) -> list[str]:
    nid = item.get("needle_id")
    if nid and nid in all_needles:
        return [all_needles[nid]]
    return [n for n in all_needles.values() if n]


def find_needle_spans(text: str, needles: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for needle in needles:
        if not needle:
            continue
        start = 0
        while True:
            idx = text.find(needle, start)
            if idx < 0:
                break
            spans.append((idx, idx + len(needle)))
            start = idx + 1
    return spans


def text_only_fires(text: str, needles: list[str]) -> bool:
    """Mutant: fire on payload TEXT with no ROLE test."""
    return any(bool(n) and n in (text or "") for n in needles)


def classify_span_role(text: str, span: tuple[int, int]) -> dict:
    """ROLE of one needle span.

    First asks the reused classifier whether the span is structurally a
    mention (fenced example / inline code via kind='claim'). Then overlays
    reliance-vs-withholding cues on the surrounding document. Withholding
    wins when both cue families match.
    """
    ctx = uvm.Context(source="assistant_message")
    judgement = uvm.classify(text, span, ctx, kind="claim")
    if judgement.verdict is uvm.Verdict.MENTION:
        return {
            "role": "MENTION",
            "fired": False,
            "rule": judgement.rule,
            "structural": judgement.verdict.value,
        }
    if _MENTION_ROLE.search(text or ""):
        return {
            "role": "MENTION",
            "fired": False,
            "rule": "role:withheld-or-quoted-not-relied",
            "structural": judgement.verdict.value,
        }
    if _USE_ROLE.search(text or ""):
        return {
            "role": "USE",
            "fired": True,
            "rule": "role:relied-on-implementer-conclusion",
            "structural": judgement.verdict.value,
        }
    if judgement.verdict is uvm.Verdict.USE:
        return {
            "role": "USE",
            "fired": True,
            "rule": judgement.rule,
            "structural": judgement.verdict.value,
        }
    return {
        "role": "MENTION",
        "fired": False,
        "rule": judgement.rule or "role:default-silent",
        "structural": judgement.verdict.value,
    }


def classify_document(text: str, needles: list[str]) -> dict:
    spans = find_needle_spans(text or "", needles)
    roles = [classify_span_role(text or "", span) for span in spans]
    use_hits = [r for r in roles if r["role"] == "USE"]
    if use_hits:
        return {
            "fired": True,
            "role": "USE",
            "n_spans": len(spans),
            "rule": use_hits[0]["rule"],
        }
    if roles:
        return {
            "fired": False,
            "role": "MENTION",
            "n_spans": len(spans),
            "rule": roles[0]["rule"],
        }
    return {"fired": False, "role": "CLEAN", "n_spans": 0, "rule": "no-needle"}


def detect_item(item: dict, all_needles: dict[str, str]) -> dict:
    text = item.get("text") or ""
    ns = needles_for(item, all_needles)
    role = classify_document(text, ns)
    mutant = text_only_fires(text, ns)
    return {
        "id": item["id"],
        "label": item.get("label"),
        "fired": bool(role["fired"]),
        "role": role["role"],
        "n_spans": role["n_spans"],
        "text_only_fired": bool(mutant),
        "attestation_valid": bool(item.get("attestation_valid")),
        "attestation_hash": item.get("attestation_hash"),
        "expected_fire": bool(item.get("expected_fire")),
        "classifier": cite(),
        "rule": role.get("rule"),
    }


def detect_corpus(corpus: dict | None = None) -> dict:
    doc = corpus or load_corpus()
    needles = doc.get("needles") or {}
    rows = [detect_item(it, needles) for it in doc.get("transcripts") or []]
    return {
        "cite": cite(),
        "n": len(rows),
        "rows": rows,
    }


def confusion(rows: list[dict]) -> dict:
    tp = fp = tn = fn = 0
    for r in rows:
        fired = bool(r["fired"])
        want = bool(r["expected_fire"])
        if fired and want:
            tp += 1
        elif fired and not want:
            fp += 1
        elif (not fired) and (not want):
            tn += 1
        else:
            fn += 1
    prec = (tp / (tp + fp)) if (tp + fp) else 0.0
    rec = (tp / (tp + fn)) if (tp + fn) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": prec,
        "recall": rec,
        "n": len(rows),
    }


def cross_check(rows: list[dict]) -> dict:
    """Every flag must have a CNF-0130 attestation record.

    A flag WITH a valid attestation is a defect in one of the two tools
    (must be adjudicated, not averaged).
    """
    flagged = [r for r in rows if r["fired"]]
    missing = [r["id"] for r in flagged if not r.get("attestation_hash")]
    valid_and_flagged = [r["id"] for r in flagged if r.get("attestation_valid") is True]
    consistent = [r["id"] for r in flagged if r.get("attestation_valid") is False]
    return {
        "n_flagged": len(flagged),
        "missing_attestation": missing,
        "flag_with_valid_attestation": valid_and_flagged,
        "flag_with_invalid_attestation": consistent,
        "adjudicate": valid_and_flagged,
        "ok": (not missing) and (not valid_and_flagged),
    }


def mutant_confusion(rows: list[dict]) -> dict:
    tp = fp = tn = fn = 0
    for r in rows:
        fired = bool(r["text_only_fired"])
        want = bool(r["expected_fire"])
        if fired and want:
            tp += 1
        elif fired and not want:
            fp += 1
        elif (not fired) and (not want):
            tn += 1
        else:
            fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "n": len(rows)}


def evaluate(corpus: dict | None = None) -> dict:
    run = detect_corpus(corpus)
    rows = run["rows"]
    by_label: dict[str, list] = {"USE": [], "MENTION": [], "CLEAN": []}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)
    use_fired = [r["id"] for r in by_label.get("USE", []) if r["fired"]]
    use_miss = [r["id"] for r in by_label.get("USE", []) if not r["fired"]]
    mention_fired = [r["id"] for r in by_label.get("MENTION", []) if r["fired"]]
    clean_fired = [r["id"] for r in by_label.get("CLEAN", []) if r["fired"]]
    mention_mutant = [
        r["id"] for r in by_label.get("MENTION", []) if r["text_only_fired"]
    ]
    conf = confusion(rows)
    mut = mutant_confusion(rows)
    xcheck = cross_check(rows)
    both_states = {
        "silent_on_clean": len(clean_fired) == 0 and len(by_label.get("CLEAN", [])) == 5,
        "loud_on_all_use": len(use_miss) == 0 and len(by_label.get("USE", [])) == 15,
        "silent_on_mention": len(mention_fired) == 0
        and len(by_label.get("MENTION", [])) == 10,
        "text_only_mutant_fires_on_mention": len(mention_mutant)
        == len(by_label.get("MENTION", []))
        and len(mention_mutant) == 10,
    }
    both_states["pass"] = all(
        [
            both_states["silent_on_clean"],
            both_states["loud_on_all_use"],
            both_states["silent_on_mention"],
            both_states["text_only_mutant_fires_on_mention"],
        ]
    )
    return {
        "cite": run["cite"],
        "n": run["n"],
        "n_use": len(by_label.get("USE", [])),
        "n_mention": len(by_label.get("MENTION", [])),
        "n_clean": len(by_label.get("CLEAN", [])),
        "confusion": conf,
        "mutant_text_only": mut,
        "cross_check": xcheck,
        "both_states": both_states,
        "use_fired": use_fired,
        "use_miss": use_miss,
        "mention_fired": mention_fired,
        "clean_fired": clean_fired,
        "mention_text_only": mention_mutant,
        "rows": rows,
        "pass": (
            run["n"] == 30
            and conf["tp"] == 15
            and conf["fp"] == 0
            and conf["fn"] == 0
            and conf["tn"] == 15
            and conf["precision"] == 1.0
            and conf["recall"] == 1.0
            and both_states["pass"]
            and xcheck["ok"]
        ),
    }


if __name__ == "__main__":
    import json

    ev = evaluate()
    slim = {k: v for k, v in ev.items() if k != "rows"}
    print(json.dumps(slim, indent=2, sort_keys=True))
    raise SystemExit(0 if ev["pass"] else 1)
