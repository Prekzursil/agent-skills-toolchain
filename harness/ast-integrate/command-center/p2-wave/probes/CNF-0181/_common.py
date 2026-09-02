"""Constants for CNF-0181: one retained self-improvement and its benchmark case.

The subject is a URL joiner. Baseline concatenates with a raw slash and produces
a triple-slash on (base-with-trailing-slash, path-with-leading-slash). The
retained improvement collapses those slashes. The original public suite never
included that input, so the failure is invisible until case.cnf0181.double-slash
is written back.
"""
from __future__ import annotations

CASE_ID = "case.cnf0181.double-slash"
IMPROVEMENT_ID = "SI-CNF-0181-001"

BASELINE_SRC = '''\
def join_url(base: str, path: str) -> str:
    """Baseline: naive slash concat. Double-slash inputs become triple-slash."""
    return base + "/" + path
'''

IMPROVED_SRC = '''\
def join_url(base: str, path: str) -> str:
    """Retained fix: collapse the join boundary to a single slash."""
    return base.rstrip("/") + "/" + path.lstrip("/")
'''

NEUTRAL_SRC = '''\
def join_url(base: str, path: str) -> str:
    """Retained fix: collapse the join boundary to a single slash."""
    # CNF-0181 neutral marker: comment-only, no behaviour change.
    return base.rstrip("/") + "/" + path.lstrip("/")
'''

# Public suite BEFORE write-back: both trees pass. The original failure is
# not represented, so a KEEP without a new case would be silent-returnable.
ORIGINAL_CASES = [
    {
        "id": "case.slash.join.plain",
        "base": "https://ex.com",
        "path": "api",
        "want": "https://ex.com/api",
    }
]

NEW_CASE = {
    "id": CASE_ID,
    "base": "https://ex.com/",
    "path": "/api",
    "want": "https://ex.com/api",
}

MEASURE_CASES = ORIGINAL_CASES + [NEW_CASE]
PUBLIC_AFTER = ORIGINAL_CASES + [NEW_CASE]

BASELINE_NEW_GOT = "https://ex.com///api"
IMPROVED_NEW_GOT = "https://ex.com/api"
