#!/usr/bin/env python3
"""Named probe 1: index rebuilt from blobs is semantically equal to the original."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.storage import (  # noqa: E402
    IndexCorrupt,
    IndexMissing,
    RegistryStorage,
    indexes_semantically_equal,
)


def _plugin(name: str, version: str = "1.0.0") -> dict:
    return {
        "name": name,
        "source": f"./packages/{name}",
        "version": version,
        "license": "MIT",
        "keywords": ["probe1"],
        "skills": [],
        "channels": ["stable"],
        "provenance": {"origin": "probe1"},
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0068-p1-") as raw:
        store = RegistryStorage(raw)
        # Non-sorted insertion so a rebuild may differ in bytes.
        for name in ("omega-kit", "beta-kit", "kappa-kit"):
            store.put_package(_plugin(name, "2.0.0"), f"blob-{name}".encode())
        original = store.read_index()
        original_bytes = store.index_path.read_bytes()
        rebuilt = store.rebuild_from_blobs()
        rebuilt_bytes = store.index_path.read_bytes()
        equal = indexes_semantically_equal(original, rebuilt)
        byte_equal = original_bytes == rebuilt_bytes
        insert_order = [p["name"] for p in original["plugins"]]
        rebuilt_order = [p["name"] for p in rebuilt["plugins"]]

        store.index_path.write_bytes(b"{not-json")
        corrupt_raised = False
        try:
            store.read_index()
        except IndexCorrupt:
            corrupt_raised = True
        recovered = store.recover_index()
        recovered_equal = indexes_semantically_equal(original, recovered)

        store.index_path.unlink()
        missing_raised = False
        try:
            store.read_index()
        except IndexMissing:
            missing_raised = True
        recovered_lost = store.recover_index()
        lost_equal = indexes_semantically_equal(original, recovered_lost)

        payload = {
            "probe": "probe1-rebuild-from-blobs",
            "unit_id": "IMP-0068",
            "plugin_count": len(original["plugins"]),
            "insert_order": insert_order,
            "rebuilt_order": rebuilt_order,
            "semantically_equal": equal,
            "byte_equal": byte_equal,
            "corrupt_raised": corrupt_raised,
            "recovered_after_corrupt": recovered_equal,
            "missing_raised": missing_raised,
            "recovered_after_lost": lost_equal,
            "pass": bool(
                equal
                and len(original["plugins"]) == 3
                and corrupt_raised
                and recovered_equal
                and missing_raised
                and lost_equal
                and insert_order == ["omega-kit", "beta-kit", "kappa-kit"]
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["pass"]:
            print("FAILED:IMP-0068-probe1 rebuild equality or recovery")
            return 1
        print(
            "SUCCESS:IMP-0068-probe1 rebuild-from-blobs semantically equal; "
            "corrupt and lost index recovered"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
