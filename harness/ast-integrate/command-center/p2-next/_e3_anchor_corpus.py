"""Does `host.tld:port` pass as a file:line evidence anchor -- and what does closing it cost?

The round-3 fix replaced "anything with a colon and a digit" with "the head must name a PATH".
An independent auditor then measured a residual in the SAME class: `example.com:443` and
`site.io:8080` were still accepted, because `.com` and `.io` satisfy "an extension carrying at
least one letter". A host:port is not a reference to a line of anything.

Closing it has a cost in the other direction, and the previous round's lesson is that the cost is
measured BEFORE shipping, not asserted. So ground truth here is MECHANICAL, not hand-built:

  every anchor-shaped token is extracted from the committed markdown corpus, and a token counts
  as a REAL anchor when its head RESOLVES to a path `git ls-files` tracks. Membership is byte
  equality -- no judgement, no regex opinion.

That is a corpus two orders of magnitude larger than the 10-to-13 hand-built strings the previous
two rounds argued over, and it is conservative in the right direction: every resolving token is
CERTAINLY a real anchor, so "the new rule rejects 0 of them" is a real no-false-positive result
rather than a small-sample one.

BEFORE is PINNED to a SHA, not to the worktree. An earlier draft of this probe compared the
worktree against itself the moment the fix was applied and printed "newly rejected: 0" -- the
exact landmine _d3_timestamp_anchor.py was rewritten to remove. If BEFORE already carries the
fix, this exits 2 rather than reporting a clean sheet.

Sections
  A  the two audited holes, in BOTH states
  B  corpus extraction + mechanical ground truth
  C  both directions on that corpus
  D  the hand-built sets, so the closure is visible per string
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
GATE = ".agents/skills/claim-verify-gate/scripts/claim_gate.py"
# The commit before the host:port fix -- the last state whose `_is_path_head` accepted any
# letter-bearing extension. Override with argv[1].
BEFORE_REV = "5423de0f"

sys.path.insert(0, str(REPO / ".agents/skills/claim-verify-gate/scripts"))

import claim_gate as after  # noqa: E402  (sys.path is set above on purpose)

FILE_LINE = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.][A-Za-z0-9_./\\-]*):(\d+)\b")

NON_ANCHORS = [
    "2026-08-12T05:15:00",
    "05:15",
    "ratio 3:1",
    "v1.2:3",
    "score 9:10",
    "I recall seeing it",
    "example.com:443",
    "site.io:8080",
    "api.github.com:443",
    "redis.internal:6379",
    "srv.corp:5432",
    "localhost:8080",
    "127.0.0.1:8812",
]
REAL_ANCHORS = [
    "command-center/p2-next/rail_count_gate.py:133",
    "claim_gate.py:113",
    r"C:\Users\Prekzursil\source\ast-integrate\scripts\claim_gate.py:113",
    "Makefile:12",
    "Dockerfile:5",
    "LICENSE:3",
    ".github/workflows/p2next-rail-count.yml:14",
    "platform/lib/receipt_schema_gate.py:520",
    "data/rows.jsonl:1200",
    "archive.7z:1",
    "AGENTS.md:74",
    "a/b/c/d.tsx:19",
    "Justfile:2",
    "x.out.json:4",
    ".gitattributes:2",
]


def git(*args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, check=True
    )
    return out.stdout.decode("utf-8", errors="replace")


def load_before(rev: str, work: Path):
    blob = git("show", f"{rev}:{GATE}")
    if "_FILE_EXTENSIONS" in blob:
        return None
    path = work / "claim_gate_before.py"
    path.write_text(blob, encoding="utf-8", newline="")
    spec = importlib.util.spec_from_file_location("claim_gate_before", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    rev = sys.argv[1] if len(sys.argv) > 1 else BEFORE_REV
    with tempfile.TemporaryDirectory() as tmp:
        before = load_before(rev, Path(tmp))
        if before is None:
            print(f"FAILED: {rev} already carries the fix; it is not a before-state")
            return 2
        return run(before)


def run(before) -> int:
    print(f"BEFORE = {BEFORE_REV}:{GATE}   AFTER = worktree")
    print("== A the two audited holes, BOTH states ==")
    for probe in (
        "example.com:443",
        "site.io:8080",
        "localhost:8080",
        "127.0.0.1:8812",
    ):
        print(
            f"   {probe:<20} before={before._is_anchor(probe)!s:<5} "
            f"after={after._is_anchor(probe)!s}"
        )

    print("== B corpus ==")
    tracked = [p for p in git("ls-files").splitlines() if p]
    tracked_set = set(tracked)
    basenames = {p.rsplit("/", 1)[-1] for p in tracked}
    docs = [p for p in tracked if p.endswith(".md")]
    print(f"   tracked files                : {len(tracked)}")
    print(f"   markdown blobs scanned       : {len(docs)}")

    heads: Counter[str] = Counter()
    for path in docs:
        try:
            text = git("show", f"HEAD:{path}")
        except subprocess.CalledProcessError:
            continue
        for match in FILE_LINE.finditer(text):
            heads[match.group(1)] += 1
    print(f"   distinct anchor-shaped heads : {len(heads)}")

    def resolves(head: str) -> bool:
        norm = head.replace("\\", "/").lstrip("./")
        if norm in tracked_set or head in tracked_set:
            return True
        if norm.rsplit("/", 1)[-1] in basenames:
            return True
        return any(p.endswith("/" + norm) for p in tracked_set)

    real = sorted(h for h in heads if resolves(h))
    unreal = sorted(h for h in heads if not resolves(h))
    print(f"   heads that RESOLVE (ground truth REAL)   : {len(real)}")
    print(f"   heads that do not resolve                : {len(unreal)}")
    if not real or not unreal:
        print("FAILED: corpus degenerate; the extraction or ls-files read is broken")
        return 1

    print("== C both directions on that corpus ==")
    b_real = [h for h in real if before._is_path_head(h)]
    a_real = [h for h in real if after._is_path_head(h)]
    lost = sorted(set(b_real) - set(a_real))
    rescued = sorted(set(a_real) - set(b_real))
    print(f"   REAL accepted BEFORE : {len(b_real)}/{len(real)}")
    print(f"   REAL accepted AFTER  : {len(a_real)}/{len(real)}")
    print(f"   REGRESSIONS (real anchors lost): {len(lost)} {lost[:10]}")
    print(f"   pre-existing false positives FIXED: {len(rescued)} {rescued[:10]}")

    b_un = [h for h in unreal if before._is_path_head(h)]
    a_un = [h for h in unreal if after._is_path_head(h)]
    closed = sorted(set(b_un) - set(a_un))
    print(f"   NON-RESOLVING accepted BEFORE : {len(b_un)}/{len(unreal)}")
    print(f"   NON-RESOLVING accepted AFTER  : {len(a_un)}/{len(unreal)}")
    print(f"   newly REJECTED: {len(closed)}")
    for head in closed:
        print(f"      CLOSED {head}  (x{heads[head]})")

    print("== D hand-built sets ==")
    b_bad = [s for s in NON_ANCHORS if before._is_anchor(s)]
    a_bad = [s for s in NON_ANCHORS if after._is_anchor(s)]
    print(f"   non-anchors accepted BEFORE : {len(b_bad)}/{len(NON_ANCHORS)} {b_bad}")
    print(f"   non-anchors accepted AFTER  : {len(a_bad)}/{len(NON_ANCHORS)} {a_bad}")
    b_ok = [s for s in REAL_ANCHORS if before._is_anchor(s)]
    a_ok = [s for s in REAL_ANCHORS if after._is_anchor(s)]
    print(f"   real anchors kept BEFORE : {len(b_ok)}/{len(REAL_ANCHORS)}")
    print(f"   real anchors kept AFTER  : {len(a_ok)}/{len(REAL_ANCHORS)}")
    print(f"   real anchors LOST : {[s for s in REAL_ANCHORS if s not in a_ok]}")

    out = {
        "before_rev": BEFORE_REV,
        "corpus_heads": len(heads),
        "real_resolving": len(real),
        "real_kept_before": len(b_real),
        "real_kept_after": len(a_real),
        "real_regressions": lost,
        "false_positives_fixed": rescued,
        "nonresolving": len(unreal),
        "nonresolving_accepted_before": len(b_un),
        "nonresolving_accepted_after": len(a_un),
        "newly_rejected": closed,
        "newly_rejected_occurrences": {h: heads[h] for h in closed},
        "handbuilt_nonanchors_accepted_before": b_bad,
        "handbuilt_nonanchors_accepted_after": a_bad,
        "handbuilt_real_lost_after": [s for s in REAL_ANCHORS if s not in a_ok],
    }
    dest = REPO / "command-center/p2-next/E3-ANCHOR-CORPUS.json"
    with open(dest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"SUCCESS:e3-anchor-corpus wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
