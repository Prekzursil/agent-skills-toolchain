"""Enumerate the agent-self/config <-> repo-root deploy-twin surface, with controls.

Round-3 BUILD probe. Independent re-derivation of grounding-round-2's G1: it does
NOT import or re-run `_g2_twindrift.py`; it enumerates from `git ls-files` and
compares universal-newline text, which is the exact comparison the shipped guard
`ci/tests/test_deployed_hook_twin_parity.py` performs.

Emits, for every DIFFERING pair, a truncated unified diff so each KNOWN_DIVERGENT
entry can carry an honest, specific reason rather than a generic one.

Run:  python command-center/slop-report/_r3_twinsurface.py
"""

from __future__ import annotations

import difflib
import json
import subprocess
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MIRROR_ROOT = "agent-self/config/"
OUT = Path(__file__).with_suffix(".out.json")

# Plausibility floor: the surface was measured at 195 pairs. A discovery that
# finds far fewer is a broken enumerator, not a clean repo -- fail closed.
MIN_PLAUSIBLE_PAIRS = 100


def tracked_files() -> set[str]:
    """NUL-delimited `git ls-files`.

    Deliberately NOT `command-center/p13_orphan_plan.tracked_files`: that one
    splits on newlines and applies a path normaliser, and importing it would
    pull an unrelated lane's module-level state into this probe.
    """
    raw = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout
    return {p for p in raw.decode("utf-8").split("\0") if p}


def read_text(rel: str) -> str | None:
    """Universal-newline read -- parity must not depend on CRLF vs LF checkout."""
    try:
        return (REPO / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def discover(tracked: set[str]) -> list[tuple[str, str]]:
    pairs = []
    for mirror in sorted(tracked):
        if not mirror.startswith(MIRROR_ROOT):
            continue
        root = mirror[len(MIRROR_ROOT) :]
        if root in tracked:
            pairs.append((root, mirror))
    return pairs


def diff_summary(root: str, mirror: str, max_lines: int = 40) -> dict:
    a = read_text(root)
    b = read_text(mirror)
    if a is None or b is None:
        return {"unreadable": True}
    a_lines = a.splitlines(keepends=True)
    b_lines = b.splitlines(keepends=True)
    ud = list(difflib.unified_diff(a_lines, b_lines, fromfile=root, tofile=mirror, n=1))
    changed = [
        ln
        for ln in ud
        if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))
    ]
    return {
        "unreadable": False,
        "root_lines": len(a_lines),
        "mirror_lines": len(b_lines),
        "changed_line_count": len(changed),
        # A `user_home_only` field lived here and was WRONG: it required every
        # changed line to contain `{{USER_HOME}}`, but a substitution produces a
        # PAIR of lines and only the mirror half carries the token, so it read
        # False for the two pairs that genuinely are templated. Removed rather
        # than left in a committed artifact. The authoritative test is
        # `differs_only_by_token` in ci/tests/test_deployed_hook_twin_parity.py,
        # which checks prefix, suffix and a single consistent expansion.
        "diff_head": "".join(ud[:max_lines]),
    }


def main() -> int:
    tracked = tracked_files()
    pairs = discover(tracked)

    identical: list[tuple[str, str]] = []
    differing: list[tuple[str, str]] = []
    unreadable: list[tuple[str, str]] = []
    for root, mirror in pairs:
        a, b = read_text(root), read_text(mirror)
        if a is None or b is None:
            unreadable.append((root, mirror))
        elif a == b:
            identical.append((root, mirror))
        else:
            differing.append((root, mirror))

    # ---- controls -------------------------------------------------------
    controls: dict[str, object] = {}

    # C1 comparator is not constant-true: a known-different pair must differ.
    # (KNOWN_DIVERGENT pair from the shipped guard.)
    c1_a = read_text("hooks/test-tamper-guard/guard.py")
    c1_b = read_text("agent-self/config/hooks/test-tamper-guard/guard.py")
    controls["c1_known_different_reads_different"] = (
        c1_a is not None and c1_b is not None and c1_a != c1_b
    )

    # C2 comparator is not constant-false: a file vs itself must read identical.
    controls["c2_self_reads_identical"] = read_text("AGENTS.md") == read_text(
        "AGENTS.md"
    )

    # C3 enumerator is not vacuous: a uuid path is not tracked and yields no pair.
    ghost = f"{MIRROR_ROOT}hooks/{uuid.uuid4().hex}.py"
    controls["c3_uuid_not_tracked"] = ghost not in tracked

    # C4 fail-closed on an implausible surface size.
    controls["c4_pair_count_plausible"] = len(pairs) >= MIN_PLAUSIBLE_PAIRS

    # C5 the enumerator finds the 4 pairs the shipped guard already pins.
    pinned = {
        "hooks/event-ledger/sessionstart-replay.py",
        "hooks/claim-guard/ledger-write.py",
        "hooks/edit-validate/record.py",
        "commands/orchestrate.md",
    }
    found_roots = {r for r, _ in pairs}
    controls["c5_all_shipped_pinned_pairs_discovered"] = pinned <= found_roots

    by_tree: dict[str, dict[str, int]] = {}
    for root, _ in pairs:
        tree = root.split("/", 1)[0] if "/" in root else "<root-file>"
        slot = by_tree.setdefault(tree, {"pairs": 0, "differing": 0})
        slot["pairs"] += 1
    for root, _ in differing:
        tree = root.split("/", 1)[0] if "/" in root else "<root-file>"
        by_tree[tree]["differing"] += 1

    payload = {
        "repo": str(REPO),
        "rev": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, check=True
        )
        .stdout.decode()
        .strip(),
        "pairs_total": len(pairs),
        "identical": len(identical),
        "differing": len(differing),
        "unreadable": len(unreadable),
        "by_tree": by_tree,
        "controls": controls,
        "all_controls_pass": all(controls.values()),
        "differing_pairs": [
            {"root": r, "mirror": m, **diff_summary(r, m)} for r, m in differing
        ],
        "identical_pairs": [r for r, _ in identical],
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"pairs={len(pairs)} identical={len(identical)} differing={len(differing)}")
    for k, v in controls.items():
        print(f"  control {k}: {v}")
    if not payload["all_controls_pass"]:
        print("FAILED:r3-twinsurface a control did not pass")
        return 1
    print(f"SUCCESS:r3-twinsurface -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
