#!/usr/bin/env python3
"""Probe 2: content classification of Probe-1 hits.

Inert prose AGENTS.md vs PreToolUse-registering AGENTS.md must both be asserted
on the single planted fixture. A CLAUDE.md that is only prose must be inert —
the filename is not a risk finding. A filename-only mutant must go red on the
inert files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import autoload as A  # noqa: E402

UID = "AUD-0081"
ART = REPO / "command-center/audit/AUD-0081-untrusted-autoload-config-audit.json"
OUT = HERE / "probe2-classify.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def _report(doc: dict) -> dict:
    report = doc.get("report")
    return report if isinstance(report, dict) else {}


def check_artifact(control: dict, live_active_n: int) -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if (
        "SUCCESS:AUD-0081 emitted only when the artifact at output_path exists, "
        "is non-empty, parses against output_schema, and both named probes are "
        "recorded with their verbatim output"
    ) not in text:
        return "artifact completion_sentinel absent"
    doc = json.loads(text)
    report = _report(doc)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"artifact self-declared {doc.get('state')}"
    cls = doc.get("classification")
    if not isinstance(cls, dict):
        cls = report.get("classification") or {}
    if cls.get("both_states_on_one_fixture") is not True:
        return "artifact missing both-states fixture pass"
    if int(cls.get("live_untrusted_active_count", -1)) != live_active_n:
        return (
            "artifact live_untrusted_active_count "
            f"{cls.get('live_untrusted_active_count')!r} != live {live_active_n}"
        )
    if control.get("pass") is not True:
        return "live control is red while artifact exists"
    return None


def main() -> int:
    classified = A.classify_hits()
    control = A.control_both_states(classified)
    live_active = A.live_untrusted_active(classified)
    if not control["inert_agents_present"] or not control["active_agents_present"]:
        return fail("fixture AGENTS.md pair not in classified hit set")
    if not control["inert_classified_inert"]:
        return fail("prose AGENTS.md was not classified inert")
    if not control["active_classified_active"]:
        return fail("PreToolUse AGENTS.md was not classified active")
    if not control["both_states_on_one_fixture"]:
        return fail("both-states control did not pass on the single fixture")
    if not control["claude_classified_inert"]:
        return fail("prose CLAUDE.md was classified as a risk finding")
    if not control["filename_only_mutant_flags_inert_agents"]:
        return fail("filename-only mutant silent on inert AGENTS.md")
    if not control["filename_only_mutant_flags_inert_claude"]:
        return fail("filename-only mutant silent on inert CLAUDE.md")
    if not control["pass"]:
        return fail(f"control bundle red {json.dumps(control)}")

    payload = {
        "probe": "probe2-content-classify",
        "classified": classified,
        "control": control,
        "live_untrusted_active_count": len(live_active),
        "live_untrusted_active": live_active,
    }
    OUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    art_err = check_artifact(control, len(live_active))
    if art_err:
        return fail(art_err)
    print(
        json.dumps(
            {
                "both_states_on_one_fixture": True,
                "inert_agents": "inert",
                "active_agents": "active",
                "inert_claude": "inert",
                "filename_only_mutant_red": True,
                "live_untrusted_active_count": len(live_active),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:{UID}-probe2 classifier inert+active on one fixture; "
        f"live_untrusted_active={len(live_active)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
