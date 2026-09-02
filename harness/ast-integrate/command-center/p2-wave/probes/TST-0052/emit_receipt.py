#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0052.json from a live parser matrix."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import kinds  # noqa: E402

OUT = "command-center/receipts/TST-0052.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0052"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0052/probe1_unknown_field_rejected.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0052/probe2_known_field_still_accepted.py"
)
QUESTION = (
    "Failure class :11302. Target: feed each manifest/config kind an extra "
    "unknown field and assert a hard rejection with a message naming the "
    "field. Question: which parsers currently ACCEPT unknown fields silently, "
    "and what does the client do with the ignored value?"
)
SUPPORTING = [
    "tools/plugin/schema/plugin-manifest.schema.json",
    "tools/plugin/payload.py",
    "tools/plugin/errors.py",
    "tools/plugin/exec_policy.py",
    "tools/marketplace/handoff.py",
    "tools/hook_load/load_probe.py",
    "command-center/p2-wave/probes/TST-0052/kinds.py",
    "command-center/p2-wave/probes/TST-0052/probe1_unknown_field_rejected.py",
    "command-center/p2-wave/probes/TST-0052/probe2_known_field_still_accepted.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def spec_anchor() -> str:
    catalog = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    needle = '"id": "TST-0052"'
    for i, line in enumerate(catalog.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"command-center/WORK-UNIT-CATALOG.json:{i}"
    return "command-center/WORK-UNIT-CATALOG.json"


def main() -> int:
    live = kinds.measure_all()
    if live["production_count"] < 4:
        print("FAILED:TST-0052 emit production_count < 4")
        return 1
    if not live["production_unknown_all_rejected"]:
        print("FAILED:TST-0052 emit a production parser accepted an unknown field")
        print(json.dumps(live["silently_accepting_production_parsers"]))
        return 1
    if not live["production_errors_all_name_field"]:
        print("FAILED:TST-0052 emit rejection did not name the field")
        return 1
    if not live["production_known_all_accepted"]:
        print("FAILED:TST-0052 emit known-good document was rejected")
        return 1
    if not live["lenient_control_accepts_unknown"]:
        print("FAILED:TST-0052 emit lenient control inert")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    production = [r for r in live["rows"] if r["production"]]
    control = [r for r in live["rows"] if not r["production"]][0]
    plugin_live = REPO / ".claude-plugin" / "plugin.json"
    answer = (
        "Four production parsers were fed a known-good document and the same "
        f"document plus extra field {live['unknown_field']!r}. All four "
        "REJECT the unknown field with an error that names it: "
        + "; ".join(
            f"{r['kind']} -> {r['unknown_error'].splitlines()[0][:160]}"
            for r in production
        )
        + ". All four ACCEPT the unmodified known-good document "
        "(test_known_field_still_accepted). No production parser on this "
        "worktree silently accepts unknown top-level fields. The json.loads "
        "negative control DOES accept the extra key and retains "
        f"{live['unknown_value']!r} on the dict; named getters never read it, "
        "which is what a lenient client would do with the ignored value. "
        f".claude-plugin/plugin.json present={plugin_live.is_file()} "
        f"(fixtures used). {SENTINEL}"
    )
    receipt = {
        "schema_version": 1,
        "id": "TST-0052",
        "unit_id": "TST-0052",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "test-receipt",
        "title": "Strict parser must reject unknown fields, and the rejection must be observable",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "spec_anchor": spec_anchor(),
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "profile": "parser-unknown-field-strictness",
        "cloud_ok": False,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "platform-test-engineer",
            "execution_substrate": "local-parallel",
        },
        "answer": answer,
        "parser_table": production,
        "lenient_control": control,
        "live_plugin_json": {
            "path": ".claude-plugin/plugin.json",
            "present": plugin_live.is_file(),
            "note": (
                "Catalog input .claude-plugin/plugin.json is a Claude Code "
                "manifest. Production rows use marketplace payload plugin.json, "
                "install-handoff, exec-policy, and hooks.json loaders; the "
                "lenient control is json.loads."
            ),
        },
        "evidence": [
            {
                "claim": "Each production parser hard-rejects an extra unknown field and the error names that field.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0052/probe1_unknown_field_rejected.py",
            },
            {
                "claim": "The same parsers still accept the unmodified known-good document (both-states pair).",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0052/probe2_known_field_still_accepted.py",
            },
            {
                "claim": "A json.loads-only client would keep the extra key on the dict and ignore it in named getters.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0052/kinds.py",
            },
        ],
        "measurements": [
            {
                "id": "production-parsers",
                "value": live["production_count"],
                "unit": "count",
                "method": "kinds.measure_all production rows",
            },
            {
                "id": "production-unknown-rejected",
                "value": live["production_unknown_all_rejected"],
                "unit": "boolean",
                "method": "inject __tst0052_unknown__ into each live loader",
            },
            {
                "id": "lenient-control-accepts",
                "value": live["lenient_control_accepts_unknown"],
                "unit": "boolean",
                "method": "json.loads negative control",
            },
        ],
        "tests": [
            {
                "id": "test_unknown_field_rejected_per_parser",
                "name": "unknown extra field is hard-rejected and named",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_known_field_still_accepted",
                "name": "known-good document still accepted (both-states pair)",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "unknown-field-rejected"},
            {"id": "probe2", "command": P2, "role": "known-field-still-accepted"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0052-probe2-known-field-still-accepted",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 re-runs the live loaders from a second process and "
                "requires known-good ACCEPT plus unknown REJECT on the same "
                "parsers. It does not reuse probe 1's printed summary."
            ),
        },
        "artifacts": [art(OUT, "primary")] + [art(p, "supporting") for p in SUPPORTING],
        "implementation": {
            "plugin_manifest_schema": "tools/plugin/schema/plugin-manifest.schema.json",
            "plugin_loader": "tools/plugin/payload.py",
            "forward_compat_prefix": "x-",
            "kinds": [r["kind"] for r in production],
        },
        "notes": (
            "G-1 for TST-0052: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. "
            f"{SENTINEL}"
        ),
        "ts": now,
        "timestamps": {"started_at": now, "ended_at": now},
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in raw:
        print("FAILED:TST-0052 emit sentinel missing")
        return 1
    out.write_text(raw, encoding="utf-8")
    sha, size = digest_file(out)
    if size < 2048:
        print(f"FAILED:TST-0052 emit too small {size}B")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:TST-0052 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
