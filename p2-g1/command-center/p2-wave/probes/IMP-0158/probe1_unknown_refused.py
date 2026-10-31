#!/usr/bin/env python3
"""IMP-0158 probe1 (source + both-states): an unknown-tier candidate is REFUSED
by the admission path while its first-party twin (same content, verified
evidence) is AUTO-ADMITTED."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from marketplace.trust_tiers import AUTO_ADMIT, REFUSED, assign_tier, decide_admission  # noqa: E402

UNKNOWN_EV = {"publisher_id": "stranger", "publisher_repo": "", "identity_verified": False, "signature_verified": False}
FIRSTPARTY_EV = {"publisher_id": "prekzursil", "publisher_repo": "Prekzursil/ast-integrate", "identity_verified": True, "signature_verified": True}


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0158-p1-"))
    try:
        candidate = {"id": "widget@1.0.0", "files": ["a", "b"], "trust_evidence": dict(UNKNOWN_EV)}
        twin = {"id": "widget@1.0.0", "files": ["a", "b"], "trust_evidence": dict(FIRSTPARTY_EV)}
        d_unknown = decide_admission(candidate)
        d_twin = decide_admission(twin)
        tier_unknown = assign_tier(candidate).tier
        tier_twin = assign_tier(twin).tier
        saved = json.dumps(candidate, sort_keys=True)
        checks = {
            "unknown_tier": tier_unknown == "unknown",
            "unknown_refused": d_unknown.verdict == REFUSED,
            "twin_first_party": tier_twin == "first-party",
            "twin_auto_admitted": d_twin.verdict == AUTO_ADMIT,
            "candidate_untouched": json.dumps(candidate, sort_keys=True) == saved,
            "refusal_names_paths": "clean-room" in " ".join(d_unknown.requirements) or "owner approval" in " ".join(d_unknown.requirements),
        }
        print(json.dumps({"unknown": {"tier": tier_unknown, "verdict": d_unknown.verdict},
                          "twin": {"tier": tier_twin, "verdict": d_twin.verdict},
                          "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0158-probe1 " + json.dumps(checks))
            return 1
        print("SUCCESS:IMP-0158-probe1 unknown refused, first-party twin auto-admitted")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
