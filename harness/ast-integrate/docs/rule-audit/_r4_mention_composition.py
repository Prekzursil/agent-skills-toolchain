"""Round-4 disclosure probe: what IS inside the bare-filename MENTION exemption?

The round-3 adversary's residual 2: ``r2_pathrefs.py`` exempts bare-filename mentions (a token
with no ``/``, so it asserts no location and cannot be a broken pointer), reports only the COUNT,
and the artifact never states the composition. A count bounds nothing on its own -- an exemption
holding 56 harmless mentions and one holding 55 harmless mentions plus a real dead pointer print
the same number.

READ-ONLY, and it does not touch the gate: it imports ``r2_pathrefs`` and re-classifies the same
tokens, so it cannot drift from what the gate actually exempts. Prints the split by verdict and
the full list of names that resolve NOWHERE, which is the only bucket that could hide something.

Detector control, printed: a name that certainly exists (``rule_audit.py``) must classify EXACT
or BASENAME-ONLY, never MISSING. Without it a resolver that reports MISSING for everything would
produce a scary-looking list and read as diligence.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from r2_pathrefs import (  # noqa: E402  (path shim must precede the import)
    TREES,
    classify,
    normalise_token,
    references,
)


def main() -> int:
    verdicts: Counter[str] = Counter()
    nowhere: list[str] = []
    total = 0

    for label, root in TREES.items():
        if not root.is_dir():
            print(
                f"FAILED:r4_mention_composition tree {label} is missing -- fail closed"
            )
            return 1
        for path in sorted(root.rglob("*.md")):
            for lineno, _line, token in references(path.read_text(encoding="utf-8")):
                if "/" in normalise_token(token):
                    continue  # a located claim, not a bare mention
                total += 1
                verdict = classify(token, root, path.parent)
                verdicts[verdict] += 1
                if verdict.startswith("MISSING"):
                    nowhere.append(f"{label}:{path.name}:{lineno} -> {token}")

    control = classify(
        "rule_audit.py", Path(__file__).resolve().parents[2], Path(__file__).parent
    )
    print(f"control: a name that certainly exists classifies {control!r}")
    if control.startswith("MISSING"):
        print(
            "FAILED:r4_mention_composition the resolver cannot find a file that exists"
        )
        return 1

    print(f"bare-filename mentions across {len(TREES)} tree(s): {total}")
    for verdict, count in sorted(verdicts.items(), key=lambda kv: -kv[1]):
        print(f"  {count:3d}  {verdict}")
    print("resolving NOWHERE (the only bucket that could hide a dead pointer):")
    for line in nowhere:
        print(f"    {line}")
    if total == 0:
        print(
            "FAILED:r4_mention_composition zero mentions found -- broken scan, fail closed"
        )
        return 1

    # Cross-check against the gate's OWN counter, run as a subprocess. My 114 counts every bare
    # mention; the gate's ``name_mentions`` counts only the non-EXACT ones, so the two numbers
    # look like a contradiction until they are reconciled -- and an unreconciled disagreement
    # between two instruments must be read as a detector fault, not published as a finding.
    non_exact = total - verdicts["EXACT"]
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "r2_pathrefs.py")],
        capture_output=True,
        text=True,
        timeout=900,
    )
    # Parse the line the gate ALWAYS prints, not ``name_mentions=``. That counter lives only in
    # the SUCCESS branch (``r2_pathrefs.py:325-330``), and the gate returns 2 from the
    # tracked-defect branch above it, so while the known defect is live the composition counters
    # -- ``name_mentions``, ``basename_only``, ``missing`` -- are UNREACHABLE. That is the
    # mechanical reason the artifact never stated the composition: the tool only volunteers it in
    # a state the tool has never been in.
    match = re.search(
        r"bare-filename MENTIONS \(no location asserted, not findings\): (\d+)",
        proc.stdout,
    )
    if match is None:
        print("FAILED:r4_mention_composition the gate printed no mention counter")
        return 1
    gate_count = int(match.group(1))
    print(
        f"cross-check: non-EXACT here = {non_exact}  ==  r2_pathrefs name_mentions = "
        f"{gate_count}  {'AGREE' if non_exact == gate_count else 'DISAGREE'}"
    )
    if non_exact != gate_count:
        print(
            "FAILED:r4_mention_composition two instruments disagree on the exempted set -- "
            "that is a detector fault to resolve, not a number to publish"
        )
        return 1
    print(
        f"SUCCESS:r4_mention_composition {total} mention(s): "
        + ", ".join(
            f"{c} {v}" for v, c in sorted(verdicts.items(), key=lambda kv: -kv[1])
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
