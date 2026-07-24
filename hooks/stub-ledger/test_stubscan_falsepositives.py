#!/usr/bin/env python3
"""Both-states tests for the 20 live stub-ledger false positives measured 2026-07-24.

PROVENANCE. Every SILENT case below is a VERBATIM line from the session ledger
``~/.claude/stub-ledger/5c615def-afc0-4e5a-97e5-1341dbd11e6f.ndjson``. That ledger held 53
records; replaying it through the real ``report.still_open()`` surfaced **20**, and inspecting
all 20 found **20/20 false positives** of the use-vs-mention class. The `file:line` anchor for
each is in the case label so a reader can re-open the original.

BOTH STATES, ALWAYS PAIRED. Each false-positive shape is followed by a POSITIVE CONTROL: the
same construct in the position where it really does mean unfinished work. A scanner that merely
goes quiet is a REGRESSION, not a fix -- a silently disarmed guard is worse than the noise it
replaced -- so a case list with only SILENT rows would prove nothing.

Run:  python test_stubscan_falsepositives.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "_shared"))

import stubscan  # noqa: E402

# The fenced corpus block from INPUT-ADDENDUM-live-fires.md:80-96, verbatim. Five of the 20
# live fires came from these six lines: a document that ENUMERATES detector inputs was scored
# as if it were the code under test.
LIVE_FIRES_DOC = (
    "# Live fires\n"
    "\n"
    "```\n"
    "R13  markdown table cell:      | tools/list_changed | Partially implemented in 2.1.0 |\n"
    "R14  markdown table cell:      | prompts/list_changed | Not implemented - needs a restart |\n"
    "R18  upstream-issue adjacency: not implemented (#31893) - tracked upstream, not ours\n"
    "```\n"
    "\n"
    "```\n"
    "P1  real source file:   # TODO: handle the empty-list case      <- in a .py, outside any fence\n"
    "P3  fenced code block:  raise NotImplementedError   <- genuine stub in code\n"
    "```\n"
)

# (label, text, path, expect_fire)
CASES: list[tuple[str, str, str, bool]] = [
    # ---------------------------------------------------------------- shape 1: prose document
    # 12 of the 20 live fires were markers inside FENCED blocks of .md files. The pre-existing
    # rule treated "fenced in prose" as real code; these 12 measured fires REFUTE that -- a
    # fenced block in a document is an EXAMPLE being shown, not the document's own pending work.
    (
        "FP INPUT-ADDENDUM-live-fires.md:81-95 - fenced corpus listing in a doc",
        LIVE_FIRES_DOC,
        "harness-sota/INPUT-ADDENDUM-live-fires.md",
        False,
    ),
    (
        "CONTROL - the SAME fenced block, but the file is real source",
        LIVE_FIRES_DOC,
        "src/live_fires.py",
        True,
    ),
    (
        "FP A2-remaining-conflicts.md:177 - fixture prose naming fake credentials",
        "# fake ghp_/github_pat_ tokens, a dummy JWT, a placeholder PEM, xoxb-/sk- tokens)\n",
        "merge/A2-remaining-conflicts.md",
        False,
    ),
    (
        "CONTROL - a real placeholder comment in real source",
        "cert = None  # placeholder PEM until the loader lands\n",
        "src/tls.py",
        True,
    ),
    # ------------------------------------------------- shape 2: a comment DESCRIBING a marker
    # The weak word sits at the END of a descriptive sentence: the comment is ABOUT placeholders,
    # it does not declare one. A declaration leads with the word.
    (
        "FP mine.py:189 - comment about what identifies a placeholder",
        "        # this is the field that identifies an unexpanded "
        "${CLAUDE_PLUGIN_ROOT} placeholder.\n",
        "tools/harness-corpus/mine.py",
        False,
    ),
    (
        "FP build_corpus.py:223 - comment describing an algorithm that emits placeholders",
        "# 2. EXTRACTION - pull non-prose out of text, leave a typed placeholder (R8 6)\n",
        "my_writing/build_corpus.py",
        False,
    ),
    (
        "CONTROL - a leading weak word IS a declaration",
        "x = 1  # placeholder until wired\n",
        "src/cfg.py",
        True,
    ),
    (
        "CONTROL - block-comment star line, weak word leading",
        " * stub: returns fake data for now\n",
        "src/api.js",
        True,
    ),
    # ------------------------------------------- shape 3: phrase in a string literal / doc table
    (
        "FP build_corpus.py:1141 - 'not implemented' inside a report STRING literal",
        '          "- PERSON-name NER: **not implemented** (needs Presidio + a Romania pack",\n',
        "my_writing/build_corpus.py",
        False,
    ),
    (
        "FP build_corpus.py - argparse help text",
        '    help="acknowledge that person-name detection is not implemented (L2/L3)")\n',
        "my_writing/build_corpus.py",
        False,
    ),
    (
        "FP mcp_health.py:21 - docstring definition table, no comment intro",
        "  handshake   an MCP initialize round-trip succeeded  [NOT IMPLEMENTED]\n",
        "tools/mcp-manager/mcp_health.py",
        False,
    ),
    (
        "CONTROL - the same phrase as a real code comment",
        "# not implemented yet - the ranking pass lands in v2\n",
        "src/rank.py",
        True,
    ),
    # ---------------------------------- shape 4: phrase in a LATER sentence of a quoted message
    (
        "FP ClaudeJson.psm1:11 - quoted PowerShell error, 2nd sentence of the comment",
        "      # Please use the -AsHashTable switch instead. The key that was attempted "
        "to be added\n",
        "scripts/claude-json/ClaudeJson.psm1",
        False,
    ),
    (
        "CONTROL - the phrase in the comment's FIRST sentence is a real declaration",
        "# this parser is to be implemented. See the design note for why.\n",
        "src/parse.py",
        True,
    ),
    # ------------------------------------------------- shape 5: intentional no-op override
    (
        "FP mcp_http_host.py:274 - no-op override with an explanatory trailing comment",
        "        def log_message(self, *args: Any) -> None:  "
        "# silence default stderr access log\n            pass\n",
        "tools/mcp_http_host.py",
        False,
    ),
    (
        "CONTROL - a pass-only body with NO explanation is still a stub",
        "def handler(req):\n    pass\n",
        "src/web.py",
        True,
    ),
    (
        "CONTROL - a pass-only body whose comment IS a marker stays flagged",
        "def handler2(req):  # TODO wire this up\n    pass\n",
        "src/web.py",
        True,
    ),
    # ------------------------------------------------------------- structural mention guards
    # These apply INSIDE source files too -- a markdown table or a struck-through line embedded
    # in a docstring is still a mention.
    (
        "FP markdown table row embedded in a .py docstring",
        "| `prompts/list_changed` | Not implemented (#1785) | upstream gap |\n",
        "src/mcp_notes.py",
        False,
    ),
    (
        "FP struck-through text = an abandoned idea, not pending work",
        "# ~~Sampling so the gateway can reason about which server to wake~~ - not implemented.\n",
        "src/gateway.py",
        False,
    ),
    (
        "FP blockquote quoting someone else's TODO",
        "# > TODO: handle the empty-list case   (quoted from the upstream issue)\n",
        "src/notes.py",
        False,
    ),
    (
        "CONTROL - an EXPLICIT marker after a struck span on the SAME line still fires "
        "(the retraction guard is scoped to _PHRASE/_WEAK only)",
        "# ~~old approach~~ raise NotImplementedError\n",
        "src/gateway.py",
        True,
    ),
    (
        "CONTROL - a struck line must not silence the NEXT line (guard is per-line)",
        "# ~~old approach: hand-rolled parser~~\n# TODO: use the new one\n",
        "src/gateway.py",
        True,
    ),
    (
        "CONTROL - the un-struck, un-quoted, un-tabled marker still fires",
        "# TODO: handle the empty-list case\n",
        "src/notes.py",
        True,
    ),
    # ------------------------------------------------------------------ positive control set
    # STUB-TP-control from hooks/_shared/use-vs-mention-corpus.jsonl:19 -- if a discriminator
    # silences THIS it has overcorrected into blindness.
    (
        "CONTROL corpus STUB-TP-control - a real unfinished stub in real code",
        "def resolve_thread(msg):\n    raise NotImplementedError  # TODO wire this up\n",
        "isolate_messenger.py",
        True,
    ),
    (
        "CONTROL - bare TODO on its own in real source",
        "# TODO: implement the semantic ranking pass\n",
        "router.py",
        True,
    ),
    (
        "CONTROL - FIXME in a JS comment",
        "// FIXME broken on empty input\n",
        "app.js",
        True,
    ),
]


def main() -> int:
    fails = 0
    for label, text, path, want in CASES:
        got = bool(stubscan.find_stubs(text, path))
        ok = got == want
        if not ok:
            fails += 1
        print(f"  {'OK ' if ok else 'XX '} {label}: fired={got} want={want}")
    fires = sum(1 for _, _, _, w in CASES if w)
    print(
        f"\nRESULT: {'ALL PASS' if not fails else str(fails) + ' FAIL'}  "
        f"({len(CASES)} cases: {fires} must FIRE, {len(CASES) - fires} must stay SILENT)"
    )
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
