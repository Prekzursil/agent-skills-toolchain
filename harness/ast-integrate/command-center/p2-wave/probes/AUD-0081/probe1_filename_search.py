#!/usr/bin/env python3
"""Probe 1: filename search for the auto-load set in non-owner-authored trees.

Does not read file bodies. A hit is a name match (.claude, .codex, .mcp.json,
hooks, AGENTS.md, CLAUDE.md) under a cloned, vendored, agent-scratch, or planted
control tree. Finding CLAUDE.md is recorded; whether it is a risk is Probe 2.
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
OUT = HERE / "probe1-filename-search.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe1 {msg}")
    return 1


def _report(doc: dict) -> dict:
    report = doc.get("report")
    return report if isinstance(report, dict) else {}


def check_artifact(hits: list[dict], control_present: bool) -> str | None:
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
    kind = str(
        doc.get("report_kind") or report.get("kind") or report.get("report_kind") or ""
    )
    if kind != "audit-finding":
        return "artifact report_kind is not audit-finding"
    census = doc.get("filename_census")
    if not isinstance(census, dict):
        census = report.get("filename_census") or {}
    if int(census.get("hit_count", -1)) != len(hits):
        return (
            f"artifact filename hit_count {census.get('hit_count')!r} "
            f"!= live {len(hits)}"
        )
    if census.get("planted_control_found") is not True:
        return "artifact did not record planted-control filename hits"
    if not control_present:
        return "live planted-control hits missing while artifact claims them"
    return None


def main() -> int:
    roots = A.untrusted_roots()
    hits = A.filename_hits(roots)
    fx = A.fixture_paths()
    by_path = {h["path"] for h in hits}
    required = [fx["inert_agents"], fx["active_agents"], fx["inert_claude"]]
    missing = [p for p in required if p not in by_path]
    if missing:
        return fail(f"planted autoload names not found {missing}")
    planted = [h for h in hits if h.get("planted_control")]
    if len(planted) < 3:
        return fail(f"planted hit count {len(planted)} < 3")
    git_roots = [r for r in roots if r["path"] == A.PLANTED_REL]
    if not git_roots:
        return fail("planted untrusted-clone was not an untrusted root")
    if not (REPO / fx["git_file"]).is_file():
        return fail("planted .git FILE missing (submodule-style clone marker)")

    payload = {
        "probe": "probe1-filename-search",
        "untrusted_root_count": len(roots),
        "hit_count": len(hits),
        "planted_hit_count": len(planted),
        "required_fixture_hits": required,
        "aud0009": A.aud0009_status(),
        "hits": hits,
        "roots": roots,
    }
    OUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    art_err = check_artifact(hits, control_present=True)
    if art_err:
        return fail(art_err)
    print(
        json.dumps(
            {
                "hit_count": len(hits),
                "planted_hit_count": len(planted),
                "untrusted_root_count": len(roots),
                "inert_agents_hit": fx["inert_agents"] in by_path,
                "active_agents_hit": fx["active_agents"] in by_path,
                "inert_claude_hit": fx["inert_claude"] in by_path,
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:{UID}-probe1 filename search hit_count={len(hits)} "
        f"planted={len(planted)} roots={len(roots)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
