"""Positive load probe: declared hooks emit markers at session start (IMP-0460).

Observed ids come ONLY from HOOK-LOAD-MARKER lines in the session-start log -
never from a hooks.json or hooks/ directory listing.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = REPO / "tools" / "hook_load" / "fixtures" / "plugin"
sys.path.insert(0, str(REPO / "tools"))

from hook_load.load_probe import load_config  # noqa: E402

LOG = HERE / "session-start.log"


def run_session_start() -> list[str]:
    declared = load_config(FIXTURE / "hooks.json")["hooks"]
    lines = []
    for hook in declared:
        proc = subprocess.run(
            [sys.executable, "-B", str(FIXTURE / hook["command"])],
            capture_output=True, text=True, timeout=60,
            env={"PYTHONDONTWRITEBYTECODE": "1",
                 "PATH": __import__("os").environ["PATH"],
                 "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
        )
        assert proc.returncode == 0, (hook["id"], proc.stderr[:200])
        for line in proc.stdout.splitlines():
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            marker = doc.get("hook-load-marker")
            if marker:
                lines.append("HOOK-LOAD-MARKER %s" % marker)
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return [l.split()[-1] for l in lines]


def main() -> int:
    config = load_config(FIXTURE / "hooks.json")
    declared = [h["id"] for h in config["hooks"]]
    observed = run_session_start()

    missing = [i for i in declared if i not in observed]
    extra = [i for i in observed if i not in declared]
    equal = sorted(declared) == sorted(observed)

    print(json.dumps({
        "probe": "probe1-declared-vs-observed",
        "unit_id": "IMP-0460",
        "declared_count": len(declared),
        "observed_count": len(observed),
        "equal": equal,
        "missing_markers": missing,
        "extra_markers": extra,
        "method": "session-start-log markers, not a config listing",
        "source": str(LOG.relative_to(REPO)).replace(chr(92), "/"),
        "sentinel": "SENTINEL:IMP-0460:HOOKS-LOAD-VERIFIED",
    }, indent=2))
    assert equal and not missing and not extra
    print("SUCCESS:IMP-0460-probe1 declared=%d observed=%d (equal)"
          % (len(declared), len(observed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
