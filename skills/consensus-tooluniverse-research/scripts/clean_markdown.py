"""Convert Consensus custom render-tags in the extracted *_search.md into readable markdown,
and lift the structured bits (meter questions, search funnel, top contributors) into meta.json.

Tags handled: consensus_meter, figure_caption, search_strategy_diagram, top_contributors,
results_timeline, evidence_strength_indicator, research_gap_heatmap_cell, + generic fallback.

Race-safe vs resolve_and_download.py: only touches *_search.md and meta.json."""

from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

# Workspace from --ws DIR, $CONSENSUS_WS, or current dir; operates on <ws>/searches.
_ws = (
    Path(sys.argv[sys.argv.index("--ws") + 1])
    if "--ws" in sys.argv
    else Path(os.environ.get("CONSENSUS_WS") or Path.cwd())
)
WS = _ws / "searches"


def attr(tag: str, name: str):
    n = re.escape(
        name
    )  # name is a literal attribute name; escape keeps it a literal in the regex
    m = re.search(n + r"\s*=\s*'([^']*)'", tag) or re.search(
        n + r'\s*=\s*"([^"]*)"', tag
    )
    return m.group(1) if m else None


def parse_atjson(val: str | None):
    if not val:
        return None
    val = val.replace("@@json@@:", "")
    try:
        return json.loads(val)
    except Exception:
        return None


def clean(md: str, meta: dict) -> str:
    meters, funnels, contributors = [], [], []

    def meter_sub(m):
        q = attr(m.group(0), "generatedQueryOverride") or ""
        meters.append(q)
        return f"\n> 📊 **Consensus Meter** — claim tested: *“{q}”*  \n> _(rendered yes/possibly/mixed/no graph — visual in `graphs/`, data in `meta.json`)_\n"

    def figcap_sub(m):
        n = attr(m.group(0), "number")
        d = attr(m.group(0), "description") or ""
        return f"\n*Figure{(' ' + n) if n else ''} — {d}*\n"

    def funnel_sub(m):
        t = m.group(0)
        idp, scr, elig, inc = (
            attr(t, "identifiedPapers"),
            attr(t, "screenedPapers"),
            attr(t, "eligiblePapers"),
            attr(t, "includedPapers"),
        )
        funnels.append(
            {"identified": idp, "screened": scr, "eligible": elig, "included": inc}
        )
        return f"\n> **Search funnel:** identified {idp} → screened {scr} → eligible {elig} → **included {inc}**\n"

    def contrib_sub(m):
        a = parse_atjson(attr(m.group(0), "authors"))
        j = parse_atjson(attr(m.group(0), "journals"))
        contributors.append({"authors": a, "journals": j})
        out = ["\n**Top contributors**\n"]
        if a:
            out.append("- Authors: " + "; ".join(x.get("name", "?") for x in a) + "\n")
        if j:
            out.append("- Journals: " + "; ".join(x.get("name", "?") for x in j) + "\n")
        return "".join(out)

    md = re.sub(r"<consensus_meter\b[^>]*/>", meter_sub, md)
    md = re.sub(r"<figure_caption\b[^>]*/>", figcap_sub, md)
    md = re.sub(r"<search_strategy_diagram\b[^>]*/>", funnel_sub, md)
    md = re.sub(r"<top_contributors\b[^>]*/>", contrib_sub, md)
    md = re.sub(
        r"<results_timeline\s*/>",
        "\n*[Figure: results timeline — citations over time]*\n",
        md,
    )
    # inline cell tags -> just their number (they sit inside tables)
    md = re.sub(
        r"<evidence_strength_indicator\b[^>]*number=\"(\d+)\"[^>]*/>", r"\1", md
    )
    md = re.sub(r"<research_gap_heatmap_cell\b[^>]*number=\"(\d+)\"[^>]*/>", r"\1", md)
    # any remaining custom tag -> drop the tag, keep nothing noisy
    md = re.sub(r"<([a-z_]+)\b[^>]*/>", lambda m: f"*[{m.group(1)}]*", md)

    meta["consensus_meter_questions"] = meters
    meta["search_funnels"] = funnels
    meta["top_contributors"] = contributors
    return md


def main():
    for folder in sorted(p.name for p in WS.iterdir() if p.is_dir()):
        mdf = WS / folder / f"{folder}_search.md"
        if not mdf.exists():
            continue
        metaf = WS / folder / "meta.json"
        meta = json.loads(metaf.read_text(encoding="utf-8")) if metaf.exists() else {}
        cleaned = clean(mdf.read_text(encoding="utf-8"), meta)
        mdf.write_text(cleaned, encoding="utf-8")
        metaf.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            f"{folder}: {len(meta.get('consensus_meter_questions', []))} meters, "
            f"{len(meta.get('search_funnels', []))} funnels"
        )


if __name__ == "__main__":
    main()
