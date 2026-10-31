"""Pre-commit self-check: would THIS working-tree document fail the published-command gate?

The gate reads committed bytes (`git cat-file -p HEAD:<path>`), so a document cannot be
tested by it until after it is committed -- which is how round 3 shipped a commit whose
own report the gate then flagged. This runs the SHIPPED extractors and the SHIPPED
resolver over the working-tree bytes instead, so the answer arrives before the commit
rather than after it.

CONTROL, both states: a synthetic uuid4 target appended to the scanned text must be
reported (proving the scanner reads THIS file's bytes and can fail), while the real
content is judged on its own. Without that, a clean result could equally mean the file
was never read.
"""

from __future__ import annotations

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_published_commands as G  # noqa: E402


def scan_text(text: str, citer: str, tracked: set[str]) -> list[tuple[int, str, str]]:
    bad: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        marked = {m.group(1) for m in G.EXAMPLE.finditer(line)}
        for verb, pat in G.EXTRACTORS:
            for m in pat.finditer(line):
                target = m.group(1)
                if target in marked:
                    continue
                ok, _ = G.resolve(target, citer, tracked)
                if not ok:
                    bad.append((lineno, verb, target))
    return bad


def main() -> int:
    root = G.repo_root()
    tracked = {p for p in G.git(root, "ls-files").splitlines() if p}
    paths = sys.argv[1:] or ["command-center/slop-report/SLOP-BUILD-R4.md"]
    rc = 0
    for rel in paths:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            text = fh.read()

        sentinel = f"scripts/_zz_selfcheck_{uuid.uuid4().hex}.ps1"
        ctl = scan_text(f"{text}\nrun `pwsh -File {sentinel}` here\n", rel, tracked)
        if not any(t == sentinel for _l, _v, t in ctl):
            print(
                f"FAILED:selfcheck control did not fire for {rel} -- scanner is inert"
            )
            return 1

        bad = scan_text(text, rel, tracked)
        print(f"{rel}: control ok, {len(bad)} unresolved published command(s)")
        for lineno, verb, target in bad:
            print(f"   !! {rel}:{lineno} [{verb}] -> {target} is NOT tracked")
            rc = 1
    print("SUCCESS:selfcheck" if rc == 0 else "FAILED:selfcheck")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
