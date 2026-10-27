"""LANE DOCS round 6 -- settle the 20/16 vs 19/15 surface counts against IMMUTABLE commits.

WHY THIS EXISTS
---------------
Round 5's report quoted ``bare_refs=20 missing=16`` inside an evidence block describing the
state *after* its fix, and that number was baked into two shipped files. The audit measured
19/15 at HEAD and refuted the sentence. The audit's discriminator was to MUTATE the working
tree back to the broken state and re-run. This probe reaches the same question by a
mechanically DIFFERENT route -- it never touches the working tree, it reads committed blobs at
two pinned SHAs -- so the two probes are independent signals rather than one signal run twice.

WHAT IT MEASURES
----------------
The same quantity ``docs/_lane_docs_r5_surface.py`` measures, by IMPORTING that module's
``extract`` / ``classify`` rather than re-implementing it. A probe that re-implements the
thing it checks can only ever agree with itself.

The two pins are full 40-char SHAs, not ref arithmetic:

  PRE_FIX  67137879...  parent of the round-5 fix; ``commands/sessions.md`` blob 3bfb914d
  POST_FIX 5d573583...  the round-5 fix itself;    ``commands/sessions.md`` blob df9d9d76

Both are immutable, so the numbers this probe prints can never go stale -- which is the whole
point. HEAD is reported too, but as a MOVING number that is never asserted: siblings add
command docs, and a gate pinned to a moving count is a gate the next lane disables.

CONTROLS -- three, and each one distinguishes two hypotheses rather than merely proving the
script ran.

  C1 PARITY (is my historical reader measuring the SAME quantity?)
     H1: it is  -> reader(HEAD commit) == the working-tree probe's own output at HEAD.
     H2: it is not -> they differ.
     Without C1 a matching 20/16 at the parent would prove nothing, because a reader that
     measured some *other* quantity could coincidentally land on 20.

  C2 DISCRIMINATION (is my reader blind to the change under test?)
     H1: it can see the fix -> reader(PRE_FIX) != reader(POST_FIX).
     H2: it is inert        -> identical counts at both pins.
     This is the control the estate keeps failing: ``len(events[ev].keys()) == 3`` on both
     sides. A reader that returns the same number either side of a one-line fix is measuring
     readability, not the claim.

  C3 FLOOR (did the corpus collapse to zero?)
     Any pin yielding 0 command docs or 0 tokens fails closed. "Nothing found -> pass" is the
     no-op gate shape from ci-hygiene.md §1.

Run:  py -3.11 docs/_lane_docs_r6_pinned_counts.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

#: Parent of the round-5 fix. Immutable.
PRE_FIX = "67137879d5e28acaf0fa7280d1943de362de864d"
#: The round-5 fix. Immutable.
POST_FIX = "5d573583f5b9694343f1975b42752e893141a144"

#: Top-level command docs only -- this mirrors ``(REPO / "commands").glob("*.md")``.
COMMAND_DOC = re.compile(r"^commands/[^/]+\.md$")


def _load_surface():
    """Import the round-5 surface probe so this probe cannot merely agree with itself."""
    src = HERE / "_lane_docs_r5_surface.py"
    if not src.is_file():
        raise SystemExit(f"FAILED:docs-r6-pinned missing dependency {src}")
    spec = importlib.util.spec_from_file_location("_r5_surface", src)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise SystemExit("FAILED:docs-r6-pinned could not load _lane_docs_r5_surface")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SURFACE = _load_surface()


def _git(*args: str) -> str:
    # encoding is EXPLICIT: ``text=True`` decodes with the locale default, which is cp1252
    # on this box and raises UnicodeDecodeError on the first non-Latin-1 byte in a doc.
    # CI (ubuntu-latest) defaults to UTF-8 and would have hidden the defect entirely.
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"FAILED:docs-r6-pinned git {' '.join(args)} rc={proc.returncode} "
            f"{proc.stderr.strip()[:200]}"
        )
    return proc.stdout


def tracked_at(rev: str) -> set[str]:
    """Every path tracked at ``rev``, forward-slashed."""
    out = _git("ls-tree", "-r", "--name-only", rev)
    return {ln.strip().replace("\\", "/") for ln in out.splitlines() if ln.strip()}


def blob_at(rev: str, path: str) -> str:
    """The STORED bytes of ``path`` at ``rev``.

    ``git show <rev>:<path>`` returns the blob with no EOL conversion (``git archive``
    is the one that re-inserts CRLF on Windows). Forward slashes only -- a backslash
    pathspec is not a valid git revision.
    """
    return _git("show", f"{rev}:{path}")


def resolves_at(path: str, tracked: set[str]) -> bool:
    """Historical analogue of the round-5 probe's ``path in tracked or (REPO/path).exists()``.

    A historical measurement must not consult today's filesystem, so ``.exists()`` has to be
    reconstructed from the tree. The subtlety C1 caught: ``.exists()`` is TRUE for a
    DIRECTORY, and a directory is never itself a member of ``git ls-tree`` output -- it only
    exists implicitly, as the prefix of its children. A naive ``path in tracked`` therefore
    reports the token ``scripts/`` as missing while the working-tree probe reports it as
    resolving, and the two readers disagree by exactly 1.

    Measured cost of getting this wrong: the first version of this probe printed
    ``missing=16`` at the HEAD commit against the working-tree probe's ``missing=15`` -- i.e.
    it would have "confirmed" round 5's refuted 16 by reproducing the right number for the
    wrong reason. C1 is the only thing that caught it.
    """
    if path in tracked:
        return True
    directory = path.rstrip("/")
    if not directory:
        return False
    prefix = directory + "/"
    return any(t.startswith(prefix) for t in tracked)


def measure(rev: str) -> dict[str, object]:
    """bare_refs / missing over top-level command docs, as stored at ``rev``.

    Control C1 proves this is the same quantity the working-tree probe reports.
    """
    tracked = tracked_at(rev)
    docs = sorted(p for p in tracked if COMMAND_DOC.match(p))
    rows: list[dict[str, object]] = []
    for doc in docs:
        text = blob_at(rev, doc)
        for i, line in enumerate(text.splitlines(), 1):
            for tok in SURFACE.extract(line):
                kind, path = SURFACE.classify(tok, tracked)
                if kind != "BARE-REPO":
                    continue
                rows.append(
                    {
                        "doc": doc,
                        "line": i,
                        "token": tok,
                        "resolves_in_repo": resolves_at(path, tracked),
                    }
                )
    missing = [r for r in rows if not r["resolves_in_repo"]]
    return {
        "rev": rev,
        "command_docs": len(docs),
        "bare_refs": len(rows),
        "missing": len(missing),
        "missing_tokens": sorted({str(r["token"]) for r in missing}),
    }


def working_tree_baseline() -> tuple[int, int]:
    """Run the round-5 surface probe as a subprocess and parse its own terminal marker."""
    proc = subprocess.run(
        [sys.executable, str(HERE / "_lane_docs_r5_surface.py")],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    m = re.search(r"bare_refs=(\d+) missing=(\d+)", proc.stdout)
    if proc.returncode != 0 or not m:
        raise SystemExit(
            f"FAILED:docs-r6-pinned baseline probe rc={proc.returncode} "
            f"tail={proc.stdout.strip()[-160:]!r}"
        )
    return int(m.group(1)), int(m.group(2))


def main() -> int:
    head = _git("rev-parse", "HEAD").strip()

    pre = measure(PRE_FIX)
    post = measure(POST_FIX)
    at_head = measure(head)

    base_refs, base_missing = working_tree_baseline()

    # C1 PARITY -- historical reader at the HEAD commit must equal the working-tree probe.
    c1 = (at_head["bare_refs"], at_head["missing"]) == (base_refs, base_missing)
    # C2 DISCRIMINATION -- the two pins must NOT agree, or the reader is inert.
    c2 = (pre["bare_refs"], pre["missing"]) != (post["bare_refs"], post["missing"])
    # C3 FLOOR -- fail closed on an empty corpus.
    c3 = all(
        int(m["command_docs"]) > 0 and int(m["bare_refs"]) > 0 for m in (pre, post)
    )

    report = {
        "pins": {"PRE_FIX": PRE_FIX, "POST_FIX": POST_FIX},
        "head": head,
        "pre_fix": pre,
        "post_fix": post,
        "at_head_commit": at_head,
        "working_tree_baseline": {"bare_refs": base_refs, "missing": base_missing},
        "controls": {
            "C1_parity_historical_equals_working_tree": c1,
            "C2_pins_discriminate": c2,
            "C3_corpus_nonempty": c3,
        },
    }
    print(json.dumps(report, indent=2))

    failures = [
        name
        for name, ok in (("C1-parity", c1), ("C2-discriminate", c2), ("C3-floor", c3))
        if not ok
    ]
    if failures:
        print(
            f"FAILED:docs-r6-pinned controls={','.join(failures)}",
            file=sys.stderr,
        )
        return 1

    print(
        f"SUCCESS:docs-r6-pinned controls=C1,C2,C3-ok "
        f"pre_fix={pre['bare_refs']}/{pre['missing']} "
        f"post_fix={post['bare_refs']}/{post['missing']} "
        f"head_moving={at_head['bare_refs']}/{at_head['missing']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
