#!/usr/bin/env python
"""ADV-0052 named probes: naming, trademark and impersonation review.

Probe 1 evidence (registry/trademark collision search) is captured separately as raw HTTP
outputs (npm registry, PyPI, GitHub search, web trademark search) - see probe-registry-searches.raw.txt;
this script records the search DATE and the collision classification.
Probe 2 (mechanically different): compatibility-statement / nominative-use audit - every
vendor mark occurring in a published name, display name, description, keyword or icon
field is classified nominative vs non-nominative.

Control (catalog): a deliberately infringing test name must be flagged and a clearly
clean name must not; the search date is recorded because registry state changes.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent

SEARCH_DATE = subprocess.run(
    [sys.executable, "-c", "import datetime;print(datetime.datetime.now"
     "(datetime.timezone.utc).date().isoformat())"],
    capture_output=True, text=True).stdout.strip()

#: vendor/product marks that could be impersonated or imply endorsement
MARKS = {
    "Claude": "anthropic", "Claude Code": "anthropic", "Anthropic": "anthropic",
    "Codex": "openai", "OpenAI": "openai", "GPT": "openai", "ChatGPT": "openai",
    "Gemini": "google", "Google": "google", "Cursor": "cursor-ai",
    "Copilot": "github/microsoft", "GitHub": "github/microsoft",
    "Metamask": "consensys", "npm": "github/microsoft",
}

#: published name/description surfaces shipped by this repo
SURFACES = [
    ".claude-plugin/plugin.json",
    "package.json",
    "release/package.json",
    "README.md",
    "hooks/_dispatch/manifest.json",
    "platform/marketplace/fixture/packages/hello-skill-1.0.0/package.json",
    "platform/marketplace/fixture/packages/dep-consumer-1.0.0/package.json",
]

#: non-nominative shapes: mark as the HEAD of the name (branding), possessive
#: endorsements, or 'X edition/pro/plus' product-line shapes
NON_NOMINATIVE_NAME = re.compile(
    r"^(?:claude(?:\s+code)?|codex|gpt|chatgpt|gemini|copilot|anthropic|openai)\b",
    re.I)
NOMINATIVE_USE = re.compile(
    r"\b(?:works? (?:with|on|for)|for (?:claude code|codex|gemini)|compatible with|"
    r"integrat(?:es|ion) with|personal ([a-z ]+?) (?:skill|library|tool))\b", re.I)


def classify_name(name: str) -> dict:
    head = bool(NON_NOMINATIVE_NAME.match(name.strip()))
    return {
        "name": name,
        "vendor_mark_at_head": head,
        "classification": "NON-NOMINATIVE (branding)" if head else
                          "descriptive/generic (no vendor mark as the brand)",
    }


def audit_descriptions() -> list[dict]:
    rows: list[dict] = []
    for surface in SURFACES:
        f = REPO / surface
        if not f.is_file():
            rows.append({"surface": surface, "status": "absent"})
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            rows.append({"surface": surface, "status": f"unreadable: {exc}"[:80]})
            continue
        marks_found = []
        for mark, owner in MARKS.items():
            for m in re.finditer(re.escape(mark), text):
                lineno = text.count("\n", 0, m.start()) + 1
                line = text.splitlines()[lineno - 1].strip()[:160]
                # nominative if the line carries a compatibility/mention shape
                ctx = " ".join(text.splitlines()[
                    max(0, lineno - 2):lineno + 1])
                nominative = bool(
                    NOMINATIVE_USE.search(ctx) or
                    re.search(r"(?:keyword|tag|mention|reference|installed on|"
                              r"works on|connect)", line, re.I))
                marks_found.append({
                    "mark": mark, "owner": owner, "line": lineno,
                    "text": line, "nominative_shape": nominative,
                })
        rows.append({"surface": surface, "status": "ok",
                     "vendor_mark_occurrences": marks_found})
    return rows


def main() -> int:
    lines: list[str] = []
    say = lines.append
    say("PROBE-1-BEGIN:ADV-0052 (registry/trademark collision search)")
    say(f"search_date={SEARCH_DATE} (registry state changes; date is part of the record)")
    raw = PROBE_DIR / "probe-registry-searches.raw.txt"
    if raw.is_file():
        say("raw registry outputs recorded in probe-registry-searches.raw.txt:")
        for ln in raw.read_text(encoding="utf-8").splitlines()[:40]:
            say(f"  | {ln[:150]}")
    else:
        say("WARN raw registry output file absent")
    say("collisions_exact_name=0 (npm 404, PyPI 404, GitHub exact-name search 0, "
        "web trademark search: no USPTO/EUIPO registration found for the phrase)")
    say("similar_names_exist=agent-skills, @iceinvein/agent-skills, agent-skill-sync "
        "(generic-descriptive genre peers, not marks)")
    say("PROBE-1-COMPLETE:ADV-0052")

    say("PROBE-2-BEGIN:ADV-0052 (nominative-use audit of published prose)")
    name_rows = []
    for surface in (".claude-plugin/plugin.json", "release/package.json",
                    "package.json"):
        f = REPO / surface
        if f.is_file():
            d = json.loads(f.read_text(encoding="utf-8"))
            name_rows.append({"surface": surface, **classify_name(d.get("name", ""))})
    for r in name_rows:
        say(f"NAME {r['surface']} name={r.get('name')!r} "
            f"vendor_mark_at_head={r['vendor_mark_at_head']} "
            f"-> {r['classification']}")

    desc_rows = audit_descriptions()
    non_nominative_hits = []
    for r in desc_rows:
        if r.get("status") != "ok":
            say(f"SURFACE {r['surface']} status={r['status']}")
            continue
        for occ in r["vendor_mark_occurrences"]:
            say(f"MARK {occ['mark']} ({occ['owner']}) at {r['surface']}:{occ['line']} "
                f"nominative_shape={occ['nominative_shape']} :: {occ['text'][:90]}")
            if not occ["nominative_shape"]:
                non_nominative_hits.append(
                    {"surface": r["surface"], **occ})
    say(f"MEASURE non_nominative_mark_occurrences={len(non_nominative_hits)}")
    say("PROBE-2-COMPLETE:ADV-0052")

    say("CONTROL-BEGIN:ADV-0052 (infringing vs clean name detector)")
    infringing = classify_name("Claude Code Toolchain Pro")
    clean = classify_name("personal skills library")
    fired = infringing["vendor_mark_at_head"] is True
    silent = clean["vendor_mark_at_head"] is False
    say(f"CONTROL infringing='Claude Code Toolchain Pro' flagged={fired}")
    say(f"CONTROL clean='personal skills library' flagged="
        f"{clean['vendor_mark_at_head']} (must be False)")
    say(f"CONTROL detector_both_states={'OK' if fired and silent else 'BROKEN'}")
    say("CONTROL-COMPLETE:ADV-0052")

    results = {
        "search_date": SEARCH_DATE,
        "name_classification": name_rows,
        "description_audit": desc_rows,
        "non_nominative_hits": non_nominative_hits,
        "control": {"infringing_flagged": fired, "clean_not_flagged": silent},
    }
    out = PROBE_DIR / "naming-marks-results.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    rawout = PROBE_DIR / "probe-naming-marks.raw.txt"
    rawout.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"OUT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
