#!/usr/bin/env python3
"""IMP-0158 probe2 (verifier): tier assignment is reproducible — the same
evidence yields the same tier and the same evidence digest across two
SUBPROCESSES with distinct injected clocks."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

CHILD = (
    "import json,sys,datetime;"
    "sys.path.insert(0, sys.argv[1]);"
    "from marketplace.trust_tiers import assign_tier, decide_admission;"
    "ev = json.loads(sys.argv[2]);"
    "a = assign_tier({'trust_evidence': ev});"
    "d = decide_admission({'trust_evidence': ev});"
    "sys.stdout.write(json.dumps({'clock': datetime.datetime.now().isoformat(), 'tier': a.tier, 'digest': a.evidence_sha256, 'verdict': d.verdict}))\n"
)

EV = {"publisher_id": "acme", "publisher_repo": "acme/widgets", "identity_verified": True, "signature_verified": True}


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0158-p2-"))
    try:
        outputs = []
        for i in range(2):
            env = {"PYTHONDONTWRITEBYTECODE": "1", "PATH": "", "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", ""), "SOURCE_DATE_EPOCH": str(1700000000 + i * 98765)}
            p = subprocess.run([sys.executable, "-B", "-c", CHILD, str(REPO), json.dumps(EV)], capture_output=True, text=True, timeout=120, env=env, cwd=str(work))
            if p.returncode != 0:
                print("FAILED:IMP-0158-probe2 child rc=%d %s" % (p.returncode, p.stderr[-300:]))
                return 1
            outputs.append(json.loads(p.stdout))
        same = outputs[0]["tier"] == outputs[1]["tier"] and outputs[0]["digest"] == outputs[1]["digest"] and outputs[0]["verdict"] == outputs[1]["verdict"]
        clocks_differ = outputs[0]["clock"] != outputs[1]["clock"]
        checks = {"two_runs_same_tier_and_digest": same, "injected_clocks_differ": clocks_differ}
        print(json.dumps({"runs": outputs, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0158-probe2 nondeterministic tier assignment")
            return 1
        print("SUCCESS:IMP-0158-probe2 tier assignment reproducible across runs with different clocks")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
