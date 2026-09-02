"""Shared paths for CNF-0038. Repo root is the worktree that holds the catalog."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_repo(start: Path = HERE) -> Path:
    for p in [start, *start.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise SystemExit("FAILED:CNF-0038 repo root with WORK-UNIT-CATALOG.json not found")


REPO = find_repo()
UNIT = "CNF-0038"
FIXTURES = HERE / "fixtures"
GENERATED = HERE / "generated"
BRIEF_PATH = GENERATED / "brief.json"
SYNTH_TEST = GENERATED / "test_independent.py"
ACCESS_LOG = GENERATED / "access-log.json"
OUT_REL = "command-center/confirmation/CNF-0038-blind-test-synthesis.json"
SCHEMA_REL = "command-center/schema/blind-test-report.schema.json"
OUT_PATH = REPO / OUT_REL
SCHEMA_PATH = REPO / SCHEMA_REL
REQUIREMENT = FIXTURES / "requirement.md"
PUBLIC_API = FIXTURES / "public_api.py"
AUTHOR_TEST = FIXTURES / "author_test.py"
DIFF_PATCH = FIXTURES / "diff.patch"
IMPLEMENTER_NOTES = FIXTURES / "implementer_notes.md"
PRE_FIX = FIXTURES / "pre-fix"
POST_FIX = FIXTURES / "post-fix"
OVERFITTED = FIXTURES / "overfitted"
ALREADY = FIXTURES / "already-satisfied"
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0038 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the synthesised test was "
    "executed at both commits and both outcomes are recorded verbatim. Any other "
    "terminal state is FAILED:CNF-0038 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Would a fresh agent, reading only the requirement and the public API and never "
    "the author test, write a test that fails before the fix and passes after? Do "
    "exactly that and answer: does the independently derived test agree with the "
    "author test, and where it disagrees, which one matches the requirement text?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0038/probe1_leak_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0038/probe2_red_green.py"
)
AUTHOR_MARKER = "AUTHOR_TEST_UNIQUE_MARKER_CNF0038"
DIFF_MARKER = "DIFF_UNIQUE_MARKER_CNF0038"
CONCLUSION_MARKER = "IMPLEMENTER_CONCLUSION:"
FORBIDDEN_NAMES = frozenset(
    {
        "author_test.py",
        "diff.patch",
        "implementer_notes.md",
    }
)
FORBIDDEN_DIR_PARTS = frozenset(
    {"pre-fix", "post-fix", "overfitted", "already-satisfied"}
)
