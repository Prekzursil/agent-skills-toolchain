"""Pinned live-URL shapes and receipt paths for RES-0004."""
from __future__ import annotations

ARTIFACT_REL = "command-center/research/RES-0004.json"
STORE_REL = "command-center/research/RES-0004-store"
COMPLETION_SENTINEL = (
    "SUCCESS:RES-0004 in the receipt AND a snapshot store exists whose every entry re-hashes "
    "to its recorded sha256 in a fresh process"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0004/probe1_recheck_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0004/probe2_redirect_rehash.py"
)
EVIDENCE_TARGETS = [
    {
        "id": "redirect-docs-claude",
        "shape": "redirect-chain",
        "url": "https://docs.claude.com/en/docs/claude-code",
        "expect_final_host_contains": "code.claude.com",
        "expect_redirect_status": 301,
    },
    {
        "id": "js-rendered-claude-code",
        "shape": "js-rendered",
        "url": "https://code.claude.com/",
        "expect_js_marker": "/_next/static/",
    },
    {
        "id": "raw-robots",
        "shape": "raw-file",
        "url": "https://code.claude.com/robots.txt",
        "expect_content_type_contains": "text/plain",
    },
]
