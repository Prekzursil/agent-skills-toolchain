#!/usr/bin/env python3
"""IMP-0023 probe1: clean install into a throwaway HOME matches the projection.

Independent signals:
  * live path set equals predicted_live_paths(projection) (set equality)
  * every live file's sha256 equals the payload source bytes recomputed by an
    independent rglob walk (not by trusting the installer's return value)
  * second install is a no-op: status=already-current, mtime+hash census unchanged
Planted negative control: a corrupted projection entry must fail set equality.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.install import (  # noqa: E402
    InstallResult,
    install_plugin,
    live_file_census,
    mtime_hash_census,
    predicted_live_paths,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def build_payload(root: Path) -> Path:
    files = {
        "README.md": "# demo plugin\n",
        "hooks/pre.json": '{"on": "pre"}\n',
        "plugin.json": '{"name": "demo-plugin", "version": "1"}\n',
        "skills/alpha/SKILL.md": "# alpha v1\nbody-one\n",
        "skills/beta/SKILL.md": "# beta v1\nbody-two\n",
    }
    root.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
    return root


def projection_for(payload: Path) -> dict:
    entries = []
    for path in sorted(payload.rglob("*")):
        if path.is_file():
            rel = path.relative_to(payload).as_posix()
            entries.append({"source": rel, "live": rel, "sha256": sha(path)})
    return {"plugin_id": "demo-plugin", "entries": entries}


def independent_walk(payload: Path) -> dict[str, str]:
    """Recompute payload hashes by rglob, not via the projection map."""
    return {
        p.relative_to(payload).as_posix(): sha(p)
        for p in sorted(payload.rglob("*"))
        if p.is_file()
    }


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0023-p1-"))
    try:
        payload = build_payload(tmp / "payload")
        projection = projection_for(payload)
        home = tmp / "home"
        res = install_plugin(home=home, payload=payload, projection=projection)
        assert isinstance(res, InstallResult) and res.status == "installed" and res.mutated

        dest = home / "plugins" / "demo-plugin"
        live = live_file_census(dest)
        predicted = predicted_live_paths(projection)
        set_equal = set(live) == predicted

        walked = independent_walk(payload)
        payload_hashes_match = live == walked
        walked_payload_hashes_match = set_equal and all(
            live.get(rel) == walked.get(rel) for rel in predicted
        )

        census_before = mtime_hash_census(dest)
        second = install_plugin(home=home, payload=payload, projection=projection)
        census_after = mtime_hash_census(dest)
        idempotent = (
            second.status == "already-current"
            and second.mutated is False
            and census_before == census_after
        )

        # Planted negative control: a wrong projection must not match the live set.
        bad_projection = {
            "plugin_id": "demo-plugin",
            "entries": [{"source": "README.md", "live": "GHOST.md", "sha256": "x"}],
        }
        bad_predicted = predicted_live_paths(bad_projection)
        control_found = bad_predicted != set(live)

        passed = bool(
            set_equal
            and payload_hashes_match
            and walked_payload_hashes_match
            and idempotent
            and control_found
        )
        out = {
            "unit_id": "IMP-0023",
            "probe": "probe1-clean-install",
            "file_count": len(live),
            "live_paths": sorted(live),
            "predicted_paths": sorted(predicted),
            "set_equal": set_equal,
            "payload_hashes_match": payload_hashes_match,
            "walked_payload_hashes_match": walked_payload_hashes_match,
            "second_install_status": second.status,
            "mtime_hash_census_unchanged": census_before == census_after,
            "census_entries": len(census_after),
            "dirty_control_found": control_found,
            "pass": passed,
        }
        print(json.dumps(out, sort_keys=True))
        print(
            f"set_equal={set_equal} files={len(live)} idempotent={idempotent} "
            f"census_entries={len(census_after)}"
        )
        if not passed:
            print("FAILED:IMP-0023-probe1 clean install mismatch")
            return 1
        print("SUCCESS:IMP-0023-probe1 clean install matches projection")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
