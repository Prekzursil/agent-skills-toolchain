"""IMP-0153 deliverable: use-vs-mention candidate extractor for prose corpora.

Mines prose corpora for described-but-never-implemented WORKFLOW candidates and
distinguishes USE (the document instructs a reader to adopt/run the workflow)
from MENTION (the document describes the workflow only to criticize, forbid, or
warn about it). A document that describes a workflow to criticize it must NOT
be harvested as a candidate.

Mechanism (kept inspectable rather than statistical):
- candidate sentences contain a workflow verb and look instructive;
- the mention guard suppresses a candidate when the sentence itself, or either
  neighbour sentence, carries a criticism/forbidding marker, or when the
  sentence embeds the workflow in quotes-as-example rather than instruction.

Re-run: python tools/workflow-foundry/wf_usemention.py <corpus-dir>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

WORKFLOW_VERBS = {
    "run", "execute", "generate", "validate", "emit", "build", "write",
    "scan", "re-run", "rerun", "recompute", "check", "assert", "verify",
    "record", "refuse", "reject", "splice", "replay", "fetch", "hash",
    "reproduce", "measure", "calibrate", "partition", "synthesize",
    "reconcile", "diff", "extract", "classify",
}

SEQUENCE_CUES = {
    "then", "after that", "afterwards", "before", "first", "next",
    "finally", "and then", "step", "once", "when done",
}

CRITICISM_MARKERS = [
    "anti-pattern", "antipattern", "failure mode", "do not", "does not",
    "must not", "should not", "never ", "don't", "wrong", "mistake",
    "criticiz", "criticis", "beware", "pitfall", "avoid", "instead of",
    "rather than", "broke", "defective", "silent", "overclaim", "bad idea",
    "myth", "misleading", "harmful", "dangerous", "waste",
]

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sentences(text: str) -> list:
    out = []
    for block in text.splitlines():
        block = block.strip().lstrip("-*0123456789. ").strip()
        if not block:
            continue
        out.extend(s.strip() for s in _SENT_SPLIT.split(block) if s.strip())
    return out


def _has_verb(low: str) -> bool:
    return any(re.search(r"\b" + re.escape(v) + r"\b", low) for v in WORKFLOW_VERBS)


def _has_cue(low: str) -> bool:
    return any(c in low for c in SEQUENCE_CUES)


def _criticism_idx(sentences: list) -> set:
    idx = set()
    for i, s in enumerate(sentences):
        low = " " + s.lower() + " "
        if any(m in low for m in CRITICISM_MARKERS):
            idx.add(i)
    return idx


def extract_candidates(text: str, doc_guarded: bool = False) -> list:
    """Return candidate workflow mentions with a USE/MENTION verdict each.

    doc_guarded: when the DOCUMENT context is criticism-dominant (decided by
    classify_document), every candidate is MENTION regardless of its local
    window - a post-mortem that restates each pipeline step is still a
    criticism, not an endorsement.
    """
    sentences = _sentences(text)
    crit = _criticism_idx(sentences)
    out = []
    for i, s in enumerate(sentences):
        low = " " + s.lower() + " "
        if not _has_verb(low):
            continue
        instructive = _has_cue(low) or low.strip().startswith(
            tuple(v for v in WORKFLOW_VERBS)
        )
        if not instructive:
            continue
        # The mention guard: criticism in this sentence or a neighbour, or the
        # workflow named inside quotation marks (quoted example, not advice),
        # or a criticism-dominant document context.
        guarded_reason = None
        if doc_guarded:
            guarded_reason = "criticism-dominant-document"
        elif i in crit or (i - 1) in crit or (i + 1) in crit:
            guarded_reason = "criticism-marker-in-window"
        elif '"' in s or "“" in s:
            guarded_reason = "quoted-example"
        out.append({
            "sentence": s[:400],
            "index": i,
            "verdict": "MENTION" if guarded_reason else "USE",
            "reason": guarded_reason or "instructive-workflow-sentence",
        })
    return out


_FORBID_RE = re.compile(r"do not adopt|never adopt|do not use|avoid it|worth naming|post-mortem")


def classify_document(text: str) -> dict:
    # Document-level context: what share of sentences carry criticism markers,
    # and does the doc forbid adoption outright?
    sentences = _sentences(text)
    crit = _criticism_idx(sentences)
    low_all = " " + text.lower() + " "
    crit_ratio = (len(crit) / len(sentences)) if sentences else 0.0
    forbidding = bool(_FORBID_RE.search(low_all))
    doc_guarded = forbidding or crit_ratio >= 0.2

    cands = extract_candidates(text, doc_guarded=doc_guarded)
    use = [c for c in cands if c["verdict"] == "USE"]
    mention = [c for c in cands if c["verdict"] == "MENTION"]
    doc_class = "USE" if use else ("MENTION" if mention else "CLEAN")
    return {
        "doc_class": doc_class,
        "use_candidates": use,
        "mention_candidates": mention,
        "candidate_count": len(cands),
        "criticism_ratio": round(crit_ratio, 4),
        "doc_guarded": doc_guarded,
    }


def scan_corpus(corpus_dir) -> list:
    corpus_dir = Path(corpus_dir)
    rows = []
    for p in sorted(corpus_dir.rglob("*.md")):
        res = classify_document(p.read_text(encoding="utf-8", errors="replace"))
        res["doc"] = p.name
        rows.append(res)
    return rows


def score_control_set(control_dir, labels_path) -> dict:
    """Precision/recall of doc-level USE classification against hand labels."""
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    control_dir = Path(control_dir)
    tp = fp = fn = tn = 0
    per_doc = []
    for doc, label in sorted(labels.items()):
        text = (control_dir / doc).read_text(encoding="utf-8", errors="replace")
        got = classify_document(text)["doc_class"]
        pred_use = got == "USE"
        true_use = label == "USE"
        if pred_use and true_use:
            tp += 1
        elif pred_use and not true_use:
            fp += 1
        elif not pred_use and true_use:
            fn += 1
        else:
            tn += 1
        per_doc.append({"doc": doc, "label": label, "predicted": got})
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "documents": len(labels),
        "true_positive": tp, "false_positive": fp,
        "false_negative": fn, "true_negative": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "per_document": per_doc,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    for row in scan_corpus(sys.argv[1]):
        print(json.dumps({
            "doc": row["doc"], "doc_class": row["doc_class"],
            "use": len(row["use_candidates"]),
            "mention": len(row["mention_candidates"]),
        }))
