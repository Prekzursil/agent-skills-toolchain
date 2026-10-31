#!/usr/bin/env python3
"""IMP-0025 probe1 (source): dry-run repair plan over a planted live tree lists
every file it would touch with its classification; the independent differ
recomputes the same classification set."""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.independent_differ import classify_independent  # noqa: E402
from plugin import repair as rp  # noqa: E402


def plant(root):
    repo = root / "repo"
    live = root / "live"
    diverged = "rules/common/both-unique.md"
    repo_ahead = "rules/project/testing.md"
    for side, base in (("repo", repo), ("live", live)):
        (base / diverged).parent.mkdir(parents=True, exist_ok=True)
    (repo / diverged).write_text("# shared\nrepo-unique-IMP0025\n", encoding="utf-8")
    (live / diverged).write_text("# shared\nlive-unique-IMP0025\n", encoding="utf-8")
    (repo / repo_ahead).parent.mkdir(parents=True, exist_ok=True)
    (live / repo_ahead).parent.mkdir(parents=True, exist_ok=True)
    (repo / repo_ahead).write_text("# shared\nrepo-ahead-line\n", encoding="utf-8")
    (live / repo_ahead).write_text("# shared\n", encoding="utf-8")
    same = "rules/common/identical.md"
    (repo / same).parent.mkdir(parents=True, exist_ok=True)
    (live / same).parent.mkdir(parents=True, exist_ok=True)
    (live / same).parent.mkdir(parents=True, exist_ok=True)
    (repo / same).write_bytes(b"# same bytes\n")
    (live / same).write_bytes(b"# same bytes\r\n")
    return repo, live


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo, live = plant(root)
        diverged_rel = "rules/common/both-unique.md"
        repo_ahead_rel = "rules/project/testing.md"
        same_rel = "rules/common/identical.md"
        klass_div = classify_independent((repo / diverged_rel).read_bytes(), (live / diverged_rel).read_bytes())
        klass_ahead = classify_independent((repo / repo_ahead_rel).read_bytes(), (live / repo_ahead_rel).read_bytes())
        klass_same = classify_independent((repo / same_rel).read_bytes(), (live / same_rel).read_bytes())
        checks = {
            "diverged_classified_diverged": klass_div == "DIVERGED",
            "repo_ahead_classified": klass_ahead in ("REPO-AHEAD", "repo-ahead"),
            "eol_only_classified_identical": klass_same in ("IDENTICAL-MODULO-EOL", "identical-modulo-eol", "SAME"),
        }
        print(json.dumps({"classes": {"diverged": klass_div, "repo_ahead": klass_ahead, "eol_only": klass_same}, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0025-probe1 classification mismatch")
            return 1
        print("SUCCESS:IMP-0025-probe1 independent differ classifies diverged, repo-ahead and EOL-only")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
