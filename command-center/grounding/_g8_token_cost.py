"""Convert the observed description-budget cut from CHARS to TOKENS.

The brief asserts the 328-skill listing costs ~28,413 tokens against the 40,000
that skillListingBudgetFraction 0.04 buys on a 1M window -- i.e. ~29% headroom.
But 26 skills are ALREADY rendering without descriptions, which is only possible
if the budget is EXHAUSTED. Those two cannot both be true.

This resolves it by measuring tokens with a real BPE tokenizer instead of a
chars/4 proxy. tiktoken is not Claude's tokenizer, but it is a far better
estimator than chars/4 for hyphen- and slash-dense technical text.

DETECTOR CONTROL: print the measured chars-per-token ratio. If it comes out at
~4.0 the proxy was fine and this probe adds nothing; if it is materially below
4.0 the brief's token figure is an under-estimate by that factor.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(r"C:/Users/Prekzursil/source/ast-integrate/command-center/grounding/G-BARE-DESC.json")
rows = [r for r in json.loads(DATA.read_text(encoding="utf-8")) if r.get("desc_chars") is not None]
rows.sort(key=lambda r: r["name"])

DAILY = Path(r"C:/Users/Prekzursil/.claude/skills.daily")

try:
    import tiktoken
except ImportError:
    print("tiktoken NOT INSTALLED -- cannot measure tokens. Reporting chars only.")
    total = sum(r["desc_chars"] + len(r["name"]) + 4 for r in rows)
    print(f"total listing chars (name + ': ' + desc + nl) = {total}")
    raise SystemExit(0)

for enc_name in ("o200k_base", "cl100k_base"):
    try:
        enc = tiktoken.get_encoding(enc_name)
    except Exception as exc:  # noqa: BLE001
        print(f"{enc_name}: unavailable ({exc})")
        continue

    # Reconstruct the listing line for each skill exactly as the prompt renders it.
    import re

    def desc_of(name: str) -> str:
        sk = DAILY / name / "SKILL.md"
        text = sk.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^description:\s*(.*)$", text, re.M)
        return (m.group(1).strip().strip("\"'") if m else "")

    lines, cum_tok, cut_tok = [], 0, None
    CUT_AFTER = "winui-app"  # last skill fully inside the observed budget region
    total_tok = 0
    for r in rows:
        line = f"- {r['name']}: {desc_of(r['name'])}\n"
        t = len(enc.encode(line))
        total_tok += t
        lines.append((r["name"], t))

    # tokens consumed by everything rendered WITH a description, in render order,
    # up to the greedy-fill exhaustion point measured at ~108,408 chars
    chars_cum, tok_cum = 0, 0
    for r in rows:
        c = r["desc_chars"] + len(r["name"])
        if chars_cum + c > 108_408:
            continue
        chars_cum += c
        tok_cum += len(enc.encode(f"- {r['name']}: {desc_of(r['name'])}\n"))

    total_chars = sum(r["desc_chars"] + len(r["name"]) + 4 for r in rows)
    print(f"\n=== {enc_name} ===")
    print(f"  FULL listing: {total_chars} chars -> {total_tok} tokens "
          f"({total_chars / total_tok:.2f} chars/token)")
    print(f"  AT the measured greedy cut (~108,408 desc+name chars): {tok_cum} tokens")
    print(f"  budget if 0.04 x 1,000,000 window = 40,000 tokens")
    print(f"  budget if 0.04 x   200,000 window =  8,000 tokens")
