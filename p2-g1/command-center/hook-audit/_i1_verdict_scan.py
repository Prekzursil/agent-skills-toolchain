r"""_i1_verdict_scan.py -- how noisy would a "published verdict count" rule be?

The H4 rule in check_citations.py guards TABLES whose cells carry a unit (ms/s/%/x/B). A
bolded integer sitting next to a VERDICT LABEL in prose carries no unit and is in no table,
so it is invisible to every rule the gate has. That is the hole the refute round found:

    docs/hook-audit/HOOK-AUDIT.md:197  "**5 dirs INERT-CONFIRMED**"
    command-center/hook-audit/B6-FLEET.json  inertness.verdicts.INERT-CONFIRMED = 6

Before adding a rule I measure how many lines it would flag, because a rule that floods is
the failure mode this very audit is about (a hook that fires so often the reader ignores it).

Two candidate shapes are measured side by side:
  WIDE      token and an integer anywhere on the same line
  ADJACENT  token and an integer within ADJ characters of each other

VOCAB is DERIVED from the tracked evidence, never hand-written: any dict named `verdicts`
contributes its keys, and any string value shaped like an uppercase hyphenated label
contributes itself. A hand list would rot the moment a lane adds a verdict.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVID = REPO / "command-center" / "hook-audit"
DOCS = REPO / "docs" / "hook-audit"

LABEL = re.compile(r"^[A-Z][A-Z0-9]*(?:[-_][A-Z0-9]+)+$")
CITE = re.compile(r"<!--\s*cite:")
FENCE = re.compile(r"^\s*(```|~~~)")
ADJ = 40


def tracked_evidence() -> list[Path]:
    p = subprocess.run(
        ["git", "ls-files", "command-center/hook-audit/*.json"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return [REPO / line for line in p.stdout.split("\n") if line.strip()]


def harvest(obj, vocab: set[str], key: str | None = None) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "verdicts" and isinstance(v, dict):
                for label in v:
                    if LABEL.match(str(label)):
                        vocab.add(str(label))
            harvest(v, vocab, k)
    elif isinstance(obj, list):
        for v in obj:
            harvest(v, vocab, key)
    elif isinstance(obj, str) and LABEL.match(obj):
        vocab.add(obj)


def strip_fenced(text: str) -> list[str]:
    out, inside = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            inside = not inside
            out.append("")
            continue
        out.append("" if inside else line)
    return out


def main() -> int:
    vocab: set[str] = set()
    files = tracked_evidence()
    for fp in files:
        try:
            harvest(json.loads(fp.read_text(encoding="utf-8")), vocab)
        except (OSError, ValueError):
            continue
    print(
        f"== vocab derived from {len(files)} tracked evidence files: {len(vocab)} labels"
    )
    print("   " + ", ".join(sorted(vocab)))

    tok = re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(vocab)) + r")\b")
    num = re.compile(r"(?<![\w.])\d[\d,]*(?![\w.])")

    wide = adj = 0
    wide_uncited = adj_uncited = 0
    rows = []
    for md in sorted(DOCS.glob("*.md")):
        lines = strip_fenced(md.read_text(encoding="utf-8"))
        for i, line in enumerate(lines):
            bare = CITE.sub("", line)
            tms = list(tok.finditer(bare))
            nms = list(num.finditer(bare))
            if not tms or not nms:
                continue
            wide += 1
            near = any(
                abs(t.start() - n.start()) <= ADJ or abs(t.end() - n.end()) <= ADJ
                for t in tms
                for n in nms
            )
            window = "\n".join(lines[max(0, i - 3) : i + 2])
            cited = bool(CITE.search(window))
            if not cited:
                wide_uncited += 1
            if near:
                adj += 1
                if not cited:
                    adj_uncited += 1
                    rows.append(
                        {
                            "doc": md.name,
                            "line": i + 1,
                            "tokens": sorted({t.group(1) for t in tms}),
                            "text": line.strip()[:110],
                        }
                    )
    print(
        f"\n== WIDE     token+integer same line : {wide} lines, {wide_uncited} uncited"
    )
    print(f"== ADJACENT within {ADJ} chars        : {adj} lines, {adj_uncited} uncited")
    print(f"\n== ADJACENT + UNCITED (what the rule would flag): {len(rows)}")
    for r in rows:
        print(f"   {r['doc']}:{r['line']} {r['tokens']} :: {r['text']}")
    (EVID / "_I1-VERDICT-SCAN.json").write_text(
        json.dumps(
            {
                "vocab": sorted(vocab),
                "wide": wide,
                "wide_uncited": wide_uncited,
                "adjacent": adj,
                "adjacent_uncited": adj_uncited,
                "rows": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
