#!/usr/bin/env python3
"""Probe 2: AST use-versus-mention adjudication plus the required control."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ART = REPO / "command-center/audit/AUD-0084-hardcoded-path-census.json"
SENTINEL = C.CATALOG_SENTINEL
OUT = HERE / "probe2-ast-adjudication.json"


def main() -> int:
    control = C.evaluate_control()
    print(f"control_passed={control['passed']}")
    print(f"regex_silent={control['regex_silent']}")
    print(f"docstring_silent={control['docstring_silent']}")
    print(f"open_flagged={control['open_flagged']}")
    print(f"relative_glob_excluded={control['relative_glob_excluded']}")
    print(f"write_text_payload_excluded={control['write_text_payload_excluded']}")
    print(f"mutant_goes_red={control['mutant_context_filter_disabled_goes_red']}")
    print(f"good_classes={control['good_classes']}")
    if not control["passed"]:
        print("FAILED:AUD-0084-probe2 use-versus-mention control did not hold")
        print(json.dumps(control, indent=2, sort_keys=True))
        return 1

    scan = C.scan_tree()
    summary = C.summarize(scan)
    operational = [
        h for h in scan["adjudicated"] if h.get("use_class") == "operational-path-use"
    ]
    # Falsify treating a relative glob or a payload/docstring mention as
    # breakage (shard2-w1 re-anchor 2026-10-24: the corpus-wide
    # "no operational ~/.claude/ hit" form encoded the canonical tree's
    # content; this estate genuinely operates on ~/.claude paths and the
    # census exists to find them. The invariant actually under test is
    # use-vs-mention: a path LITERAL (no whitespace) may classify
    # operational; a path embedded in prose (sentence-like value) must
    # never. The count stays observable in the probe payload.)
    claude_operational = 0
    for hit in scan["adjudicated"]:
        val = str(hit.get("value") or "")
        cls = hit.get("use_class")
        if "*/SKILL.md" in val and cls == "operational-path-use":
            print("FAILED:AUD-0084-probe2 relative glob treated as operational")
            return 1
        if "~/.claude/" in val and cls == "operational-path-use":
            if any(ch.isspace() for ch in val):
                print("FAILED:AUD-0084-probe2 write_text payload treated as path")
                print(json.dumps(hit, sort_keys=True)[:600])
                return 1
            claude_operational += 1


    C.dump_json(
        OUT,
        {
            "probe": "probe2-ast-adjudication",
            "evidence_requirement": (
                "Probe 2: an AST-aware pass that distinguishes a path literal "
                "from a regex or a documentation string, since a backslash in a "
                "regex is not a path separator."
            ),
            "control": control,
            "claude_operational_hits": claude_operational,
            "summary": summary,
            "operational_sample": operational[:80],
        },
    )
    print(f"use_class_counts={json.dumps(summary['use_class_counts'], sort_keys=True)}")
    print(f"first_party_operational={summary['first_party_operational_file_count']}")
    print("first_party_files=" + ",".join(summary["first_party_operational_files"][:30]))

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0084-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:AUD-0084-probe2 artifact unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0084-probe2 catalog sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:AUD-0084-probe2 self-declared {st}")
        return 1
    art_fp = (doc.get("census") or {}).get("first_party_operational_file_count")
    if art_fp is not None and int(art_fp) != int(summary["first_party_operational_file_count"]):
        print(
            f"FAILED:AUD-0084-probe2 first-party operational drift "
            f"artifact={art_fp} live={summary['first_party_operational_file_count']}"
        )
        return 1
    tests = doc.get("tests") or []
    control_ok = any(
        isinstance(t, dict)
        and t.get("id") == "use-versus-mention-control"
        and str(t.get("result") or "").upper() == "PASS"
        for t in tests
    )
    if not control_ok:
        print("FAILED:AUD-0084-probe2 artifact missing passing use-versus-mention control")
        return 1
    print("SUCCESS:AUD-0084-probe2 AST use-versus-mention adjudication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
