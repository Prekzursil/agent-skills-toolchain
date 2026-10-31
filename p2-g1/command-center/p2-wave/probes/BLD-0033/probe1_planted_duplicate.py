#!/usr/bin/env python3
"""BLD-0033 probe1: planted-duplicate mechanism detection.

Receipt claims: a renamed rebuild of handled-ledger.mjs scores 1.0 (>=
threshold 0.52) and is caught DUPLICATE-OF even though export-name token
search misses the rename; a novel scheduler with shared vocabulary scores
~0.11 and stays GENUINELY-NEW; a deleted-only symbol is reachable via git
pickaxe. The mechanism engine (shape-normalized line shingles, Jaccard) is
rebuilt and all three controls are executed on fresh fixtures + a throwaway
git repo.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _shard6lib import ProbeFailure, git_fixture, check_receipt_core, require  # noqa: E402

UID = "BLD-0033"
THRESH = 0.52
HERE = Path(__file__).resolve().parent
EST = HERE / "fixtures" / "estate"

PRIOR = """\
export const LEDGER_VERSION = 2;
export function createLedger(root) {
  const entries = new Map();
  return {
    append(key, value) {
      if (entries.has(key)) {
        throw new Error("duplicate key: " + key);
      }
      entries.set(key, value);
      return entries.size;
    },
    flush() {
      const out = {};
      for (const [key, value] of entries) {
        out[key] = value;
      }
      return out;
    },
  };
}
"""

REBUILD = """\
export const JOURNAL_VERSION = 2;
export function createJournal(root) {
  const records = new Map();
  return {
    append(key, item) {
      if (records.has(key)) {
        throw new Error("duplicate key: " + key);
      }
      records.set(key, item);
      return records.size;
    },
    flush() {
      const out = {};
      for (const [key, item] of records) {
        out[key] = item;
      }
      return out;
    },
  };
}
"""

NOVEL = """\
export function makeScheduler(space) {
  const points = [];
  const bounce = (index) => {
    const angle = 2 * Math.PI * index / space;
    points.push([Math.cos(angle), Math.sin(angle)]);
    return points[points.length - 1];
  };
  return { bounce, points };
}
"""


TOK_RE = re.compile(
    r'[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|"[^"]*"|[^A-Za-z0-9_\s"]+'
)


def shape_tokens(text: str) -> list[str]:
    """Identifier-normalize the token stream so renames collapse.

    Receipt method (command-center/receipts/BLD-0033.json method.primary):
    "identifier-normalized w-shingles (w=5) Jaccard". Every identifier maps
    to I, every numeral to N; operators/punctuation/string literals survive
    verbatim. A pure rename therefore yields an IDENTICAL stream (Jaccard
    1.0); structurally novel code diverges regardless of vocabulary.
    """
    toks: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        for tok in TOK_RE.findall(line):
            if tok[0].isalpha() or tok[0] == "_":
                toks.append("I")
            elif tok[0].isdigit():
                toks.append("N")
            else:
                toks.append(tok)
    return toks


def shingles(tokens: list[str], w: int = 5) -> set[str]:
    return {"|".join(tokens[i:i + w]) for i in range(max(1, len(tokens) - w + 1))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b)


def score_pair(a_text: str, b_text: str) -> float:
    return jaccard(shingles(shape_tokens(a_text)), shingles(shape_tokens(b_text)))


def vocab_overlap(a_text: str, b_text: str) -> bool:
    words_a = set(re.findall(r"[A-Za-z]{4,}", a_text.lower()))
    words_b = set(re.findall(r"[A-Za-z]{4,}", b_text.lower()))
    return bool(words_a & words_b)


def main() -> int:
    doc = check_receipt_core(UID)
    (EST / "tools" / "lib").mkdir(parents=True, exist_ok=True)
    (EST / "tools" / "rebuilds").mkdir(parents=True, exist_ok=True)
    (EST / "tools/lib/handled-ledger.mjs").write_text(PRIOR, encoding="utf-8")
    (EST / "tools/rebuilds/task-journal.mjs").write_text(REBUILD, encoding="utf-8")
    (EST / "tools/rebuilds/geodesic-bounce-scheduler.mjs").write_text(NOVEL, encoding="utf-8")

    # planted renamed rebuild: mechanism caught, filename + exports differ
    s_dup = score_pair(PRIOR, REBUILD)
    require(s_dup >= THRESH,
            f"planted rebuild scored {s_dup:.3f} < {THRESH}")
    dup_verdict = "DUPLICATE-OF" if s_dup >= THRESH else "GENUINELY-NEW"

    # novel with shared vocabulary stays GENUINELY-NEW
    s_novel = score_pair(PRIOR, NOVEL)
    shared = vocab_overlap(PRIOR, NOVEL)
    require(s_novel < THRESH, f"novel scored {s_novel:.3f} >= {THRESH}")
    ceil = float((doc.get("method") or {}).get("novel_ceiling") or 0.34)
    require(s_novel < ceil, f"novel scored {s_novel:.3f} >= novel_ceiling {ceil}")
    require(shared, "novel fixture lacks shared vocabulary bait")

    # export-name token search MISSES the rename (strike-1 recall failure)
    export_names = re.findall(r"export (?:const|function) ([A-Za-z_][A-Za-z0-9_]*)", PRIOR)
    hits = [n for n in export_names if n in REBUILD]
    require(not hits, f"token search unexpectedly matched: {hits}")

    # git pickaxe reaches a deleted-only symbol
    symbol = "BLD0033_DELETED_ONLY_SYMBOL"
    repo, revs = git_fixture(
        {"tools/retired/once-only-scanner.mjs": f"export const {symbol} = true;\n"},
        delete=["tools/retired/once-only-scanner.mjs"],
    )
    p = subprocess.run(
        ["git", "-C", repo, "log", "--all", "-S", symbol, "--name-only",
         "--format=%H"],
        capture_output=True, text=True, timeout=120,
    )
    require(p.returncode == 0, f"git pickaxe failed: {p.stderr[:200]}")
    require("once-only-scanner.mjs" in p.stdout,
            f"deleted-only symbol not found via pickaxe: {p.stdout[:200]}")
    head = subprocess.run(["git", "-C", repo, "show", "HEAD:tools/retired/once-only-scanner.mjs"],
                          capture_output=True, text=True)
    require(head.returncode != 0, "deleted file still present in HEAD")

    obs = {o["name"] for o in doc["report"]["observations"]}
    require({"planted_duplicate_verdict", "planted_duplicate_score",
             "token_search_missed_rename", "novel_verdict",
             "git_history_deleted_only_symbol"} <= obs,
            f"receipt observation kinds changed: {sorted(obs)}")

    print(json.dumps({
        "probe": "probe1-planted-duplicate", "unit_id": UID,
        "dup_score": round(s_dup, 4), "dup_verdict": dup_verdict,
        "novel_score": round(s_novel, 4), "shared_vocab_bait": shared,
        "token_search_hits": hits, "git_pickaxe_found_deleted": True,
        "pass": True,
    }, ensure_ascii=False))
    print(f"SUCCESS:{UID}-probe1 renamed rebuild caught by mechanism "
          f"(score {s_dup:.2f}); novel stays GENUINELY-NEW; pickaxe finds "
          f"deleted-only symbol")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        print(f"FAILED:{UID}-probe1 {exc}")
        raise SystemExit(1)
