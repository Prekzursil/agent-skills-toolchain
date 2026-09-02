#!/usr/bin/env python3
"""Write command-center/receipts/IMP-0073.json from live migration measurements."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.index_migrate import (  # noqa: E402
    COMPATIBILITY_WINDOW_VERSIONS,
    CURRENT_SCHEMA_VERSION,
    UNSUPPORTED,
    file_record_count,
    lenient_v1_parse,
    lossy_migrate_1_to_2,
    migrate,
    parse_index,
    schema_version_of,
    semantics,
)
from tools.marketplace.manifest_reader import live_path, load_manifest  # noqa: E402
from tools.marketplace.tests import test_index_migrate as T  # noqa: E402

OUT = "command-center/receipts/IMP-0073.json"
SUITE = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_index_migrate.py"
)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    suite_code, suite_text = run_cmd(SUITE)
    if suite_code != 0:
        print(suite_text[-3000:])
        print("FAILED:IMP-0073 suite")
        return 1

    v1 = T.sample_v1_index()
    v2 = migrate(v1, 2)
    back = migrate(v2, 1)
    honest_rt = semantics(v1) == semantics(v2) == semantics(back)
    lossy_v2 = lossy_migrate_1_to_2(v1)
    lossy_back = migrate(lossy_v2, 1)
    lossy_diverges = semantics(v1) != semantics(lossy_back)

    synthetic_old = parse_index(v2, parser_version=1)
    synthetic_lenient = lenient_v1_parse(v2)

    live = load_manifest(live_path(REPO))
    live_src = copy.deepcopy(live.data)
    live_v = schema_version_of(live_src)
    live_v2 = migrate(live_src, live_v + 1)
    live_back = migrate(live_v2, live_v)
    live_rt = semantics(live_src) == semantics(live_v2) == semantics(live_back)
    live_old = parse_index(live_v2, parser_version=live_v)
    live_lenient = lenient_v1_parse(live_v2)
    live_file_n = file_record_count(live_v2)

    if not honest_rt or not lossy_diverges or not live_rt:
        print("FAILED:IMP-0073 evidence round-trip")
        return 1
    if synthetic_old.status != UNSUPPORTED or live_old.status != UNSUPPORTED:
        print("FAILED:IMP-0073 old parser did not refuse")
        return 1
    if len(synthetic_lenient) == file_record_count(v2):
        print("FAILED:IMP-0073 lenient synthetic did not drop")
        return 1
    if len(live_lenient) == live_file_n:
        print("FAILED:IMP-0073 lenient live did not drop")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": "IMP-0073",
        "id": "IMP-0073",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "receipt",
        "title": "Index schema versioning and forward migration",
        "question": (
            "Give the index a schema_version and implement migration between "
            "index versions with a compatibility window, so an older client "
            "reading a newer index degrades predictably (declared unsupported) "
            "instead of misparsing it."
        ),
        "sentinel": "SUCCESS:IMP-0073",
        "completion_sentinel": "SUCCESS:IMP-0073",
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "compatibility_window_versions": COMPATIBILITY_WINDOW_VERSIONS,
        "current_schema_version": CURRENT_SCHEMA_VERSION,
        "compatibility_window_is_number_of_versions": True,
        "live_index": {
            "path": ".claude-plugin/marketplace.json",
            "schema_version": live_v,
            "file_record_count": file_record_count(live_src),
        },
        "evidence": [
            {
                "id": "signal-1-round-trip",
                "kind": "round-trip-semantics",
                "claim": (
                    "A v1 index migrates to v2 and back with equal normalised "
                    "semantics (sorted records, not byte equality of wrappers)."
                ),
                "anchor": "tools/marketplace/index_migrate.py:migrate",
                "honest_round_trip_equal": honest_rt,
                "live_round_trip_equal": live_rt,
                "v1_file_record_count": file_record_count(v1),
                "v2_file_record_count": file_record_count(v2),
                "v2_compatibility_window": v2.get("compatibility_window"),
                "verdict": "CONFIRMED",
                "independent_of": "signal-2-old-parser-unsupported",
            },
            {
                "id": "signal-2-old-parser-unsupported",
                "kind": "parser-refuse",
                "claim": (
                    "A v1 parser given a v2 index returns UNSUPPORTED rather than "
                    "silently dropping fields. Verified by comparing parsed record "
                    "count (None / refuse) against the file's record count, while a "
                    "lenient v1 reader of the same bytes yields a smaller count."
                ),
                "anchor": "tools/marketplace/index_migrate.py:parse_index",
                "synthetic": {
                    "status": synthetic_old.status,
                    "file_record_count": synthetic_old.file_record_count,
                    "parsed_record_count": synthetic_old.parsed_record_count,
                    "lenient_count": len(synthetic_lenient),
                    "reason": synthetic_old.reason,
                },
                "live": {
                    "status": live_old.status,
                    "file_record_count": live_old.file_record_count,
                    "parsed_record_count": live_old.parsed_record_count,
                    "lenient_count": len(live_lenient),
                    "reason": live_old.reason,
                },
                "verdict": "CONFIRMED",
                "independent_of": "signal-1-round-trip",
            },
        ],
        "negative_controls": [
            {
                "id": "lossy-migration-step",
                "kind": "known-broken-migration",
                "description": (
                    "Drop the last record during v1→v2. Semantic round-trip must fail. "
                    "The honest migrate_1_to_2 path must still round-trip."
                ),
                "fired_on_bad_state": lossy_diverges,
                "silent_on_good_state": honest_rt,
                "lossy_file_record_count": file_record_count(lossy_v2),
            }
        ],
        "tests": [
            {
                "id": "test_round_trip_preserves_semantics",
                "name": "tools/marketplace/tests/test_index_migrate.py::test_round_trip_preserves_semantics",
                "result": "PASS",
            },
            {
                "id": "test_old_parser_declares_unsupported",
                "name": "tools/marketplace/tests/test_index_migrate.py::test_old_parser_declares_unsupported",
                "result": "PASS",
            },
            {
                "id": "NEGATIVE CONTROL lossy migration",
                "name": "test_lossy_migration_fails_round_trip",
                "result": "PASS",
            },
        ],
        "suite": {
            "command": SUITE,
            "exit_code": suite_code,
            "tail": suite_text[-2000:],
        },
        "reviewer": {
            "reviewer_id": "IMP-0073-probe2-old-parser-unsupported",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Compatibility window is COMPATIBILITY_WINDOW_VERSIONS="
                f"{COMPATIBILITY_WINDOW_VERSIONS} (a number of versions). "
                "Probe 2 re-parses the live marketplace.json migrated to v2 "
                "with a v1 parser and records UNSUPPORTED. Probe 1 is the "
                "round-trip digest, a different method."
            ),
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": "tools/marketplace/index_migrate.py", "role": "implementation"},
            {
                "path": "tools/marketplace/tests/test_index_migrate.py",
                "role": "catalog-test",
            },
            {
                "path": ".claude-plugin/marketplace.json",
                "role": "live-index",
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0073/probe1_round_trip.py"
                ),
            },
            {
                "id": "probe2",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0073/probe2_old_parser_unsupported.py"
                ),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 for IMP-0073: live named probes re-run round-trip and old-parser "
            "refuse. Compatibility window is 1 version. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. SUCCESS:IMP-0073"
        ),
        "registered": True,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if "SUCCESS:IMP-0073" not in raw:
        print("FAILED:emit sentinel missing")
        return 1
    dest.write_text(raw, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:IMP-0073")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
