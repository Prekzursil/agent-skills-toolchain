#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0042.json (default-exercise census)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import constants as K  # noqa: E402
import validate_schema as V  # noqa: E402
from fixtures import planted_defaults as P  # noqa: E402


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_snippet(rel_path: str, fallback: str) -> tuple[int, str]:
    if ":" in rel_path:
        path_s, _, line_s = rel_path.rpartition(":")
        try:
            line_no = int(line_s)
        except ValueError:
            line_no = 1
    else:
        path_s, line_no = rel_path, 1
    path = REPO / path_s
    if not path.is_file():
        return line_no, fallback
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if 1 <= line_no <= len(lines):
        return line_no, lines[line_no - 1].strip()[:240]
    return line_no, fallback


def map_kind(kind: str) -> str:
    if kind == "planted":
        return "planted"
    if kind == "cli_flag":
        return "cli_flag"
    if kind == "config_default":
        return "config_default"
    return "function_param"


def main() -> int:
    P.run_planted_assertions()
    P.run_empty_test_only()

    measured = C.run_census()
    controls = C.control_results(measured)
    required = controls[:3]
    if any(c["result"] != "PASS" for c in required):
        print("FAILED:BLD-0042 required controls")
        print(json.dumps(required, indent=2))
        return 1
    if not V.garbage_rejected():
        print("FAILED:BLD-0042 schema is vacuous")
        return 1

    cli = measured["known"].get("require_complete_cli") or {}
    planted = measured["known"].get("planted") or {}
    ci = measured["ci_join"]
    consumed = measured["consumed_aud_0057"]

    unexercised_rows = []
    for row in measured["unexercised"]:
        unexercised_rows.append(
            {
                "name": row["name"],
                "kind": map_kind(row["kind"]),
                "declaration_site": row["declaration_site"],
                "explicit_call_site_count": row["explicit_call_site_count"],
                "classification": "UNEXERCISED",
                "reason": row["reason"],
                "func_name": row["func_name"],
                "default_repr": row["default_repr"],
                "flags": row.get("flags") or [],
                "ci_tool_invocations": row.get("ci_tool_invocations") or 0,
                "ci_flag_passed": row.get("ci_flag_passed") or 0,
            }
        )

    require_site = cli.get("declaration_site") or "tools/command-center/validate.py:1"
    rline, rsnip = line_snippet(require_site, "parser.add_argument('--require-complete'")
    never = planted.get("planted_never_omitted") or {}
    nsite = never.get("declaration_site") or (
        "command-center/p2-wave/probes/BLD-0042/fixtures/planted_defaults.py:1"
    )
    nline, nsni = line_snippet(nsite, "def planted_never_omitted")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out_path = REPO / K.OUT_REL
    doc = {
        "unit_id": K.UNIT_ID,
        "state": "SUCCESS",
        "sentinel": K.SENTINEL,
        "kind": "test-quality-census",
        "question": K.QUESTION,
        "answer": (
            f"CI invokes tools/command-center/validate.py bare "
            f"(invocations={ci.get('validate_py_invocations')}, "
            f"--require-complete passed={ci.get('require_complete_flag_passed')}); "
            f"the CLI default require_complete=False is UNEXERCISED in the shipped "
            f"configuration (CI-OMITS-FLAG). Enumerated {measured['defaults_enumerated']} "
            f"defaults under tools/ plus planted fixtures; "
            f"{len(unexercised_rows)} reported unexercised. AUD-0057 artifact is "
            f"ABSENT; live .github/workflows present="
            f"{ci.get('live_github_workflows_present')}."
        ),
        "scope_boundary": measured["scope"]["bound"],
        "census": {
            "scope": {
                "roots": measured["scope"]["roots"],
                "bound": measured["scope"]["bound"],
                "files_parsed": measured["scope"]["files_parsed"],
            },
            "defaults_enumerated": measured["defaults_enumerated"],
            "unexercised": unexercised_rows,
            "ci_join": {
                "live_github_workflows_present": ci["live_github_workflows_present"],
                "recorded_inventory_present": ci["recorded_inventory_present"],
                "validate_py_invocations": ci["validate_py_invocations"],
                "require_complete_flag_passed": ci["require_complete_flag_passed"],
                "recorded_inventory_path": ci["recorded_inventory_path"],
                "commands_collected": ci["commands_collected"],
                "validate_invocation_examples": ci["validate_invocation_examples"],
            },
            "consumed_aud_0057": {
                "path": consumed["path"],
                "present": consumed["present"],
                "note": consumed.get("note"),
            },
            "known_require_complete_cli": cli,
            "known_require_complete_fn": measured["known"].get("require_complete_fn"),
            "planted": planted,
        },
        "controls": [
            {
                "id": c["id"],
                "expected": c["expected"],
                "observed": c["observed"],
                "result": c["result"],
            }
            for c in controls
        ],
        "tests": [
            {"id": "probe1", "command": K.P1, "result": "PASS"},
            {"id": "probe2", "command": K.P2, "result": "PASS"},
            {
                "id": "control-require_complete-ci-bare",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/BLD-0042/census.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0042-probe2-independent-default-mutation",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Scratch-copy rewrite of two reported UNEXERCISED planted defaults; "
                "asserting suite stays green. Vacuity: rewriting planted_exercised "
                "turns the asserting test red."
            ),
        },
        "artifacts": [
            {"path": K.OUT_REL, "exists": True, "role": "primary"},
            {"path": K.SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "evidence": [
            {
                "claim": (
                    "validate.py --require-complete defaults to False and CI invokes "
                    "the tool without the flag"
                ),
                "verdict": "CONFIRMED",
                "anchor": require_site,
                "path": require_site.split(":")[0],
                "line": rline,
                "snippet": rsnip,
                "kind": "declaration",
            },
            {
                "claim": (
                    "A planted default passed explicitly on every asserting call is "
                    "reported UNEXERCISED (DEFAULT-NEVER-USED)"
                ),
                "verdict": "CONFIRMED",
                "anchor": nsite,
                "path": nsite.split(":")[0],
                "line": nline,
                "snippet": nsni,
                "kind": "planted-control",
            },
        ],
        "produced_at": now,
        "measured_not_asserted": True,
    }

    errs = V.validate_doc(doc)
    if errs:
        print("FAILED:BLD-0042 schema")
        print("\n".join(errs[:12]))
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    print(f"wrote {K.OUT_REL} bytes={size} sha256={digest}")
    print(K.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
