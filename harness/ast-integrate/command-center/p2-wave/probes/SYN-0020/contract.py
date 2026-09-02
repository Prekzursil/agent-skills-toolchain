"""SYN-0020 shared contract constants."""

from __future__ import annotations

UNIT_ID = "SYN-0020"
OUT_REL = "command-center/synthesis/SYN-0020.docs-code-parity.json"
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
LIVE_CHECKLIST = "command-center/RELEASE-CHECKLIST.md"
SENTINEL = "SUCCESS:SYN-0020"
COMPLETION_SENTINEL = (
    "SUCCESS:SYN-0020 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the known-present control "
    "fired and no statement is silently classed AGREE without a test id. Any "
    "other terminal state is FAILED:SYN-0020 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Which documented commands fail to run, and which documented behaviours "
    "contradict measured behaviour? Extract every fenced command from the "
    "shipped docs, run it in a clean shell, and separately diff prose "
    "behaviour statements against test results. The known live instance is "
    "RELEASE-CHECKLIST.md prescribing verification against the LF blob "
    "(git archive), which returns CRLF on the Windows box this recipe was "
    "written for."
)
KNOWN_PRESENT_SNIPPET = "against the LF blob (git archive)"
KNOWN_PRESENT_FIXTURE = (
    "command-center/p2-wave/probes/SYN-0020/fixtures/"
    "known-present-git-archive.md"
)
MENTION_ONLY_FIXTURE = (
    "command-center/p2-wave/probes/SYN-0020/fixtures/mention-only.md"
)
NEGATED_MENTION = (
    "Never use git archive to read stored bytes; cat-file returns the blob."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0020/probe1_known_present_and_noexec.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0020/probe2_untested_not_agree.py"
)
EXPECTED_LIVE_DOCS = (
    "command-center/RELEASE-CHECKLIST.md",
    "command-center/RUNBOOK.md",
    "README.md",
    "command-center/README.md",
)
NOEXEC_TOKENS = frozenset(
    {"noexec", "not-executable", "illustrative", "mention"}
)
UNSAFE_RE = (
    r"(?:^|[;&|]\s*)(?:rm\s+|rmdir\s+|dd\s+|mkfs\s+|sudo\s+|reboot\b|"
    r"shutdown\b|git\s+(?:add|commit|push|reset|rebase|stash|checkout|clone)\b|"
    r"git-crypt\b|npm\s+install\b|pip(?:3)?\s+install\b|uvx\b|claude\b|"
    r"curl\s+[^\n]*\|\s*(?:ba)?sh|wget\s+[^\n]*\|\s*(?:ba)?sh)"
)


def domain(doc: dict) -> dict:
    """Read SYN-0020 domain fields from report (receipt_core) or top-level."""
    if not isinstance(doc, dict):
        return {}
    rep = doc.get("report")
    if isinstance(rep, dict) and (
        "fingerprint" in rep or "known_present_control" in rep
    ):
        return rep
    return doc
