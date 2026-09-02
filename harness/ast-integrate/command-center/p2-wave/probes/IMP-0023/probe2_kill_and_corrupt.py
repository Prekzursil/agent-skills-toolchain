#!/usr/bin/env python3
"""Probe 2: kill mid-activate leaves one legal state; corrupt stage refuses.

Independent of probe 1: fresh throwaway HOME, independent census of payload
bytes, SIGKILL of a real installer subprocess (not an in-process exception).

Both-states control: a mixed tree is classified MIXED, so the inspector
cannot rubber-stamp every tree as OLD or NEW.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.install import (  # noqa: E402
    InstallError,
    classify_live_state,
    install_plugin,
    live_file_census,
    plugin_root,
    resolve_live,
)
from plugin.tests.harness import (  # noqa: E402
    expected_census,
    kill_mid_activate,
    projection_for,
    v1_files,
    v2_files,
    write_projection,
    write_tree,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0023-p2-") as tmp:
        tmp_path = Path(tmp)
        home = tmp_path / "home"
        p1 = tmp_path / "payload-v1"
        p2 = tmp_path / "payload-v2"
        write_tree(p1, v1_files())
        write_tree(p2, v2_files())
        proj1 = projection_for(p1)
        proj2 = projection_for(p2)
        proj2_path = write_projection(tmp_path / "proj-v2.json", proj2)
        old_expected = expected_census(v1_files())
        new_expected = expected_census(v2_files())
        if old_expected == new_expected:
            print("FAILED:IMP-0023-probe2 v1 and v2 censuses are identical")
            return 1

        first = install_plugin(home=home, payload=p1, projection=proj1)
        if first.status != "installed":
            print(f"FAILED:IMP-0023-probe2 v1 install {first.status}")
            return 1
        root = plugin_root(home, "demo-plugin")
        old_live = live_file_census(root)
        if old_live != old_expected:
            print("FAILED:IMP-0023-probe2 v1 live census != payload census")
            return 1

        pause = tmp_path / "pause-before-swap"
        rc = kill_mid_activate(home, p2, proj2_path, pause)
        if rc == 0:
            print("FAILED:IMP-0023-probe2 killed installer reported success")
            return 1
        state_after_kill = classify_live_state(root, old_expected, new_expected)
        if state_after_kill not in {"OLD", "NEW"}:
            print(
                json.dumps(
                    {
                        "error": "invalid-state-after-kill",
                        "state": state_after_kill,
                        "live": live_file_census(root),
                    },
                    sort_keys=True,
                )
            )
            return 1
        if state_after_kill != "OLD":
            print(f"FAILED:IMP-0023-probe2 expected OLD after pre-swap kill, got {state_after_kill}")
            return 1
        if live_file_census(root) != old_expected:
            print("FAILED:IMP-0023-probe2 live bytes drifted across SIGKILL")
            return 1

        completed = install_plugin(home=home, payload=p2, projection=proj2)
        if completed.status != "installed":
            print(f"FAILED:IMP-0023-probe2 v2 install {completed.status}")
            return 1
        if classify_live_state(root, old_expected, new_expected) != "NEW":
            print("FAILED:IMP-0023-probe2 completed upgrade is not NEW")
            return 1

        # Restore v1 as the live tree, then refuse a corrupted v2 stage.
        home_c = tmp_path / "home-corrupt"
        install_plugin(home=home_c, payload=p1, projection=proj1)
        root_c = plugin_root(home_c, "demo-plugin")
        before = live_file_census(root_c)
        gen_before = resolve_live(root_c)
        if gen_before is None:
            print("FAILED:IMP-0023-probe2 corrupt-control missing live tree")
            return 1

        def corrupt(staging: Path) -> None:
            target = staging / "skills/alpha/SKILL.md"
            target.write_text(target.read_text(encoding="utf-8") + "CORRUPT\n", encoding="utf-8")

        refused = False
        code = None
        try:
            install_plugin(
                home=home_c, payload=p2, projection=proj2, after_stage=corrupt
            )
        except InstallError as exc:
            refused = True
            code = exc.code
        if not refused or code != "verify-digest":
            print(f"FAILED:IMP-0023-probe2 corrupt stage not refused code={code}")
            return 1
        if live_file_census(root_c) != before:
            print("FAILED:IMP-0023-probe2 corrupt stage mutated live tree")
            return 1
        if resolve_live(root_c) != gen_before:
            print("FAILED:IMP-0023-probe2 live generation changed after refuse")
            return 1

        # Inspector both-states: mixed must not be accepted as OLD or NEW.
        mixed_home = tmp_path / "mixed-home"
        mixed_root = plugin_root(mixed_home, "demo-plugin")
        mixed_live = mixed_root / "current-dir"
        write_tree(mixed_live, v1_files())
        (mixed_live / "skills/gamma/SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (mixed_live / "skills/gamma/SKILL.md").write_text("# gamma new in v2\n", encoding="utf-8")
        (mixed_root / "current").symlink_to(mixed_live.name)
        mixed_state = classify_live_state(mixed_root, old_expected, new_expected)
        if mixed_state != "MIXED":
            print(f"FAILED:IMP-0023-probe2 inspector silent on mixed tree: {mixed_state}")
            return 1

        summary = {
            "probe": "probe2-kill-and-corrupt",
            "unit_id": "IMP-0023",
            "kill_returncode": rc,
            "state_after_kill": state_after_kill,
            "completed_state": "NEW",
            "corrupt_refused": True,
            "corrupt_code": code,
            "inspector_mixed": mixed_state,
            "pass": True,
        }
        print(json.dumps(summary, sort_keys=True))
        print(
            f"kill_state={state_after_kill} corrupt_refused=True "
            f"mixed={mixed_state} completed=NEW"
        )
        print("SUCCESS:IMP-0023-probe2 kill mid-activate and corrupt-stage refuse")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
