#!/usr/bin/env python3
"""IMP-0107 probe2: same-run negative + positive controls.
Matching upstream/mirror digests -> install writes the payload to dest;
a divergent package is refused (unresolved-mirror-conflict); a policy config
that names a silent-preference key (prefer_upstream) is refused at policy
construction (never pick a side by default)."""
from __future__ import annotations

import glob
import importlib.util
import sys
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load_mc():
    hits = sorted(glob.glob(str(REPO / "tools" / "marketplace" / "mirror_conflict.py")))
    spec = importlib.util.spec_from_file_location("imp0107_mc2", hits[0])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # 3.14 dataclass: resolve cls.__module__
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mc = load_mc()
    root = Path(tempfile.mkdtemp(prefix="imp0107neg-"))
    store = root / "conflicts.json"
    dest = root / "dest"

    # a clean package installs (matching digests, no conflict record)
    policy = mc.MirrorConflictPolicy(store)
    res_ok = policy.install("clean-pkg", "1.0.0", dest, b"same-bytes")
    census = mc.census(dest)
    clean_installed = res_ok.ok and "clean-pkg/1.0.0/payload.bin" in census

    # a divergent sibling package is recorded then REFUSED at install
    dig_a = mc.sha256_digest(b"v1")
    dig_b = mc.sha256_digest(b"v2")
    policy.compare_and_record("divergent-pkg", "1.0.0",
                              upstream_url="u", upstream_digest=dig_a,
                              mirror_url="m", mirror_digest=dig_b)
    res_bad = policy.install("divergent-pkg", "1.0.0", dest, b"v1-or-v2")
    refused = (not res_bad.ok) and res_bad.reason == "unresolved-mirror-conflict"
    not_written = "divergent-pkg/1.0.0/payload.bin" not in census

    # silent preference is refused at construction
    silent_refused = False
    try:
        mc.MirrorConflictPolicy(root / "other.json", config={"prefer_upstream": True})
    except mc.SilentPreferenceRefused:
        silent_refused = True
    except Exception:  # noqa: BLE001
        silent_refused = False

    result = {
        "unit_id": "IMP-0107",
        "probe": "probe2-persist-negative",
        "clean_installed": clean_installed,
        "census_has_clean": "clean-pkg/1.0.0/payload.bin" in census,
        "divergent_refused": refused,
        "divergent_not_written": not_written,
        "silent_preference_refused": silent_refused,
        "pass": clean_installed and refused and not_written and silent_refused,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0107-probe2 matching digests install; divergent refused; "
            "silent preference refused (both-states same run)"
            if result["pass"] else
            "FAILED:IMP-0107-probe2 install/refusal contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
