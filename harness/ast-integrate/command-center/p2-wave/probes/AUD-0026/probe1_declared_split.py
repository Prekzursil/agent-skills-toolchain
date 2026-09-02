#!/usr/bin/env python3
"""Named probe 1: declared prod/dev split in packaging manifests.

Independent of probe 2's import graph. This probe parses pyproject.toml,
package.json, and requirements*.txt into runtime vs development classes and
checks the fixture split parser (pytest is dev, rich is runtime).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import split as S  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0026-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aud0026-p1-") as raw:
        control = S.run_control(Path(raw) / "fx")
    if not control["split_parser_ok"]:
        return fail(
            "fixture split parser did not place rich in runtime and pytest in dev"
        )
    if not control["pass"]:
        return fail("fixture control did not pass both-states (split+import)")

    plugin = S.live_plugin_scan()
    census = S.repo_manifest_census()
    exclusion = S.load_exclusion_rules()

    payload = {
        "probe": "probe1-declared-prod-dev-split",
        "unit_id": "AUD-0026",
        "plugin_root": plugin["plugin_root"],
        "plugin_root_exists": plugin["plugin_root_exists"],
        "plugin_manifest_absent": plugin["manifest_absent"],
        "plugin_manifests": plugin["manifests"],
        "plugin_runtime": plugin["runtime"],
        "plugin_dev": plugin["dev"],
        "consumer_forced": plugin["consumer_forced"],
        "dev_only": plugin["dev_only"],
        "packaging_exclude": plugin["packaging_exclude"],
        "package_gate": exclusion,
        "repo_manifests_outside_probes": census,
        "repo_manifest_count": len(census),
        "control_split_parser_ok": control["split_parser_ok"],
        "control_declared_runtime": control["declared_runtime"],
        "control_declared_dev": control["declared_dev"],
        "control_packaging_exclude": control["packaging_exclude"],
        "pass": True,
    }
    (HERE / "probe1-declared-split.json").write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0026-probe1 declared split "
        f"plugin_manifest_absent={plugin['manifest_absent']} "
        f"consumer_forced={plugin['consumer_forced']} "
        f"dev_only={plugin['dev_only']} "
        f"repo_manifests={len(census)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
