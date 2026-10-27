"""Round 8: do the deferred command-doc invocations resolve ANYWHERE, or nowhere?

WHY THIS EXISTS
---------------
Round 5 measured 16 unresolved ``scripts/...`` references in command docs, fixed the
one in PROSE, and scoped the rest out:

    "The 13 code-block invocations are out of scope by design, not overlooked."

That scoping is defensible ONLY if those invocations resolve at RUNTIME against a
root other than the repo -- which is exactly what round 5 established for
``scripts/hooks/cost-tracker.js`` (absent from the repo; 27 files present under
``~/.claude/scripts/hooks/``). Nobody measured the other tokens. From inside the
repo, "out of scope by design" and "a published command tells you to run a file
that exists nowhere" look identical -- and the lane's charter names the second as
its target defect class.

REUSE, NOT REIMPLEMENTATION
---------------------------
The token grammar, the BARE-REPO classifier and the repo resolver are IMPORTED from
``_lane_docs_r5_surface.py`` -- the same module ``_lane_docs_r6_pinned_counts.py``
loads. If this probe re-implemented them it could disagree with the 20/16 -> 19/15
figures the lane has already pinned, and then two of the lane's own numbers would
be measuring different things while appearing to measure one. What is NEW here is
only the second axis: resolution against the LIVE deploy roots.

    REPO      resolves at the repo root                -> not a defect
    SHORTHAND absent there, but the file ships in this repo under another root
                                                       -> not a defect; the
                                                          reference is relative
                                                          to that root
    RUNTIME   absent from the repo, present in a live deploy root
                                                       -> not a defect, but the
                                                          doc should name it
    DEAD      resolves in NO searched root             -> genuine dead promise

CONTROLS (four-state; a two-state control could not tell "my resolver is broken"
from "everything really is dead", which is the failure mode that matters here --
it would manufacture a spectacular and entirely false finding)

    C1  a token known to be at the repo root      must land in REPO
    C2  a token known to be live-only             must land in RUNTIME
    C3  a token that exists nowhere               must land in DEAD
    C4  a token that ships under another root     must land in SHORTHAND
    C5  the corpus must be non-empty, so "nothing found" can never read as clean

All four must land in four DIFFERENT buckets or the run aborts without reporting.
C4 was ADDED after this probe shipped a false DEAD (see ``_live_bucket``): the
first version had no SHORTHAND bucket, so a file that exists at three tracked
paths was reported as a dead promise.

The live roots are read READ-ONLY. Nothing here writes outside ``docs/``.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
HOME = Path(os.path.expanduser("~"))

#: Roots a command doc's ``scripts/...`` token could legitimately resolve against.
#: ``~/.claude`` is this repo's deploy target; round 5 proved ``scripts/hooks/``
#: exists there and not here.
LIVE_ROOTS = (
    ("~/.claude", HOME / ".claude"),
    ("~/.agents", HOME / ".agents"),
    ("~/.codex", HOME / ".codex"),
)

FENCE = re.compile(r"^\s*(?:```|~~~)")

CONTROL_REPO = "scripts/longrun.ps1"
CONTROL_RUNTIME = "scripts/hooks/cost-tracker.js"
CONTROL_DEAD = "scripts/zzz-not-a-real-file.js"
#: Tracked at 3 paths under the vendored metaswarm plugin, none of them
#: ``scripts/`` at the repo root. Deliberately NOT the token this probe is used
#: to classify, so the SHORTHAND control is not the claim vouching for itself.
CONTROL_SHORTHAND = "scripts/beads-fetch-conversation-history.ts"


def _load_surface():
    """Import the round-5 surface probe so this probe cannot merely agree with itself."""
    src = HERE / "_lane_docs_r5_surface.py"
    if not src.is_file():
        raise SystemExit(f"FAILED:docs-r8-dead missing dependency {src}")
    spec = importlib.util.spec_from_file_location("_r5_surface_r8", src)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise SystemExit("FAILED:docs-r8-dead could not load _lane_docs_r5_surface")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SURFACE = _load_surface()


def _live_bucket(token: str, tracked: set[str]) -> tuple[str, str]:
    """RUNTIME/SHORTHAND/DEAD for a token that does not resolve at the repo root.

    SHORTHAND is the bucket this probe originally lacked, and its absence
    produced a FALSE DEAD: ``scripts/beads-fetch-pr-comments.ts`` does not exist
    at the repo root, but the file ships at three tracked paths under the
    vendored metaswarm plugin, where the reference is relative to that plugin's
    own root. Reporting it as a dead promise would have been the root-anchoring
    overclaim this lane exists to catch -- caught here only by a second,
    mechanically different probe (a basename search over ``git ls-files``).
    """
    bare = token.rstrip("*").rstrip("/")
    tail = bare.rsplit("/", 1)[-1]
    elsewhere = sorted(p for p in tracked if p.endswith("/" + tail))
    if elsewhere:
        return "SHORTHAND", elsewhere[0]
    for label, root in LIVE_ROOTS:
        if (root / bare).exists():
            return "RUNTIME", f"{label}/{bare}"
    return "DEAD", ""


def _bucket(token: str, tracked: set[str]) -> tuple[str, str]:
    if SURFACE.resolves(token, tracked):
        return "REPO", token
    return _live_bucket(token, tracked)


def main() -> int:
    tracked = SURFACE.tracked_repo_paths()

    controls = {
        "C1_repo": _bucket(CONTROL_REPO, tracked)[0],
        "C2_runtime": _bucket(CONTROL_RUNTIME, tracked)[0],
        "C3_dead": _bucket(CONTROL_DEAD, tracked)[0],
        "C4_shorthand": _bucket(CONTROL_SHORTHAND, tracked)[0],
    }
    expected = {
        "C1_repo": "REPO",
        "C2_runtime": "RUNTIME",
        "C3_dead": "DEAD",
        "C4_shorthand": "SHORTHAND",
    }
    if controls != expected:
        print(
            f"FAILED:docs-r8-dead controls did not separate: {controls} != {expected}"
        )
        return 1

    docs = sorted(p for p in tracked if re.fullmatch(r"commands/[^/]+\.md", p))
    if not docs:
        print("FAILED:docs-r8-dead corpus is empty -- nothing found cannot mean clean")
        return 1

    occ: dict[str, list[dict[str, object]]] = {}
    for rel in docs:
        text = io.open(REPO / rel, encoding="utf-8", newline="").read()
        fenced = False
        for i, line in enumerate(text.splitlines(), start=1):
            if FENCE.match(line):
                fenced = not fenced
                continue
            for tok in SURFACE.extract(line):
                kind, _ = SURFACE.classify(tok, tracked)
                if kind != "BARE-REPO" or SURFACE.resolves(tok, tracked):
                    continue
                occ.setdefault(tok, []).append(
                    {"doc": rel, "line": i, "fenced": fenced}
                )

    if not occ:
        print("FAILED:docs-r8-dead zero unresolved tokens -- pinned probe says 15")
        return 1

    rows = []
    for token in sorted(occ):
        bucket, where = _live_bucket(token, tracked)
        rows.append(
            {
                "token": token,
                "bucket": bucket,
                "resolves_at": where,
                "occurrences": occ[token],
            }
        )

    dead = [r for r in rows if r["bucket"] == "DEAD"]
    runtime = [r for r in rows if r["bucket"] == "RUNTIME"]
    shorthand = [r for r in rows if r["bucket"] == "SHORTHAND"]
    total_occ = sum(len(r["occurrences"]) for r in rows)

    print(json.dumps({"controls": controls, "unresolved_at_repo_root": rows}, indent=2))
    print(
        f"SUCCESS:docs-r8-dead controls=4-state-ok command_docs={len(docs)} "
        f"tokens={len(rows)} occurrences={total_occ} "
        f"shorthand={len(shorthand)} runtime={len(runtime)} dead={len(dead)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
