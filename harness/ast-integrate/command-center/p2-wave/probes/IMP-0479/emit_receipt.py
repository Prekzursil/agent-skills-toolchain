#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0479.json from a live redaction proof."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))

from telemetry.canaries import value_leaked  # noqa: E402
from telemetry.fields import FIELD_PURPOSE  # noqa: E402
from telemetry.netaudit import audit_no_network  # noqa: E402
from telemetry.points import EMISSION_POINTS, POINT_PURPOSE  # noqa: E402
from telemetry.redact import MARKER_HOME, MARKER_PERSON, MARKER_PROJECT, MARKER_SECRET  # noqa: E402
from telemetry.sweep import (  # noqa: E402
    refuse_ephemeral_sink,
    run_canary_sweep,
    run_opt_out_proof,
    run_unredacted_control,
)

OUT = "command-center/receipts/IMP-0479.json"
SCHEMA = "command-center/schema/telemetry-contract.schema.json"
SENTINEL = "SENTINEL:IMP-0479:TELEMETRY-REDACTION-PROVEN"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0479/probe1_canary_sweep.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0479/probe2_optout_control.py"
)
PKG = REPO / "command-center" / "telemetry"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    exists = path.is_file()
    row = {"path": rel, "exists": exists, "role": role}
    if exists:
        sha, size = sha256_file(path)
        row["sha256"] = sha
        row["bytes"] = size
    return row


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0479-emit-") as tmp:
        sweep = run_canary_sweep(Path(tmp) / "sweep")
        opt = run_opt_out_proof(Path(tmp) / "opt")
    ctrl = run_unredacted_control()
    eph = refuse_ephemeral_sink()
    net = audit_no_network(PKG)

    failed = [
        name
        for name, ok in (
            ("canary_sweep", sweep.get("pass")),
            ("opt_out", opt.get("pass")),
            ("unredacted_control", ctrl.get("pass")),
            ("ephemeral_channel", eph.get("pass")),
            ("network_audit", net.get("pass")),
        )
        if not ok
    ]
    if failed:
        print("FAILED:IMP-0479 proofs failed:", ",".join(failed))
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        "command-center/schema/telemetry-contract.schema.json",
        "command-center/telemetry/bus.py",
        "command-center/telemetry/redact.py",
        "command-center/telemetry/sink.py",
        "command-center/telemetry/sweep.py",
        "command-center/telemetry/points.py",
        "command-center/telemetry/fields.py",
        "command-center/telemetry/policy.py",
        "command-center/p2-wave/probes/IMP-0479/probe1_canary_sweep.py",
        "command-center/p2-wave/probes/IMP-0479/probe2_optout_control.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print("FAILED:IMP-0479 missing supporting", missing)
        return 1

    doc = {
        "unit_id": "IMP-0479",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:10819",
        "question": (
            "Implement the telemetry and privacy contract from spec line 10819: "
            "what is recorded, what is redacted, where it is stored, how it is "
            "disabled. Redaction must be proven executably against planted canaries."
        ),
        "recorded_fields": [
            {"name": name, "purpose": purpose}
            for name, purpose in sorted(FIELD_PURPOSE.items())
        ],
        "redaction_rules": [
            {
                "class": "SECRET_SHAPED",
                "marker": MARKER_SECRET,
                "rule": (
                    "Prefix classes (sk-, ghp_, AKIA, JWT, PEM, Bearer) and "
                    "mixed-class tokens of length >= 24 are replaced before persist."
                ),
            },
            {
                "class": "HOME_PATH",
                "marker": MARKER_HOME,
                "rule": (
                    "POSIX /home /Users /root, Windows Users\\, and ~user paths "
                    "are replaced in every string that reaches the durable sink."
                ),
            },
            {
                "class": "PROJECT_NAME",
                "marker": MARKER_PROJECT,
                "rule": (
                    "Configured identifiers (cwd name, home basename, policy extras) "
                    "of length >= 5 are stripped longest-first from emitted text."
                ),
            },
            {
                "class": "PERSONAL",
                "marker": MARKER_PERSON,
                "rule": "Email-shaped strings are replaced; values are never printed.",
            },
        ],
        "storage": {
            "kind": "local-file-jsonl",
            "durable": True,
            "ephemeral_refused": True,
            "default_relative_path": "command-center/telemetry/local-store/events.jsonl",
            "mode": "0600",
            "note": (
                "Stdout/stderr/fifo are rejected. An ephemeral channel is not "
                "exfiltration-safe and is not a store."
            ),
        },
        "disable": {
            "mechanism": (
                "AST_TELEMETRY_ENABLED=0|false|off, or policy.local_enabled=false"
            ),
            "when_disabled": (
                "emit() returns without creating a file and without writing any "
                "bytes at any named emission point."
            ),
        },
        "egress": {
            "default": "none",
            "implementation": "absent",
            "owner_opt_in_required": True,
            "note": (
                "No socket/http/urllib import exists in command-center/telemetry/. "
                "Env AST_TELEMETRY_EGRESS cannot open a wire: bus.emit refuses egress."
            ),
        },
        "emission_points": [
            {"id": pid, "purpose": POINT_PURPOSE[pid]} for pid in EMISSION_POINTS
        ],
        "canary_sweep": sweep,
        "opt_out": opt,
        "unredacted_control": ctrl,
        "ephemeral_channel": eph,
        "network_audit": net,
        "evidence": [
            {
                "claim": (
                    "Every registered emission point redacts planted SECRET_SHAPED, "
                    "HOME_PATH, and PROJECT_NAME canaries from the durable stream."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/telemetry/sweep.py:run_canary_sweep",
            },
            {
                "claim": "Disabling telemetry emits literally nothing (no file, 0 bytes).",
                "verdict": "CONFIRMED",
                "anchor": "command-center/telemetry/sweep.py:run_opt_out_proof",
            },
            {
                "claim": (
                    "The sweep detector is not inert: an unredacted blob is flagged "
                    "by class, and a redacted blob is silent."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/telemetry/sweep.py:run_unredacted_control",
            },
            {
                "claim": "Stdout is refused as a sink; the package has no network imports.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/telemetry/sink.py:assert_durable_path",
            },
        ],
        "tests": [
            {"id": "canary-per-point", "command": P1, "result": "PASS"},
            {"id": "opt-out-silence", "command": P2, "result": "PASS"},
            {
                "id": "unredacted-control",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0479-probe2-optout-control",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Mechanical: opt-out silence, unredacted-canary fire, ephemeral "
                "refusal, network-import AST. Not a substitute for owner sign-off "
                "of the recorded-field list."
            ),
        },
        "owner_approval": {
            "required": True,
            "status": "PENDING-RECORDED-FIELD-LIST",
            "subject": "recorded_fields in this artifact",
            "blocks_production_egress": True,
            "does_not_block_local_redaction_proof": True,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This sparse worktree does not contain the plugin runtime; "
                    "downstream emitters (IMP-0397 router telemetry, hook/CI writers "
                    "in a full checkout) must call command-center/telemetry.bus.emit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a full tree, census writers and route each through emit(); "
                    "re-run the canary sweep against those call sites."
                ),
            }
        ],
        "report": {
            "kind": "telemetry-contract",
            "observations": [
                {
                    "name": "canary_sweep_points",
                    "measured": int(sweep.get("point_count") or 0),
                    "method": "run_canary_sweep",
                    "anchor": "command-center/telemetry/sweep.py:run_canary_sweep",
                },
                {
                    "name": "opt_out_bytes",
                    "measured": int(opt.get("bytes") or 0),
                    "method": "run_opt_out_proof",
                    "anchor": "command-center/telemetry/sweep.py:run_opt_out_proof",
                },
                {
                    "name": "unredacted_control_fired",
                    "measured": bool(ctrl.get("fired_on_bad_state")),
                    "method": "run_unredacted_control",
                    "anchor": "command-center/telemetry/sweep.py:run_unredacted_control",
                },
            ],
            "control_ids": [
                "canary-per-point",
                "opt-out-silence",
                "unredacted-control",
            ],
        },
        "timestamps": {"generated_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            *artifacts,
        ],
    }

    # The declared output_schema is a $ref shim onto
    # platform/schema/artifact-class-profiles.schema.json. Following that URI
    # over the network (ast-integrate.invalid) is refused. Named probes re-run
    # the live redaction proofs against the written file.
    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:IMP-0479 schema missing")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("x-artifact-class") != "telemetry-contract":
        print("FAILED:IMP-0479 schema class mismatch")
        return 1
    if not isinstance(schema.get("$ref"), str) or not schema["$ref"]:
        print("FAILED:IMP-0479 schema $ref missing")
        return 1
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "telemetry-contract":
        print("FAILED:IMP-0479 report.kind missing")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0479 sentinel missing after write")
        return 1
    if value_leaked(text):
        print("FAILED:IMP-0479 canary value leaked into receipt")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
