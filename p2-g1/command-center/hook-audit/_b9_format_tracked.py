#!/usr/bin/env python
"""_b9_format_tracked.py -- is CI's `gate-lint-format` red, measured on the bytes CI reads?

WHY THIS EXISTS, and why `_r4_blobgate.py` did not catch it. That gate does the hard part
correctly (staged blobs, the committed ruff.toml, both-states controls) but walks a
HARDCODED eight-entry `PATHS` list. A file committed outside that list is not "clean" to it,
it is INVISIBLE -- the same shape as check_citations' H4 hole, where a number with no marker
was not unbacked but unseen. Measured 2026-08-14: commit bac65640 shipped
`command-center/hook-audit/_g5_vendorcaps.py` unformatted, the follow-up format pass
c2ab418f reformatted the files its author knew about, and the blob gate reported GREEN
throughout because that path was never in its list. `ruff format --check .` on the whole
repo was red the entire time.

So this probe DERIVES its file list -- every tracked `*.py` in the repo -- and can therefore
never go blind the same way. It is the local pre-commit twin of quality.yml's
`ruff format --check .`.

MEASURED ON THE BLOB, NOT THE WORKTREE. A Windows working tree is CRLF, git stores LF, CI
checks out LF, and ruff makes different decisions on the two forms (windows-shell 8b: a
`format --check` reported "already formatted" locally while CI wanted a reformat). Blobs are
read with `git cat-file --batch` -- ONE process for the whole index rather than 2,400 spawns
-- which returns stored bytes, unlike `git archive`, which re-applies EOL conversion on
Windows and hands back CRLF.

EVERY ruff CONFIG IS COPIED IN, NOT JUST THE ROOT ONE -- and getting this wrong is how the
first version of this probe manufactured a false red on four innocent files. ruff resolves
configuration hierarchically, from the NEAREST `pyproject.toml` / `ruff.toml` / `.ruff.toml`
above each file. Materialising only `*.py` + the root `ruff.toml` left
`tools/mcp/patent-search-mcp/pyproject.toml` out of the tree, so its four modules were
formatted against the wrong settings and reported as CI-red. They are clean. Measured
2026-08-14; recorded rather than quietly fixed, because the failing shape -- a probe whose
controls all PASS while it reads an environment the real gate never sees -- is the one this
program keeps repeating.

DETECTOR CONTROLS (both states, printed before any verdict, fail-closed on disagreement):
  C1 POSITIVE -- a deliberately mis-formatted file placed in the materialised tree must be
     flagged. If it is not, a short complaint list means nothing.
  C2 NEGATIVE -- a correctly formatted twin must NOT be flagged, so C1 is not just "ruff
     complains about everything".
  C3 NON-EMPTY -- the materialised tree must hold a plausible number of files. Zero, or a
     handful, is the "read the wrong tree and still say SUCCESS" failure this program has
     already shipped twice; it exits 2 rather than reporting clean.
  C4 CONFIG PARITY -- every ruff config tracked in the index is present in the materialised
     tree. C1-C3 all PASS while the tree is missing a config, so none of them can tell
     "genuinely unformatted" from "formatted against settings that do not apply" -- a control
     that cannot separate the two hypotheses is not a control, it only proves ruff ran. C4 is
     the one that separates them, and it is the reason the four false reds are not in the
     table below.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(
    subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=HERE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
)

# A tree this small means the walk failed, not that the repo is small: measured 2,423
# formatted + 58 unformatted python files at the time of writing.
MIN_PLAUSIBLE_FILES = 200

MANGLED = "x = {'a':1,'b':2}\ndef  f( a ,b ):\n\n\n    return (   a+b )\n"
CLEAN = 'x = {"a": 1, "b": 2}\n\n\ndef f(a, b):\n    return a + b\n'


# Everything ruff reads: the sources, and EVERY config that can govern one of them.
CONFIG_GLOBS = [
    "ruff.toml",
    "*/ruff.toml",
    ".ruff.toml",
    "*/.ruff.toml",
    "pyproject.toml",
    "*/pyproject.toml",
]
CONFIG_NAMES = {"ruff.toml", ".ruff.toml", "pyproject.toml"}


def _tracked_py() -> list[tuple[str, str]]:
    """-> [(path, blob_sha)] for every tracked *.py plus every ruff config, from the index."""
    out = subprocess.run(
        ["git", "ls-files", "-s", "--", "*.py", *CONFIG_GLOBS],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        # `<mode> <sha> <stage>\t<path>`
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3 and path:
            rows.append((path.strip(), parts[1]))
    return rows


def _materialise(rows: list[tuple[str, str]], root: Path) -> int:
    """Write every blob to root/<path>. ONE `git cat-file --batch` for all of them."""
    stdin = "\n".join(sha for _, sha in rows) + "\n"
    proc = subprocess.run(
        ["git", "cat-file", "--batch"],
        cwd=REPO,
        input=stdin.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    buf = proc.stdout
    pos = 0
    written = 0
    for path, _sha in rows:
        nl = buf.index(b"\n", pos)
        header = buf[pos:nl].decode("utf-8", "replace").split()
        size = int(header[2])
        start = nl + 1
        data = buf[start : start + size]
        pos = start + size + 1  # trailing newline after the object
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written += 1
    return written


def _would_reformat(root: Path) -> set[str]:
    out = subprocess.run(
        ["ruff", "format", "--check", "."],
        cwd=root,
        capture_output=True,
        text=True,
    ).stdout
    return {
        line[len("Would reformat: ") :].strip().replace("\\", "/")
        for line in out.splitlines()
        if line.startswith("Would reformat: ")
    }


def main() -> int:
    rows = _tracked_py()
    tmp = Path(tempfile.mkdtemp(prefix="b9blob_"))
    try:
        n = _materialise(rows, tmp)
        if n < MIN_PLAUSIBLE_FILES:
            print(f"CONTROL C3 non-empty tree = FAIL ({n} files materialised)")
            print(
                "FAILED:format-tracked materialised tree implausibly small -- verdict withheld"
            )
            return 2
        want_cfg = {p for p, _ in rows if Path(p).name in CONFIG_NAMES}
        have_cfg = {p for p in want_cfg if (tmp / p).exists()}
        c4 = want_cfg == have_cfg and len(want_cfg) > 0
        (tmp / "_ctl_mangled.py").write_text(MANGLED, encoding="utf-8")
        (tmp / "_ctl_clean.py").write_text(CLEAN, encoding="utf-8")
        comp = _would_reformat(tmp)
        c1 = "_ctl_mangled.py" in comp
        c2 = "_ctl_clean.py" not in comp
        print(f"CONTROL C1 mis-formatted file IS flagged   = {c1}")
        print(f"CONTROL C2 formatted file is NOT flagged   = {c2}")
        print(f"CONTROL C3 files materialised from blobs   = {n}")
        print(
            f"CONTROL C4 ruff configs present            = {c4} ({len(have_cfg)}/{len(want_cfg)})"
        )
        if not (c1 and c2 and c4):
            print(
                "FAILED:format-tracked detector control disagreed -- verdict withheld"
            )
            return 2
        offenders = sorted(comp - {"_ctl_mangled.py", "_ctl_clean.py"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    blob = {
        "probe": "_b9_format_tracked.py",
        "measured_on": "staged blobs (git cat-file --batch), not the worktree",
        "controls": {
            "C1_positive": c1,
            "C2_negative": c2,
            "C3_files": n,
            "C4_config_parity": c4,
            "C4_configs": len(want_cfg),
        },
        "tracked_unformatted": offenders,
        "tracked_unformatted_count": len(offenders),
    }
    (HERE / "B9-FORMAT-TRACKED.json").write_text(
        json.dumps(blob, indent=2) + "\n", encoding="utf-8"
    )
    for p in offenders:
        print(f"  TRACKED-UNFORMATTED {p}")
    if offenders:
        print(
            f"FAILED:format-tracked {len(offenders)} tracked file(s) would be reformatted by CI"
        )
        return 1
    print(
        f"SUCCESS:format-tracked 0 of {n} tracked files unformatted -- gate-lint-format is green"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
