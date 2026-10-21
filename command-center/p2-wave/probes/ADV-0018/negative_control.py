"""ADV-0018 negative control (NC-ADV0018-FRONTMATTER-POINTER-REMOVAL): the frontmatter
detector must fire (RED) for a declared-contradicted note whose superseded_by key is
absent even when the body mentions the token, and must stay silent (GREEN) for the same
shape carrying a non-empty pointer. Uses the SAME detector function probe 2 ships.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from probe2_frontmatter import detector
from shared import write_raw

BAD = """---
title: fixture contradicted no pointer
type: report
permalink: fixtures/contradicted-no-pointer
tags:
- adv-0018-fixture
---

- status: BLOCKED
- note: body mentions superseded_by in prose only, not as a frontmatter key
"""

GOOD = """---
title: fixture contradicted with pointer
type: report
permalink: fixtures/contradicted-with-pointer
tags:
- adv-0018-fixture
superseded_by: "[[Replacement note]]"
---

- status: BLOCKED
- superseded_by recorded in frontmatter
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        bad = Path(td) / "bad.md"
        good = Path(td) / "good.md"
        bad.write_text(BAD, encoding="utf-8")
        good.write_text(GOOD, encoding="utf-8")
        r_bad = detector(bad)
        r_good = detector(good)
    fired = r_bad["fires"] is True          # must FIRE on the bad state
    silent = r_good["fires"] is False       # must stay SILENT on the good state
    verdict = "PASS" if (fired and silent) else "FAIL"
    lines = [
        f"DETECTOR CONTROL: {verdict}",
        f"  bad_state (no frontmatter superseded_by, body mention only): fires={r_bad['fires']}"
        f" (required True) -> {'OK' if fired else 'BROKEN'}",
        f"  good_state (frontmatter superseded_by present): fires={r_good['fires']}"
        f" (required False) -> {'OK' if silent else 'BROKEN'}",
    ]
    text_out = "\n".join(lines) + "\n"
    print(text_out, end="")
    write_raw("negative-control", {
        "control": "NC-ADV0018-FRONTMATTER-POINTER-REMOVAL",
        "verdict": verdict,
        "fired_on_bad_state": fired,
        "silent_on_good_state": silent,
        "bad_state_output": f"fires={r_bad['fires']} superseded_by={r_bad['superseded_by']}",
        "good_state_output": f"fires={r_good['fires']} superseded_by={r_good['superseded_by']}",
    }, text_out)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
