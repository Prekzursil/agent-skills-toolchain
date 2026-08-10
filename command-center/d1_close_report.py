"""Render the row-by-row tables of D1-CLOSE-REGISTRY-GAP.md FROM the measured JSON.

The prose in the .md is hand-written; the tables are GENERATED between the markers below, so a
number in the report cannot drift from the number that was measured. Hand-transcribing 84 rows
is exactly how a report ends up disagreeing with its own artifact.

Run:  python command-center/d1_close_report.py
"""

from __future__ import annotations

import json
from pathlib import Path

CC = Path("C:/Users/Prekzursil/source/ast-integrate/command-center")
MD = CC / "D1-CLOSE-REGISTRY-GAP.md"
BEFORE = CC / "D1-CLOSE-MATRIX.before.json"
AFTER = CC / "D1-CLOSE-MATRIX.after.json"
START = "<!-- GENERATED:rows -->"
END = "<!-- /GENERATED:rows -->"

#: NOT-COMPUTABLE is the CORRECT answer for these; the column says which rule refuses.
REFUSAL_GROUND = {
    "bedrock": "hosting plane - Bedrock serves Anthropic/Meta/Mistral models",
    "vertex": "hosting plane - Vertex serves Anthropic models too",
    "azure": "hosting plane - Azure OpenAI Service serves OpenAI models",
    "openrouter": "router - the vendor behind a routed call is unknown",
    "unassigned": "placeholder - the field was never filled in",
    "Google Cloud": "hosting plane (registered alias of vertex)",
    "AWS Bedrock Inc": "hosting plane (strips to aws-bedrock)",
    "Amazon Web Services": "hosting plane (registered alias of bedrock)",
    "Azure AI": "hosting plane (registered alias of azure)",
    "n/a": "placeholder",
    "totally-made-up-vendor": "UNREGISTERED - genuinely unidentifiable",
    "Acme Inc": "UNREGISTERED - strips to 'acme', still unknown",
    "Acme AI Ltd": "UNREGISTERED - strips to 'acme', still unknown",
    "Anthropic Killer Inc": "UNREGISTERED - strips to 'anthropic-killer', NOT anthropic",
    "Inc": "a bare corporate form names no vendor",
    "Ltd.": "a bare corporate form names no vendor",
    "AI": "a bare descriptor names no vendor",
    "openai-ish": "UNREGISTERED near-miss",
    "!!!": "folds to an EMPTY candidate, which never matches",
    "...": "folds to an EMPTY candidate, which never matches",
    "unknown-vendor-inc": "UNREGISTERED - strips to 'unknown-vendor'",
    "": "blank field",
    "None": "absent field",
    "7": "not a string",
    "{'vendor': 'openai'}": "not a string",
}


def _show(value: str) -> str:
    """Render a cell so an INVISIBLE character is visible.

    A row whose whole point is a U+200B renders as two identical-looking `anthropic` cells
    otherwise - the report would hide the very thing it is reporting.
    """
    out = []
    for ch in value:
        if ch.isprintable() and ch.isascii():
            out.append("\\|" if ch == "|" else ch)
        else:
            out.append(f"<U+{ord(ch):04X}>")
    return "".join(out) or "<empty string>"


def _ground(row: dict) -> str:
    for side in (row["reviewer"], row["executor"]):
        if side in REFUSAL_GROUND:
            return REFUSAL_GROUND[side]
    return "see reason column of the JSON artifact"


def _rows_table(before: list[dict], after: list[dict], title: str) -> list[str]:
    out = [f"### {title}", ""]
    out.append("| # | executor | reviewer | expected | BEFORE | AFTER | correct |")
    out.append("|---|---|---|---|---|---|---|")
    for i, (b, a) in enumerate(zip(before, after, strict=True), 1):
        assert (b["executor"], b["reviewer"]) == (a["executor"], a["reviewer"])
        flip = "**" if b["comparison"] != a["comparison"] else ""
        out.append(
            f"| {i} | `{_show(b['executor'])}` | `{_show(b['reviewer'])}` | {b['expected']} | "
            f"{flip}{b['comparison']}{flip} | {flip}{a['comparison']}{flip} | "
            f"{'yes' if a['correct'] else 'NO'} |"
        )
    out.append("")
    return out


def _refusals_table(after: list[dict]) -> list[str]:
    nc = [r for r in after if r["comparison"] == "NOT-COMPUTABLE"]
    out = [
        f"### The {len(nc)} rows that remain NOT-COMPUTABLE, and why each one does",
        "",
        "Every one is a row whose EXPECTED outcome is a refusal. None is a same-vendor or a",
        "cross-vendor pair that the resolver failed to classify.",
        "",
        "| # | executor | reviewer | expected | why NOT-COMPUTABLE is the right answer |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(nc, 1):
        out.append(
            f"| {i} | `{_show(r['executor'])}` | `{_show(r['reviewer'])}` | "
            f"{r['expected']} | {_ground(r)} |"
        )
    out.append("")
    over = [r for r in nc if r["expected"] != "NC"]
    out.append(
        f"**Rows that are NOT-COMPUTABLE but should not be: {len(over)}.** "
        + ("None." if not over else f"{over}")
    )
    out.append("")
    return out


def main() -> int:
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    after = json.loads(AFTER.read_text(encoding="utf-8"))
    body: list[str] = []
    body += _rows_table(
        before["rows_audit45"],
        after["rows_audit45"],
        "The Wave 3 audit's 45 rows, imported verbatim from `wave3_floor_audit.py:D1_PAIRS`",
    )
    body += _rows_table(
        before["rows_extended"],
        after["rows_extended"],
        "The 39 extended rows added by this unit (real-world spellings + over-fold guards)",
    )
    body += _refusals_table(after["rows_audit45"] + after["rows_extended"])

    text = MD.read_text(encoding="utf-8")
    head, _, rest = text.partition(START)
    _, _, tail = rest.partition(END)
    MD.write_text(
        head + START + "\n\n" + "\n".join(body) + END + tail,
        encoding="utf-8",
        newline="\n",
    )
    total = len(after["rows_audit45"]) + len(after["rows_extended"])
    print(f"rendered {total} rows into {MD.name}")
    print("SUCCESS:d1-close-report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
