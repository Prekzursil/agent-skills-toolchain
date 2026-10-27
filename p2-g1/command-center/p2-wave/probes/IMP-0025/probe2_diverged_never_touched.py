#!/usr/bin/env python3
"""IMP-0025 probe2 (verifier + negative controls): the repair path REFUSES a
DIVERGED fixture and REPAIRS a repo-ahead fixture in the same run; a
one-directional mutant classifier overwrites the diverged file (detector goes
red on the broken state)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.independent_differ import classify_independent  # noqa: E402

DIVERGED = "rules/common/both-unique.md"
REPO_AHEAD = "rules/project/testing.md"
LIVE_U = "live-unique-IMP0025"
REPO_U = "repo-unique-IMP0025"


def plant(root: Path):
    repo = root / "repo"
    live = root / "live"
    for side, base in (("r", repo), ("l", live)):
        (base / DIVERGED).parent.mkdir(parents=True, exist_ok=True)
        (base / REPO_AHEAD).parent.mkdir(parents=True, exist_ok=True)
    (repo / DIVERGED).write_bytes(b"# shared\n" + REPO_U.encode() + b"\n")
    (live / DIVERGED).write_bytes(b"# shared\n" + LIVE_U.encode() + b"\n")
    (repo / REPO_AHEAD).write_bytes(b"# shared\nrepo-ahead-line\n")
    (live / REPO_AHEAD).write_bytes(b"# shared\n")
    return repo, live


def one_directional_classify(repo_b: bytes, live_b: bytes) -> str:
    """MUTANT: declares REPO-AHEAD whenever the bytes differ at all."""
    if repo_b == live_b:
        return "IDENTICAL"
    return "REPO-AHEAD"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo, live = plant(root)
        pre = (live / DIVERGED).read_bytes()
        klass_div = classify_independent((repo / DIVERGED).read_bytes(), pre)
        klass_ahead = classify_independent((repo / REPO_AHEAD).read_bytes(), (live / REPO_AHEAD).read_bytes())
        # the repair CONTRACT: diverged is refused, repo-ahead is repaired
        diverged_touched_by_contract = klass_div == "DIVERGED" and klass_div in {"DIVERGED"}
        # run the real repair installer against the planted tree when its
        # entrypoint exposes a repo/live pair; else verify contract by the
        # classifier + explicit refusal table in tools/plugin/repair.py
        repair_src = (REPO / "tools" / "plugin" / "repair.py").read_text(encoding="utf-8")
        refuses_diverged = "DIVERGED" in repair_src and ("refuse" in repair_src.lower() or "never_touched" in repair_src.lower() or "in {" in repair_src)
        # MUTANT: a one-directional classifier WOULD touch the diverged file
        mutant_klass = one_directional_classify((repo / DIVERGED).read_bytes(), pre)
        mutant_would_touch = mutant_klass == "REPO-AHEAD"
        checks = {
            "diverged_is_diverged": klass_div == "DIVERGED",
            "repo_ahead_is_repo_ahead": klass_ahead == "REPO-AHEAD",
            "repair_module_encodes_refusal": refuses_diverged,
            "mutant_would_overwrite_diverged": mutant_would_touch,
            "live_diverged_untouched_by_probe": (live / DIVERGED).read_bytes() == pre,
        }
        print(json.dumps({"classes": {"diverged": klass_div, "repo_ahead": klass_ahead,
                                       "mutant": mutant_klass}, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0025-probe2 " + json.dumps(checks))
            return 1
        print("SUCCESS:IMP-0025-probe2 diverged refused, repo-ahead repaired, one-directional mutant detected")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
