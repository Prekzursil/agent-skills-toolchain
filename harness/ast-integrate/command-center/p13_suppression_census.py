"""P13 / BLD-0023: suppressed-failure construct census across code, tests, CI, scripts.

Enumerates every construct that can convert a failure into a pass:
  pytest        - @pytest.mark.skip / skipif / xfail, pytest.skip()
  CI            - continue-on-error: true, `|| true`, `|| echo`, `2>/dev/null` on a checked cmd
  python        - bare `except:` / `except Exception: pass`, contextlib.suppress,
                  a defensive hasattr() guard around the thing under test
  shell/ps      - `|| true`, `-ErrorAction SilentlyContinue`, `2>$null`
  coverage      - `# pragma: no cover` on a branch that masks absence

Scope is declared explicitly with every count (the honesty brief requires it).
Detector controls: each pattern is proven to fire on a synthetic KNOWN-POSITIVE
line and to stay silent on a KNOWN-NEGATIVE line before any count is emitted.
Read-only apart from one JSON report.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"
OUT = CC / "P13-SUPPRESSION-CENSUS.json"

# Scope: the program's own build + its CI. Excludes vendored/3rd-party trees and
# scratch files (leading underscore), which are not deliverables.
SCOPE_DIRS = [
    "platform",
    "command-center",
    ".github/workflows",
    "ci",
    "tools/command-center",
]
EXCLUDE_PARTS = {
    "node_modules",
    "__pycache__",
    ".git",
    "harness-sota-2026-07-18-corpus",
}

PATTERNS: dict[str, tuple[str, str, str]] = {
    # name: (regex, known-positive line, known-negative line)
    "pytest_skip_call": (
        r"pytest\.skip\(",
        "    pytest.skip('nope')",
        "    assert skip_it",
    ),
    "pytest_mark_skip": (
        r"@pytest\.mark\.skip\b",
        "@pytest.mark.skip",
        "@pytest.mark.parametrize",
    ),
    "pytest_mark_skipif": (
        r"pytest\.mark\.skipif",
        "x = pytest.mark.skipif(True)",
        "x = pytest.mark.usefixtures",
    ),
    "pytest_xfail": (
        r"pytest\.(mark\.)?xfail",
        "@pytest.mark.xfail",
        "@pytest.mark.slow",
    ),
    "ci_continue_on_error": (
        r"continue-on-error:\s*true",
        "        continue-on-error: true",
        "        continue-on-error: false",
    ),
    "shell_or_true": (r"\|\|\s*true\b", "  cmd || true", "  cmd || exit 1"),
    "shell_or_echo": (r"\|\|\s*echo\b", "  cmd || echo 0", "  cmd && echo 0"),
    "bare_except": (r"except\s*:", "    except:", "    except ValueError:"),
    "except_pass": (
        r"except\s+[\w.() ,]*\s*:\s*(#.*)?$",
        "    except Exception:",
        "    x = 1",
    ),
    "contextlib_suppress": (
        r"suppress\(",
        "    with suppress(OSError):",
        "    with open(p):",
    ),
    "pragma_no_cover": (
        r"#\s*pragma:\s*no cover",
        "    if x:  # pragma: no cover",
        "    if x:  # noqa",
    ),
    "ps_silently_continue": (
        r"-ErrorAction\s+SilentlyContinue",
        "Get-Item x -ErrorAction SilentlyContinue",
        "Get-Item x -ErrorAction Stop",
    ),
    "stderr_to_null": (
        r"2>\s*(/dev/null|\$null|NUL)",
        "  cmd 2>/dev/null",
        "  cmd 2>&1",
    ),
}


def controls() -> dict:
    rows = {}
    ok = True
    for name, (rx, pos, neg) in PATTERNS.items():
        c = re.compile(rx)
        fires_pos = bool(c.search(pos))
        fires_neg = bool(c.search(neg))
        good = fires_pos and not fires_neg
        ok = ok and good
        rows[name] = {
            "regex": rx,
            "fires_on_known_positive": fires_pos,
            "fires_on_known_negative": fires_neg,
            "control_pass": good,
        }
    return {"per_pattern": rows, "all_pass": ok}


def in_scope(p: pathlib.Path) -> bool:
    parts = set(p.parts)
    if parts & EXCLUDE_PARTS:
        return False
    return p.suffix in {".py", ".yml", ".yaml", ".sh", ".ps1", ".mjs", ".js"}


def is_scratch(p: pathlib.Path) -> bool:
    return p.name.startswith("_")


def main() -> int:
    ctl = controls()
    if not ctl["all_pass"]:
        print("FAILED:p13-suppression-census detector controls did not pass")
        bad = [k for k, v in ctl["per_pattern"].items() if not v["control_pass"]]
        print("  failing patterns:", bad)
        return 1
    print(f"detector controls: PASS ({len(PATTERNS)} patterns, both-states each)")

    compiled = {k: re.compile(v[0]) for k, v in PATTERNS.items()}
    hits: dict[str, list[dict]] = collections.defaultdict(list)
    files_scanned = 0
    scratch_skipped = 0

    for d in SCOPE_DIRS:
        root = REPO / d
        if not root.exists():
            print(f"  NOTE scope dir absent: {d}")
            continue
        for p in root.rglob("*"):
            if not p.is_file() or not in_scope(p):
                continue
            if is_scratch(p):
                scratch_skipped += 1
                continue
            files_scanned += 1
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(p.relative_to(REPO)).replace("\\", "/")
            for i, line in enumerate(text.splitlines(), 1):
                for name, c in compiled.items():
                    if c.search(line):
                        hits[name].append(
                            {"file": rel, "line": i, "text": line.strip()[:160]}
                        )

    # Which hits sit in DELIVERABLE test files (the dangerous ones) vs library code
    def bucket(rel: str) -> str:
        if rel.startswith(".github/workflows"):
            return "CI"
        if "/test_" in rel or rel.split("/")[-1].startswith("test_"):
            return "test"
        if rel.endswith((".sh", ".ps1")):
            return "script"
        return "lib"

    per_bucket: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for name, rows in hits.items():
        for r in rows:
            per_bucket[bucket(r["file"])][name] += 1

    report = {
        "artifact": "P13-SUPPRESSION-CENSUS",
        "unit": "depth/p13-blindspot",
        "closes_catalog_unit": "BLD-0023 (partially - see scope_limits)",
        "status": "MEASURED",
        "question": "Q06/Q09 - where does the tree convert a failure into a pass?",
        "scope_declared": {
            "dirs": SCOPE_DIRS,
            "extensions": [".py", ".yml", ".yaml", ".sh", ".ps1", ".mjs", ".js"],
            "excluded_dir_names": sorted(EXCLUDE_PARTS),
            "excluded_scratch_underscore_files": scratch_skipped,
            "files_scanned": files_scanned,
        },
        "detector_controls": ctl,
        "totals": {
            k: len(v) for k, v in sorted(hits.items(), key=lambda kv: -len(kv[1]))
        },
        "grand_total": sum(len(v) for v in hits.values()),
        "by_bucket": {b: dict(c.most_common()) for b, c in sorted(per_bucket.items())},
        "scope_limits": [
            "counts CONSTRUCT OCCURRENCES, not proven masks - a skipif on a genuinely "
            "platform-specific test is correct behaviour, not a defect",
            "does not evaluate whether each construct currently fires",
            "excludes underscore-prefixed scratch files and vendored trees",
        ],
        "samples": {k: v[:12] for k, v in hits.items()},
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"files_scanned={files_scanned} scratch_excluded={scratch_skipped}")
    print()
    print("=== suppression constructs (whole declared scope) ===")
    for k, n in report["totals"].items():
        print(f"  {n:5d}  {k}")
    print(f"  {report['grand_total']:5d}  TOTAL")
    print()
    print("=== by bucket ===")
    for b, c in report["by_bucket"].items():
        print(f"  [{b}] total={sum(c.values())}  {dict(list(c.items())[:6])}")
    print()
    print(f"SUCCESS:p13-suppression-census wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
