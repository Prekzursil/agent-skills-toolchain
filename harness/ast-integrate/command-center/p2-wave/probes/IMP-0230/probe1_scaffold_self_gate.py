#!/usr/bin/env python3
"""Named probe 1: scaffold output passes its own gate unmodified (self-application).

Two signals: (1) in-memory scaffold_blueprint() registers with zero violations;
(2) bytes written to disk and loaded back without editing also register, and
the declared hermetic smoke test passes.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _lib import REPO, SENTINEL, TOOLS, load_receipt  # noqa: E402

sys.path.insert(0, str(TOOLS))
from blueprint_contract import (  # noqa: E402
    dump_blueprint,
    emit_scaffold,
    load_blueprint,
    register_blueprint,
    run_declared_smoke,
    scaffold_blueprint,
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def main() -> int:
    load_receipt()
    live = scaffold_blueprint()
    dumped = dump_blueprint(live)
    round_tripped = json.loads(dumped)
    if round_tripped != live:
        print("FAILED:IMP-0230-probe1 scaffold is not JSON-round-trippable")
        return 1
    r_mem = register_blueprint(live)
    if not r_mem.ok:
        print("FAILED:IMP-0230-probe1 in-memory scaffold rejected")
        print(json.dumps(r_mem.as_dict(), indent=2))
        return 1
    r_rt = register_blueprint(round_tripped)
    if not r_rt.ok:
        print("FAILED:IMP-0230-probe1 JSON-round-trip scaffold rejected")
        print(json.dumps(r_rt.as_dict(), indent=2))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0230-p1-") as tmp:
        dest = Path(tmp) / "skel"
        emit_scaffold(dest)
        raw_path = dest / "blueprint.json"
        raw = raw_path.read_bytes()
        if b"\r\n" in raw:
            print("FAILED:IMP-0230-probe1 scaffold bytes contain CRLF")
            return 1
        loaded = load_blueprint(dest)
        if loaded != live:
            print("FAILED:IMP-0230-probe1 on-disk scaffold differs from in-memory")
            return 1
        r_disk = register_blueprint(loaded)
        if not r_disk.ok:
            print("FAILED:IMP-0230-probe1 unmodified on-disk scaffold rejected")
            print(json.dumps(r_disk.as_dict(), indent=2))
            return 1

    ok_smoke, failed = run_declared_smoke(live)
    if not ok_smoke:
        print(f"FAILED:IMP-0230-probe1 smoke asserts failed: {failed}")
        return 1

    twice = scaffold_blueprint()
    if twice != live:
        print("FAILED:IMP-0230-probe1 scaffold is not deterministic")
        return 1

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-scaffold-self-gate",
                "unit_id": "IMP-0230",
                "registered_unmodified": True,
                "json_round_trip": True,
                "disk_unmodified": True,
                "smoke_ok": True,
                "scaffold_sha256": _digest(dumped),
                "violation_count": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"{SENTINEL}-probe1 scaffold output passes its own gate unmodified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
