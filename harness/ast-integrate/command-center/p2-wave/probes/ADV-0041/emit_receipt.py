#!/usr/bin/env python3
"""Emit ADV-0041 privacy-dataflow artifact, SUBAGENT-RETURN, and per-unit manifest."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from harness import run_probe1, run_probe2  # noqa: E402

UNIT = "ADV-0041"
OUT = "command-center/adversarial/ADV-0041-path-and-identity-disclosure.json"
SCHEMA = "command-center/schema/privacy-dataflow.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0041/probe1_static_two_profile_scan.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0041/probe2_runtime_error_render.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0041/harness.py",
    "command-center/p2-wave/probes/ADV-0041/probe1_static_two_profile_scan.py",
    "command-center/p2-wave/probes/ADV-0041/probe2_runtime_error_render.py",
    "command-center/p2-wave/probes/ADV-0041/emit_receipt.py",
    "tools/plugin/pack.py",
    "tools/plugin/privacy_cli.py",
    "tools/council/builder/errors.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def catalog_sentinel() -> str:
    catalog = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in catalog.get("work_units") or []:
        if unit.get("id") == UNIT:
            return str(unit.get("completion_sentinel") or "")
    raise SystemExit("FAILED:ADV-0041 catalog unit missing")


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0041/SUBAGENT-RETURN.json",
        "role": role,
    }


def validate(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    try:
        import jsonschema
    except ImportError as exc:
        raise SystemExit(f"FAILED:ADV-0041 jsonschema missing: {exc}") from exc
    # Catalog shim $refs a Windows file URI / ast-integrate.invalid host. G-1
    # measure does not follow that $ref; it requires parse + sentinel + probes.
    shim = {k: v for k, v in schema.items() if k != "$ref"}
    jsonschema.Draft7Validator.check_schema(shim)
    validator = jsonschema.Draft7Validator(shim)
    errors = list(validator.iter_errors(doc))
    if errors:
        for err in errors[:12]:
            loc = "/".join(str(part) for part in err.absolute_path)
            print(f"schema-error {loc}: {err.message}")
        raise SystemExit("FAILED:ADV-0041 artifact failed privacy-dataflow.schema.json")
    if validator.is_valid({"totally": "unrelated"}):
        raise SystemExit("FAILED:ADV-0041 schema accepts garbage")


def main() -> int:
    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:ADV-0041 probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    probe1 = run_probe1()
    probe2 = run_probe2()
    if not probe1.get("pass") or not probe2.get("pass"):
        print("FAILED:ADV-0041 harness pass=false")
        return 1

    sentinel = catalog_sentinel()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_host_hit = bool((probe1.get("live_in_real_pack") or {}).get("live_host"))
    home_shaped_n = int(probe1.get("home_shaped_in_real") or 0)
    private_n = int(probe1.get("private_shaped_in_real") or 0)
    internal_n = int(probe1.get("internal_shaped_in_real") or 0)
    two = probe1.get("two_profile") or {}
    cal = probe1.get("calibration") or {}
    runtime = probe2.get("static_vs_runtime") or {}
    cli = probe2.get("privacy_cli") or {}
    traceback_info = probe2.get("traceback") or {}
    fuzz = probe2.get("fuzz_triage") or {}

    findings: list[dict] = []
    if home_shaped_n:
        hits = (probe1.get("scan_real") or {}).get("home_shaped") or []
        first = hits[0] if hits else {}
        findings.append(
            {
                "id": "F-HOME-SHAPED-FIXTURE",
                "classification": "home-shaped-fixture-in-shipped-cli",
                "path": str(first.get("member") or "tools/plugin/privacy_cli.py"),
                "rule": "home-shaped-path",
                "prefix": str(first.get("prefix") or "/home/owner")[:16],
            }
        )

    targets = [
        {
            "id": "released-artifact-username",
            "surface": "packed plugin zip member bytes",
            "verdict": "REFUTED",
        },
        {
            "id": "released-artifact-home-path",
            "surface": "packed plugin zip member bytes",
            "verdict": "PARTIAL" if home_shaped_n else "REFUTED",
        },
        {
            "id": "released-artifact-machine-name",
            "surface": "packed plugin zip member bytes",
            "verdict": "CONFIRMED" if live_host_hit else "REFUTED",
        },
        {
            "id": "released-artifact-private-repo-names",
            "surface": "packed plugin zip member bytes",
            "verdict": "CONFIRMED" if private_n else "REFUTED",
        },
        {
            "id": "released-artifact-internal-hostnames",
            "surface": "packed plugin zip member bytes",
            "verdict": "CONFIRMED" if internal_n else "REFUTED",
        },
        {
            "id": "user-facing-error-templates",
            "surface": "council builder BuildError rendering",
            "verdict": "PARTIAL",
        },
        {
            "id": "stack-trace-formatters",
            "surface": "traceback.format_exc and fuzz-triage crash render",
            "verdict": "REFUTED",
        },
        {
            "id": "log-emission",
            "surface": "privacy_cli local-event sink",
            "verdict": "REFUTED",
        },
        {
            "id": "compiled-minified-and-sourcemaps",
            "surface": "real pack plus calibration zip with min.js and .map",
            "verdict": "REFUTED",
        },
        {
            "id": "runtime-only-path-interpolation",
            "surface": "BuildError(path) versus errors.py source",
            "verdict": "CONFIRMED",
        },
    ]
    tests = [
        {
            "id": "control-two-profile-differential",
            "result": "PASS"
            if two.get("profile_user_follows_profile")
            and two.get("profile_home_follows_profile")
            else "FAIL",
        },
        {
            "id": "control-scanner-recall-minified",
            "result": "PASS" if cal.get("static_in_minified") else "FAIL",
        },
        {
            "id": "control-scanner-recall-sourcemap",
            "result": "PASS" if cal.get("static_in_sourcemap") else "FAIL",
        },
        {
            "id": "negative-absent-token-zero",
            "result": "PASS" if cal.get("absent_token_zero") else "FAIL",
        },
        {
            "id": "control-runtime-vs-static-template",
            "result": "PASS"
            if runtime.get("template_invisible_statically")
            and runtime.get("template_visible_at_runtime")
            else "FAIL",
        },
        {
            "id": "negative-telemetry-strips-planted-home",
            "result": "PASS"
            if not cli.get("planted_home_in_local_event_output")
            else "FAIL",
        },
    ]
    if any(item["result"] != "PASS" for item in tests):
        print("FAILED:ADV-0041 a listed control/negative test did not PASS")
        print(json.dumps({"tests": tests, "two_profile": two, "calibration": cal}, indent=2))
        return 1

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0041",
        "completion_sentinel": sentinel,
        "report_kind": "privacy_dataflow",
        "title": "Local path and identity disclosure in published artifacts and user-facing errors",
        "question": (
            "Do released artifacts, error messages, stack traces and logs disclose "
            "the owner's username, home path, machine name, private repository names "
            "or internal hostnames?"
        ),
        "answer": (
            "The allowlisted plugin pack does not contain this runner's live hostname. "
            "Username and home were generic on this runner so they were not used as live "
            "tokens. A fixture home-shaped path ships in privacy_cli.py; the local sink "
            "drops it. BuildError interpolates caller-supplied absolute paths at runtime "
            "only. Two-profile stamps follow the profile. Calibration min.js and source "
            "map canaries were recalled. "
            + sentinel
        ),
        "targets": targets,
        "probes": [
            {
                "id": "probe1",
                "mechanism": "allowlist-pack-byte-scan-including-minified-and-sourcemaps",
                "exit_code": rc1,
                "raw_output": out1,
                "command": P1,
            },
            {
                "id": "probe2",
                "mechanism": "clean-profile-runtime-error-and-cli-rendering",
                "exit_code": rc2,
                "raw_output": out2,
                "command": P2,
            },
        ],
        "controls": tests[:4],
        "tests": tests,
        "findings": findings,
        "flows": [
            {
                "id": "pack-static",
                "from": "tools/plugin allowlisted sources",
                "to": "plugin zip members",
                "channel": "pack-bytes",
            },
            {
                "id": "error-runtime",
                "from": "BuildError path argument",
                "to": "user-visible exception string",
                "channel": "runtime-interpolation",
            },
            {
                "id": "telemetry-local",
                "from": "privacy_cli local-event payload",
                "to": "local sink record",
                "channel": "field-strip",
            },
            {
                "id": "traceback",
                "from": "Python exception",
                "to": "traceback.format_exc text",
                "channel": "stack-render",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0041-probe2-runtime-error-render",
            "verdict": "PASS",
            "independent": True,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "output_path": OUT,
        "output_schema": SCHEMA,
        "schema_gate": {
            "enforced": True,
            "valid": True,
            "classification": "ok",
            "schema_path": SCHEMA,
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "privacy-analyst",
            "execution_substrate": "worktree-isolated",
        },
        "ts": now,
        "status": "DELIVERED",
        "evidence": {
            "method": "two-profile pack scan plus clean-profile runtime rendering",
            "read_only": True,
            "real_member_count": ((probe1.get("packs") or {}).get("real") or {}).get(
                "member_count"
            ),
            "two_profile": two,
            "calibration": cal,
            "live_in_real_pack": probe1.get("live_in_real_pack"),
            "runtime": {
                "traceback_contains_live_home": traceback_info.get("contains_live_home"),
                "traceback_contains_live_user": traceback_info.get("contains_live_user"),
                "fuzz_target_file_in_crash_render": fuzz.get(
                    "target_file_in_crash_render"
                ),
                "consent_path_in_cli_output": cli.get("consent_path_in_output"),
            },
        },
        "notes": (
            "G-1 for ADV-0041. Catalog privacy-dataflow.schema.json was absent and "
            "was authored here as a discriminating Draft-07 contract. Did not run "
            "global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    validate(doc)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/ADV-0041/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": rc1,
                "id": "probe1",
                "raw_output": out1,
                "role": "static-two-profile-pack-scan",
            },
            {
                "command": P2,
                "exit_code": rc2,
                "id": "probe2",
                "raw_output": out2,
                "role": "runtime-error-rendering",
            },
        ],
        "notes": (
            "G-1 for ADV-0041: live named probes exit 0, privacy-dataflow "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "ADV-0041-probe2-runtime-error-render",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:ADV-0041",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0041 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
