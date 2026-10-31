"""Where is the blueprint corpus actually THIN?

Scout's recommendation is only meaningful if the demanded set can be unsatisfiable. This probe
measures, over every executable blueprint, how many provide each capability and cover each
hazard - so a goal can be drawn from the measured gaps instead of guessed. Reported as counts,
not opinions.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from foundry import mechanisms, registry  # noqa: E402
from foundry.model import HAZARD_IDS, capabilities  # noqa: E402


def main() -> int:
    dsl = registry.load_dsl_candidates()
    profs = [mechanisms.profile(c) for c in dsl]
    n = len(profs)
    cap_counts = Counter()
    haz_counts = Counter()
    for p in profs:
        cap_counts.update(p.provided)
        haz_counts.update(p.covered_hazards)
    out = {
        "executable_blueprints": n,
        "capability_presence": {c: cap_counts.get(c, 0) for c in capabilities()},
        "hazard_coverage": {h: haz_counts.get(h, 0) for h in HAZARD_IDS},
        "saturated_capabilities": [
            c for c in capabilities() if cap_counts.get(c, 0) == n
        ],
        "absent_capabilities": [c for c in capabilities() if cap_counts.get(c, 0) == 0],
        "rare_capabilities": sorted(
            (c for c in capabilities() if 0 < cap_counts.get(c, 0) <= max(1, n // 10)),
            key=lambda c: cap_counts[c],
        ),
        "rare_hazards": sorted(
            (h for h in HAZARD_IDS if 0 < haz_counts.get(h, 0) <= max(1, n // 10)),
            key=lambda h: haz_counts[h],
        ),
        "never_covered_hazards": [h for h in HAZARD_IDS if haz_counts.get(h, 0) == 0],
    }
    print(json.dumps(out, indent=2))
    print("SUCCESS:foundry-corpus-thinness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
