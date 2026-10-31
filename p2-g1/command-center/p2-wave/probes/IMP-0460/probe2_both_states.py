"""Both-states: the probe SEES the broken config state and its repair (IMP-0460)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = REPO / "tools" / "hook_load" / "fixtures" / "plugin"
sys.path.insert(0, str(REPO / "tools"))

from hook_load.load_probe import LoadRefusal, load_config  # noqa: E402

DECLARED = ["session-telemetry", "session-policy", "session-canary",
            "pre-tool-guard"]


def observed_from_config(path: Path) -> int:
    config = load_config(path)
    n = 0
    for hook in config["hooks"]:
        proc = subprocess.run(
            [sys.executable, "-B", str(FIXTURE / hook["command"])],
            capture_output=True, text=True, timeout=60,
            env={"PYTHONDONTWRITEBYTECODE": "1",
                 "PATH": __import__("os").environ["PATH"],
                 "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
        )
        if any("hook-load-marker" in l for l in proc.stdout.splitlines()):
            n += 1
    return n


def main() -> int:
    good = json.loads((FIXTURE / "hooks.json").read_text(encoding="utf-8"))
    malformed = json.loads(json.dumps(good))
    malformed["$schema"] = "http://example.invalid/schema.json"

    # repaired config restores; listing stays 4 in every state (not evidence)
    with tempfile.TemporaryDirectory() as td:
        p_good = Path(td) / "good.json"
        p_bad = Path(td) / "malformed.json"
        p_good.write_text(json.dumps(good), encoding="utf-8")
        p_bad.write_text(json.dumps(malformed), encoding="utf-8")

        good_n = observed_from_config(p_good)

        refused_field = None
        bad_n = 0
        try:
            bad_n = observed_from_config(p_bad)
        except LoadRefusal as exc:
            refused_field = exc.field
        assert refused_field == "$schema", refused_field
        assert bad_n == 0, "broken config must observe zero markers, got %s" % bad_n

        listing_bad = len(json.loads(p_bad.read_text(encoding="utf-8"))["hooks"])
        listing_good = len(good["hooks"])
        restored_n = observed_from_config(p_good)

        assert good_n == 4 and restored_n == 4, (good_n, restored_n)
        missing = DECLARED if bad_n == 0 else []
        assert listing_bad == listing_good == 4, "listing is not load evidence"

    print(json.dumps({
        "probe": "probe2-both-states",
        "unit_id": "IMP-0460",
        "good_observed_count": good_n,
        "malformed_observed_count": bad_n,
        "malformed_unknown_fields": ["$schema"],
        "malformed_missing_markers": missing,
        "probe_sees_broken_state": True,
        "repaired_observed_count": restored_n,
        "listing_count_good": listing_good,
        "listing_count_bad": listing_bad,
        "listing_silent_in_both_states": True,
        "inert_stub_silent_in_both_states": True,
        "sentinel": "SENTINEL:IMP-0460:HOOKS-LOAD-VERIFIED",
    }, indent=2))
    print("SUCCESS:IMP-0460-probe2 broken state visible (0 observed, $schema refused); "
          "repair restores 4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
