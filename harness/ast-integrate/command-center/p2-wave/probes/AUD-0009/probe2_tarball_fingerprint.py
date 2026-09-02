#!/usr/bin/env python3
"""Probe 2: content merkle of a vendored tree vs upstream tarball members.

An undeclared copy with no vendor/ marker must still match. A one-byte
mutant must not.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fingerprint import compare_tree_to_tarball, make_deterministic_tarball  # noqa: E402
from scan import live_vendor_inventory, repo_root  # noqa: E402


def write_upstream(src: Path) -> None:
    src.mkdir(parents=True)
    (src / "README.md").write_text(
        "# fixture-lib\nupstream pin for AUD-0009 probe 2\n", encoding="utf-8"
    )
    (src / "LICENSE").write_text(
        "MIT License\n\nCopyright (c) 2026 fixture-lib authors\n", encoding="utf-8"
    )
    (src / "src").mkdir()
    (src / "src" / "lib.py").write_text("VALUE = 7\n", encoding="utf-8")


def run_control() -> dict:
    with tempfile.TemporaryDirectory(prefix="aud0009-tar-") as tmp:
        tmp_p = Path(tmp)
        upstream = tmp_p / "upstream" / "fixture-lib-1.0.0"
        write_upstream(upstream)
        tar_bytes = make_deterministic_tarball(upstream)
        planted = tmp_p / "unmarked-copy" / "fixture-lib"
        planted.mkdir(parents=True)
        for rel, data in (
            ("README.md", (upstream / "README.md").read_bytes()),
            ("LICENSE", (upstream / "LICENSE").read_bytes()),
            ("src/lib.py", (upstream / "src" / "lib.py").read_bytes()),
        ):
            dest = planted / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        mutant = tmp_p / "mutant-copy" / "fixture-lib"
        mutant.mkdir(parents=True)
        for rel, data in (
            ("README.md", (upstream / "README.md").read_bytes()),
            ("LICENSE", (upstream / "LICENSE").read_bytes()),
            ("src/lib.py", b"VALUE = 8\n"),
        ):
            dest = mutant / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        good = compare_tree_to_tarball(planted, tar_bytes)
        bad = compare_tree_to_tarball(mutant, tar_bytes)
        undeclared_path = planted.as_posix()
        has_vendor_token = any(
            part in {"vendor", "third_party", "third-party", "_vendor", "vendored"}
            for part in planted.parts
        )
        fired_on_mutant = not bad["match"]
        silent_on_plant = good["match"]
        return {
            "planted_path_has_vendor_marker": has_vendor_token,
            "planted_match": good["match"],
            "mutant_match": bad["match"],
            "planted_tree_merkle": good["tree_merkle"],
            "tarball_member_merkle": good["tarball_member_merkle"],
            "tarball_sha256": good["tarball_sha256"],
            "mutant_tree_merkle": bad["tree_merkle"],
            "fired_on_mutant": fired_on_mutant,
            "silent_on_unmarked_plant": silent_on_plant,
            "control_pass": silent_on_plant and fired_on_mutant and not has_vendor_token,
            "undeclared_plant_parent": str(Path(undeclared_path).parent.name),
        }


def main() -> int:
    ctl = run_control()
    live = live_vendor_inventory(repo_root())
    out = {
        "probe": "probe2-tarball-content-fingerprint",
        "control": ctl,
        "live_vendor_trees": live,
    }
    print(json.dumps(out, sort_keys=True))
    if not ctl["control_pass"]:
        print(
            "FAILED:AUD-0009-probe2 unmarked plant did not match tarball "
            "or mutant was silent"
        )
        return 1
    print(
        "SUCCESS:AUD-0009-probe2 unmarked plant matched tarball; mutant mismatched; "
        f"live_vendor_trees={len(live)}"
    )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    raise SystemExit(main())
