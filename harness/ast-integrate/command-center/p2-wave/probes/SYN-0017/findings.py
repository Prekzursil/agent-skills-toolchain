"""Planted synthesis-finding corpus for SYN-0017.

SYN-0011's merged finding set is not on this worktree. The detector is proven
on a fixture corpus that includes the three required planted mutants, two
genuinely distinct findings, and one full rewrite of the same mechanism
(coverage disclosure). Live-input absence is recorded, not invented.
"""
from __future__ import annotations

BASE_ID = "F-MANIFEST-GATE"
RENAME_ID = "F-MANIFEST-GATE-RENAME"
PARAPHRASE_ID = "F-MANIFEST-GATE-PARAPHRASE"
FORK_ID = "F-MANIFEST-GATE-FORK"
DISTINCT_A_ID = "F-GIT-ARCHIVE-CRLF"
DISTINCT_B_ID = "F-DISSENT-DISPOSAL"
REWRITE_ID = "F-MANIFEST-GATE-REWRITE"

MECH_MANIFEST = "report-time-manifest-verification-gate"
MECH_CRLF = "blob-read-recipe-crlf"
MECH_DISSENT = "omitted-dissent-audit"

BASE_BODY = (
    "The final synthesis agent must verify the artifact manifest on disk "
    "before writing the completion report. Existence, non-empty, minimum "
    "size, schema parse and content hash are re-checked inside a five-minute "
    "freshness window."
)


def _f(
    fid: str,
    title: str,
    body: str,
    mechanism: str,
    anchors: list[str],
    role: str,
) -> dict:
    return {
        "id": fid,
        "title": title,
        "body": body,
        "canonical_mechanism": mechanism,
        "evidence_anchors": list(anchors),
        "role": role,
    }


def corpus() -> list[dict]:
    return [
        _f(
            BASE_ID,
            "Report-time artifact-manifest verification gate",
            BASE_BODY,
            MECH_MANIFEST,
            [
                "spec:_USER-PROMPTS.md:11098",
                "path:command-center/ARTIFACT-MANIFEST.json",
            ],
            "incumbent",
        ),
        _f(
            RENAME_ID,
            "Report-time artifact-manifest verification gate",
            BASE_BODY,
            MECH_MANIFEST,
            ["path:command-center/schema/"],
            "planted-rename",
        ),
        _f(
            PARAPHRASE_ID,
            "Gate that re-confirms listed artifacts still parse",
            (
                "Before the completion report is written, the final synthesis "
                "agent has to verify the artifact manifest on disk. The re-check "
                "covers existence, non-empty, minimum size, schema parse and "
                "content hash inside a five-minute freshness window."
            ),
            MECH_MANIFEST,
            ["unit:AUD-0036"],
            "planted-paraphrase",
        ),
        _f(
            FORK_ID,
            "Report-time artifact-manifest verification gate (fifteen-minute window)",
            (
                "The final synthesis agent must verify the artifact manifest on "
                "disk before writing the completion report. Existence, non-empty, "
                "minimum size, schema parse and content hash are re-checked "
                "inside a fifteen-minute freshness window."
            ),
            MECH_MANIFEST,
            ["note:freshness-window-15min"],
            "planted-parameter-fork",
        ),
        _f(
            DISTINCT_A_ID,
            "git archive returns CRLF worktree bytes",
            (
                "Read file bytes with git cat-file -p revision:path. Never use "
                "git archive, which on this box returns CRLF worktree bytes and "
                "corrupts the content-hash comparison."
            ),
            MECH_CRLF,
            ["spec:rules/common/windows-shell.md:8b"],
            "distinct-a",
        ),
        _f(
            DISTINCT_B_ID,
            "Unmatched dissent needs a written disposal reason",
            (
                "Enumerate the dissent population from council transcripts and "
                "require every unmatched dissent to carry an explicit disposal "
                "reason. Silently dropping a minority report is a named council "
                "failure class."
            ),
            MECH_DISSENT,
            [
                "spec:_USER-PROMPTS.md:11341",
                "path:command-center/council/",
            ],
            "distinct-b",
        ),
        _f(
            REWRITE_ID,
            "Do not emit SUCCESS until listed files still parse",
            (
                "A green reconciliation from yesterday does not authorise today's "
                "write. Fail closed when a listed path cannot be stat-ed, including "
                "Windows reserved device names that need the extended-length prefix."
            ),
            MECH_MANIFEST,
            ["note:fail-closed-reserved-names"],
            "full-rewrite-coverage-disclosure",
        ),
    ]


def finding_text(row: dict) -> str:
    return f"{row.get('title') or ''} {row.get('body') or ''}".strip()


def by_id(rows: list[dict] | None = None) -> dict[str, dict]:
    return {str(r["id"]): r for r in (rows if rows is not None else corpus())}
