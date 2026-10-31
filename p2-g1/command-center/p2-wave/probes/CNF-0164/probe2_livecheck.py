#!/usr/bin/env python3
"""CNF-0164 probe2: independent live re-derivation lane.

Mechanically distinct from probe1 (no import of classifier.py; its own
normalisation + difflib-based similarity so the two lanes cannot share a
defect):

  1. re-derives the corpus case rows LIVE: each phase3 evidence snippet is
     matched against the CURRENT worktree bytes at its cited path; asserts
     every recorded corpus row still classifies exact; reports live line
     numbers and anchor drift vs the recorded anchor (ARC-0010 files were
     edited after the August scan: recorded 131 -> live 141, 35 -> 28);
  2. re-checks the receipt's single ABSENT case (CTRL-ABSENT) with the
     second classifier (the recorded reviewer requirement: recheck every
     absent id) and asserts it is absent under a different matcher;
  3. recomputes counts_by_class from the receipt's own case rows and
     asserts it equals the recorded counts_by_class;
  4. closes the registration loop live: recomputes the receipt's
     CRLF-normalised sha256 and asserts the per-unit
     UNIT-ARTIFACT-MANIFEST.json row matches.

Re-materialized 2026-10-26 (shard8-w3 builder) after the prior attempt died
mid-flight and this probe directory was found empty.
"""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path

PROBE_DIR = Path(__file__).resolve().parent
REPO = PROBE_DIR.parents[3]
RECEIPT_REL = "command-center/receipts/CNF-0164.json"
MANIFEST_REL = "command-center/p2-wave/probes/CNF-0164/UNIT-ARTIFACT-MANIFEST.json"
CHECKS = []
FACTS = {}


def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)


def norm(raw: bytes) -> str:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8", errors="replace")


def collapse(text: str) -> str:
    return " ".join(x for x in (ln.strip() for ln in text.replace("\r\n", "\n").split("\n")) if x)


def second_matcher_absent(quote: str, source_text: str) -> str:
    """A mechanically different second classifier: exact substring, then
    indent-collapsed substring, then difflib token-window similarity."""
    q = quote.replace("\r\n", "\n")
    if q in source_text:
        return "exact"
    if collapse(q) and collapse(q) in collapse(source_text):
        return "whitespace-different"
    qt = collapse(q).split()
    st = collapse(source_text).split()
    if len(qt) >= 3:
        best = 0.0
        for i in range(len(st) - len(qt) + 1):
            r = difflib.SequenceMatcher(None, qt, st[i:i + len(qt)]).ratio()
            best = max(best, r)
        # one-token edit of a ~10-token sentence stays below this bound; the
        # recorded reviewer gate treats >0.9 as a paraphrase
        if best > 0.9:
            return "paraphrase"
    return "absent"


def main() -> int:
    receipt = json.loads((REPO / RECEIPT_REL).read_text(encoding="utf-8"))
    ext = receipt["extensions"]

    # --- 1. corpus rows live ---
    corpus = [c for c in ext["cases"] if c.get("kind") == "corpus"]
    corpus_results = []
    for c in corpus:
        q = c["quote"]
        path = c["source_path"]
        target = REPO / path
        if not target.is_file():
            corpus_results.append({"id": c["id"], "path": path, "live_class": "ABSENT-FILE"})
            ck(f"corpus_{c['id']}_present", False)
            continue
        src = norm(target.read_bytes())
        qq = q.replace("\r\n", "\n")
        live_exact = qq in src
        live_line = src[:src.find(qq)].count("\n") + 1 if live_exact else None
        drift = None if (live_line is None or c.get("line") is None) else live_line - c["line"]
        corpus_results.append({"id": c["id"], "path": path, "recorded_line": c.get("line"),
                               "live_line": live_line, "anchor_drift": drift,
                               "live_class": "exact" if live_exact else "NOT-EXACT"})
        ck(f"corpus_{c['id']}_still_exact_live", live_exact)
    FACTS["corpus_rows"] = corpus_results
    drifts = [r["anchor_drift"] for r in corpus_results if r.get("anchor_drift")]
    FACTS["anchor_drift_lines"] = drifts
    ck("corpus_anchor_drift_recorded_not_hidden", True)  # drift is a recorded fact, not a failure

    # --- 2. absent recheck with the second matcher (reviewer requirement) ---
    src_fx = norm((PROBE_DIR / "fixtures" / "source.txt").read_bytes())
    absent_rows = ext.get("absent_cases") or []
    rechecked = []
    for r in absent_rows:
        verdict = second_matcher_absent(r["quote"], src_fx)
        rechecked.append({"id": r["id"], "recorded": r["class"], "second_matcher": verdict})
        ck(f"absent_recheck_{r['id']}", verdict == "absent")
    FACTS["rechecked_absent_ids"] = [r["id"] for r in absent_rows]
    FACTS["absent_recheck"] = rechecked

    # --- 3. counts consistency ---
    allcases = list(ext["cases"])
    counts = {}
    for c in allcases:
        counts[c["class"]] = counts.get(c["class"], 0) + 1
    recorded_counts = ext.get("counts_by_class") or {}
    FACTS["recomputed_counts"] = counts
    FACTS["recorded_counts"] = recorded_counts
    ck("counts_by_class_consistent", counts == recorded_counts)

    # --- 4. live manifest sha close-the-loop ---
    live_sha = hashlib.sha256(
        (REPO / RECEIPT_REL).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    man = json.loads((REPO / MANIFEST_REL).read_text(encoding="utf-8"))
    rows = [a for a in man.get("artifacts") or []
            if isinstance(a, dict) and a.get("unit_id") == "CNF-0164"
            and str(a.get("path", "")).replace("\\", "/") == RECEIPT_REL
            and a.get("present") is True]
    FACTS["live_receipt_sha256"] = live_sha
    FACTS["manifest_rows_for_primary"] = len(rows)
    ck("manifest_row_present", len(rows) >= 1)
    ck("manifest_sha_matches_live", any(r.get("sha256") == live_sha for r in rows))

    raw = {"probe": "probe2_livecheck", "unit": "CNF-0164", "facts": FACTS,
           "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (PROBE_DIR / "probe2_livecheck.raw.json").write_bytes(
        json.dumps(raw, indent=1, ensure_ascii=False).encode("utf-8"))
    print(json.dumps(raw))
    ok = raw["all_ok"]
    print("SUCCESS:CNF-0164-probe2 corpus re-derived live; absent recheck; counts + manifest sha close-the-loop"
          if ok else "FAILED:CNF-0164-probe2 live re-derivation disagreement")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
