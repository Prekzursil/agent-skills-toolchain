#!/usr/bin/env python3
"""Probe 2: independent regex re-extraction + overclaim check on the live receipt.

Mechanically different from extract.py (AST): this probe uses regex over
add_argument(...) and markdown. It must agree with the fixture planted
defects and must refuse a receipt that claims live empty diffs when they
are not empty.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RECEIPT = REPO / "command-center" / "receipts" / "TST-0112.json"
MISMATCH_DOCS = HERE / "fixtures" / "mismatch" / "docs.md"
MISMATCH_PARSER = HERE / "fixtures" / "mismatch" / "parser.py"
ALIGNED_DOCS = HERE / "fixtures" / "aligned" / "docs.md"
ALIGNED_PARSER = HERE / "fixtures" / "aligned" / "parser.py"

ADD_ARGUMENT_FLAG = re.compile(
    r"""add_argument\(\s*(?:['"](--[A-Za-z0-9][A-Za-z0-9-]*)['"])"""
)
DOC_FLAG = re.compile(r"(?<![A-Za-z0-9-])(--[A-Za-z0-9][A-Za-z0-9-]*)(?![A-Za-z0-9-])")
MENTION = re.compile(r"(?i)removed in v\d|deprecated|do not use|must not count")


def flags_from_parser_regex(source: str) -> set[str]:
    return set(ADD_ARGUMENT_FLAG.findall(source))


def flags_from_docs_regex(text: str) -> tuple[set[str], set[str]]:
    live: set[str] = set()
    mentions: set[str] = set()
    for line in text.splitlines():
        found = set(DOC_FLAG.findall(line))
        if MENTION.search(line):
            mentions |= found
        else:
            live |= found
    return live, mentions - live


def main() -> int:
    m_docs = MISMATCH_DOCS.read_text(encoding="utf-8")
    m_parser = MISMATCH_PARSER.read_text(encoding="utf-8")
    a_docs = ALIGNED_DOCS.read_text(encoding="utf-8")
    a_parser = ALIGNED_PARSER.read_text(encoding="utf-8")

    m_doc, m_mentions = flags_from_docs_regex(m_docs)
    m_impl = flags_from_parser_regex(m_parser)
    a_doc, _ = flags_from_docs_regex(a_docs)
    a_impl = flags_from_parser_regex(a_parser)

    a_missing = sorted(a_doc - a_impl)
    a_extra = sorted(a_impl - a_doc)
    m_missing = sorted(m_doc - m_impl)
    m_extra = sorted(m_impl - m_doc)

    print(f"regex aligned missing={a_missing} extra={a_extra}")
    print(f"regex mismatch documented_not_parser={m_missing} parser_not_documented={m_extra}")
    print(f"regex mentions={sorted(m_mentions)}")

    if a_missing or a_extra:
        print("FAILED:TST-0112-probe2 aligned regex diffs not empty")
        return 1
    if "--ghost-flag" not in m_missing:
        print("FAILED:TST-0112-probe2 regex missed planted --ghost-flag")
        return 1
    if "--undocumented-real" not in m_extra:
        print("FAILED:TST-0112-probe2 regex missed planted --undocumented-real")
        return 1
    if m_missing == m_extra:
        print("FAILED:TST-0112-probe2 regex collapsed both-direction sets")
        return 1
    if "--legacy-removed" in m_doc:
        print("FAILED:TST-0112-probe2 regex counted removed-in-v2 mention")
        return 1
    if "--legacy-removed" not in m_mentions:
        print("FAILED:TST-0112-probe2 regex did not record mention")
        return 1

    if not RECEIPT.is_file():
        print("FAILED:TST-0112-probe2 receipt missing")
        return 1
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0112-probe2 receipt self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0112" not in RECEIPT.read_text(encoding="utf-8"):
        print("FAILED:TST-0112-probe2 sentinel absent")
        return 1

    live = ((doc.get("differences") or {}).get("live") or {})
    live_flags = live.get("flags") or {}
    claimed_missing = int(live_flags.get("documented_not_implemented_count") or 0)
    claimed_extra = int(live_flags.get("implemented_not_documented_count") or 0)
    listed_missing = live_flags.get("documented_not_implemented") or []
    listed_extra = live_flags.get("implemented_not_documented") or []
    if len(listed_missing) != claimed_missing or len(listed_extra) != claimed_extra:
        print("FAILED:TST-0112-probe2 live flag counts disagree with lists")
        return 1

    # Independent live parser regex over the declared parser files.
    live_impl: set[str] = set()
    for rel in (doc.get("scope") or {}).get("parser_paths") or []:
        path = REPO / rel
        if path.is_file():
            live_impl |= flags_from_parser_regex(path.read_text(encoding="utf-8"))
    live_doc: set[str] = set()
    for rel in (doc.get("scope") or {}).get("doc_paths") or []:
        path = REPO / rel
        if path.is_file():
            flags, _ment = flags_from_docs_regex(path.read_text(encoding="utf-8"))
            live_doc |= flags
    indep_missing = sorted(live_doc - live_impl)
    indep_extra = sorted(live_impl - live_doc)
    print(
        f"regex live documented={len(live_doc)} parser={len(live_impl)} "
        f"doc_not_parser={len(indep_missing)} parser_not_doc={len(indep_extra)}"
    )
    if claimed_missing == 0 and claimed_extra == 0:
        if indep_missing or indep_extra:
            print(
                "FAILED:TST-0112-probe2 overclaim: receipt claims live flag "
                f"parity but regex finds missing={indep_missing[:8]} extra={indep_extra[:8]}"
            )
            return 1
    # Receipt lists must be a subset of the regex view (AST may drop shorts; regex is long-only).
    extra_listed = set(listed_extra)
    if extra_listed - live_impl:
        print(
            "FAILED:TST-0112-probe2 receipt lists undocumented flags regex did not see "
            f"{sorted(extra_listed - live_impl)[:8]}"
        )
        return 1

    tests = doc.get("tests") or []
    if any(t.get("result") != "PASS" for t in tests if isinstance(t, dict)):
        print("FAILED:TST-0112-probe2 receipt tests not all PASS")
        return 1
    print("independent=regex-add_argument reviewer=probe2 overclaim=checked")
    print("SUCCESS:TST-0112-probe2 independent regex and live overclaim check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
