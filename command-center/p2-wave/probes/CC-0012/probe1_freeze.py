#!/usr/bin/env python3
"""CC-0012 probe: freeze gate both-states + migration round-trip."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))
import schema_freeze as sf  # noqa: E402


def main() -> int:
    PROBE.mkdir(parents=True, exist_ok=True)
    tests = REPO / "tools/command-center/tests/test_schema_freeze.py"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests), "-q", "--tb=line"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    pytest_out = (proc.stdout or "") + (proc.stderr or "")
    (PROBE / "pytest-freeze.out").write_text(pytest_out, encoding="utf-8")

    freeze = sf.load_freeze(REPO / "command-center/SCHEMA-FREEZE.json")
    migration = sf.load_migration(
        REPO / "command-center/schema/migrations", "m001-receipt-core-example"
    )
    sample = {"schema_version": 1, "legacy_note": "pre-freeze", "keep": True}
    (PROBE / "roundtrip-sample.json").write_text(
        json.dumps(sample, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rt = sf.roundtrip_ok(sample, migration)

    red = sf.check_edit(
        freeze,
        rel_path="command-center/schema/receipt.schema.json",
        old_sha256="11" * 32,
        new_sha256="22" * 32,
        version_bumped=False,
        migration_id=None,
        migration_roundtrip_ok=False,
    )
    green = sf.check_edit(
        freeze,
        rel_path="command-center/schema/receipt.schema.json",
        old_sha256="11" * 32,
        new_sha256="22" * 32,
        version_bumped=True,
        migration_id="m001-receipt-core-example",
        migration_roundtrip_ok=rt,
    )
    silent = sf.check_edit(
        freeze,
        rel_path="docs/plans/README.md",
        old_sha256="11" * 32,
        new_sha256="22" * 32,
        version_bumped=False,
        migration_id=None,
        migration_roundtrip_ok=False,
    )

    summary = {
        "probe": "CC-0012-freeze",
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pytest_rc": proc.returncode,
        "activation_commit": freeze.get("activation_commit"),
        "activated": freeze.get("activated"),
        "frozen_path_count": len(freeze.get("frozen_paths") or []),
        "roundtrip_ok": rt,
        "unversioned_edit": red,
        "versioned_edit": green,
        "non_frozen_edit": silent,
        "ok": (
            proc.returncode == 0
            and freeze.get("activated") is True
            and bool(freeze.get("activation_commit"))
            and rt
            and red["verdict"] == "RED"
            and green["verdict"] == "GREEN"
            and silent["verdict"] == "SILENT"
        ),
    }
    (PROBE / "probe1-freeze-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    raw = (
        f"PROBE=CC-0012-freeze\n"
        f"PYTEST_RC={proc.returncode}\n"
        f"ACTIVATED={freeze.get('activated')}\n"
        f"ACTIVATION_COMMIT={freeze.get('activation_commit')}\n"
        f"ROUNDTRIP_OK={rt}\n"
        f"UNVERSIONED={red['verdict']}\n"
        f"VERSIONED={green['verdict']}\n"
        f"NON_FROZEN={silent['verdict']}\n"
        f"PYTEST_TAIL=\n{pytest_out[-3000:]}\n"
        f"VERDICT={'PASS' if summary['ok'] else 'FAIL'}\n"
    )
    (PROBE / "probe1-freeze.raw.txt").write_text(raw, encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
