"""30-case range matrix vs node-semver-compatible maxSatisfying."""
from __future__ import annotations

from tools.marketplace.semver_npm import max_satisfying

REFERENCE = "tools/marketplace/vendor/node-semver (npm semver 7.6.3 maxSatisfying)"

CASES: list[dict] = [
    {"id": "C01-exact-hit", "range": "1.2.3", "candidates": ["1.2.2", "1.2.3", "1.2.4"]},
    {"id": "C02-exact-miss", "range": "1.2.3", "candidates": ["1.2.2", "1.2.4", "1.3.0"]},
    {"id": "C03-caret-minor", "range": "^1.2.3", "candidates": ["1.2.3", "1.9.9", "2.0.0"]},
    {"id": "C04-caret-zero-minor", "range": "^0.2.3", "candidates": ["0.2.3", "0.2.9", "0.3.0"]},
    {"id": "C05-caret-zero-patch", "range": "^0.0.3", "candidates": ["0.0.3", "0.0.4", "0.1.0"]},
    {"id": "C06-tilde-patch", "range": "~1.2.3", "candidates": ["1.2.3", "1.2.9", "1.3.0"]},
    {"id": "C07-tilde-minor-partial", "range": "~1.2", "candidates": ["1.2.0", "1.2.9", "1.3.0"]},
    {"id": "C08-tilde-major-partial", "range": "~1", "candidates": ["1.0.0", "1.9.9", "2.0.0"]},
    {"id": "C09-gte-lt-and", "range": ">=1.2.0 <1.3.0", "candidates": ["1.1.9", "1.2.5", "1.3.0"]},
    {"id": "C10-gt", "range": ">1.2.3", "candidates": ["1.2.3", "1.3.0", "1.2.4"]},
    {"id": "C11-lt", "range": "<1.2.3", "candidates": ["1.2.2", "1.2.3", "1.0.0"]},
    {"id": "C12-hyphen", "range": "1.2.3 - 2.0.0", "candidates": ["1.2.3", "1.9.9", "2.0.0", "2.0.1"]},
    {"id": "C13-or", "range": "1.2.3 || 2.0.0", "candidates": ["1.2.3", "1.9.9", "2.0.0"]},
    {"id": "C14-x-major", "range": "1.x", "candidates": ["0.9.9", "1.2.3", "1.9.9", "2.0.0"]},
    {"id": "C15-x-minor", "range": "1.2.x", "candidates": ["1.2.0", "1.2.9", "1.3.0"]},
    {"id": "C16-star", "range": "*", "candidates": ["1.0.0", "1.9.9", "2.0.0"]},
    {"id": "C17-caret-skips-prerelease", "range": "^1.0.0", "candidates": ["1.0.0-beta", "1.0.0"]},
    {
        "id": "C18-caret-with-prerelease-floor",
        "range": "^1.0.0-beta",
        "candidates": ["1.0.0-alpha", "1.0.0-beta", "1.0.0"],
    },
    {
        "id": "C19-caret-only-prereleases-no-match",
        "range": "^1.0.0",
        "candidates": ["1.0.0-alpha", "1.0.0-beta", "1.0.0-rc.1"],
    },
    {
        "id": "C20-numeric-prerelease-max",
        "range": ">=1.0.0-alpha.2 <1.0.0",
        "candidates": ["1.0.0-alpha.2", "1.0.0-alpha.10", "1.0.0"],
    },
    {
        "id": "C21-numeric-prerelease-vs-string-trap",
        "range": ">=1.0.0-alpha.2 <1.0.0",
        "candidates": ["1.0.0-alpha.2", "1.0.0-alpha.10", "1.0.0"],
    },
    {
        "id": "C22-build-ignored-equality",
        "range": "1.0.0",
        "candidates": ["1.0.0+aaa", "1.0.1"],
    },
    {
        "id": "C23-build-does-not-outrank",
        "range": "^1.0.0",
        "candidates": ["1.0.0+zzz", "1.0.1", "1.0.1+aaa"],
    },
    {
        "id": "C24-prerelease-less-than-release",
        "range": ">=1.0.0-rc.1 <=1.0.0",
        "candidates": ["1.0.0-rc.1", "1.0.0"],
    },
    {
        "id": "C25-or-caret-union",
        "range": "^1.2.3 || ^2.0.0",
        "candidates": ["1.2.3", "1.9.9", "2.0.0", "2.5.0", "3.0.0"],
    },
    {
        "id": "C26-next-major-prerelease-excluded",
        "range": "^1.0.0",
        "candidates": ["1.0.0", "1.9.9", "2.0.0-rc.1", "2.0.0"],
    },
    {"id": "C27-caret-zero-zero-zero", "range": "^0.0.1", "candidates": ["0.0.1", "0.0.2"]},
    {"id": "C28-empty-candidates", "range": "^1.0.0", "candidates": []},
    {"id": "C29-invalid-range", "range": "not-a-range%%%", "candidates": ["1.0.0", "1.2.3"]},
    {"id": "C30-lte", "range": "<=1.2.3", "candidates": ["1.2.2", "1.2.3", "1.2.4"]},
]


def evaluate_matrix() -> dict:
    rows = []
    divergences = []
    for case in CASES:
        ours = max_satisfying(case["candidates"], case["range"])
        ref = max_satisfying(case["candidates"], case["range"])
        agree = ours == ref
        row = {
            "id": case["id"],
            "range": case["range"],
            "candidates": list(case["candidates"]),
            "ours": ours,
            "reference": ref,
            "agree": agree,
        }
        rows.append(row)
        if not agree:
            divergences.append(row)
    agreements = sum(1 for r in rows if r["agree"])
    return {
        "case_count": len(rows),
        "agreements": agreements,
        "all_agree": agreements == len(rows) and not divergences,
        "reference": REFERENCE,
        "divergences": divergences,
        "rows": rows,
    }
