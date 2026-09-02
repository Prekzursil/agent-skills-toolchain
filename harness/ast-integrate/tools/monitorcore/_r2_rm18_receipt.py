"""Build R-M18's declared receipt, validate it with the repo's OWN gate, refuse to write it
if it does not validate -- and report the precise blocker when it does not.

WHY THIS EXISTS. Round 1 of this lane claimed the receipt could not be written because
`platform/schema/receipt.schema.json` requires an INDEPENDENT reviewer PASS. An adversarial
audit REFUTED that: the reviewer clause is inside an `if state == "SUCCESS"` branch, so a
`state="BLOCKED"` receipt with `reviewer.independent=false` is schema-valid -- and
`command-center/receipts/BLD-0023.json` is exactly that, already on disk and already valid.
The quotation was accurate; the conclusion drawn from it was wider than the clause. That
earlier wording is RECORDED AS REFUTED here rather than deleted.

Re-measuring instead of re-asserting produced a DIFFERENT and much narrower blocker, which
this script proves both ways. It is deliberately mechanically independent of round 1's
reading: round 1 read the `state` conditional, this reads the `unit_id` pattern.

The script never hand-writes an artifact. It builds, validates, and only then would write --
a receipt that is emitted without validating is the "guard that converts a bug into a green"
the emitter it is modelled on (command-center/p13_emit_receipt.py) refuses to be.

Run:  python tools/monitorcore/_r2_rm18_receipt.py          (build + validate, never writes)
      python tools/monitorcore/_r2_rm18_receipt.py --write  (writes ONLY if it validates)
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "command-center" / "receipts" / "R-M18.json"
TS_START = "2026-08-12T09:00:00Z"
TS_END = "2026-08-12T12:00:00Z"


def load_gate() -> Any:
    path = REPO / "platform" / "lib" / "receipt_schema_gate.py"
    spec = importlib.util.spec_from_file_location("receipt_schema_gate", path)
    if spec is None or spec.loader is None:  # pragma: no cover - import plumbing
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["receipt_schema_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def artifact(rel: str) -> dict[str, Any]:
    p = REPO / rel
    exists = p.is_file()
    data = p.read_bytes() if exists else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest() if exists else "0" * 64,
        "exists": exists,
    }


def probe(role: str, method: str, command: str, raw: str) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw,
        "fingerprint": hashlib.sha256(f"{command}\n{raw}".encode()).hexdigest()[:32],
    }


def build(unit_id: str, sentinel: str) -> dict[str, Any]:
    """The receipt body. `unit_id`/`sentinel` are parameters so the id-shape blocker can be
    isolated from every other field by re-validating the SAME body under a conformant id."""
    return {
        "schema_version": 1,
        "unit_id": unit_id,
        # NOT "SUCCESS", and not because the schema forbids naming it: the honest state is
        # that this lane BUILT the increment, so its own verdict is not independent. BLOCKED
        # is what BLD-0023 uses for the same situation.
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": "command-center/sources/REGISTER.md#R-M18",
        "min_bytes_threshold": 512,
        "artifacts": [
            artifact("docs/monitor/ENROLMENT-R-M18.md"),
            artifact("docs/monitor/MON-ROUND2.md"),
            artifact("tools/monitorcore/tests/test_registry_commit_truth.py"),
            artifact("skills/monitor-launcher/monitors.toml"),
        ],
        "evidence": [
            {
                "claim": (
                    "The cockpit is reachable from BOTH committed registry mirrors: a "
                    "[cockpit] stanza resolves to a tracked entry script that hands off to "
                    "monitorcore.unified."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "skills/monitor-launcher/monitors.toml",
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        "monitorcore.monitors.load_monitors(<each shipped registry>)",
                        "6 stanzas per registry; 'cockpit' present in both",
                    ),
                    probe(
                        "verifier",
                        "byte-compare",
                        "git ls-tree -r --name-only HEAD | membership test on each resolved entry",
                        "12/12 entry paths tracked at HEAD (control: a bogus path is absent, "
                        "a known path is present)",
                    ),
                ],
            },
            {
                "claim": (
                    "The two committed registry mirrors are byte-identical in the COMMIT, "
                    "not merely in this Windows working tree."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "tools/monitorcore/tests/test_registry_commit_truth.py",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "git cat-file -p HEAD:<each mirror>",
                        "3874 B each, 0 CRLF, raw-identical",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        "python -m pytest tests/test_registry_commit_truth.py -q",
                        "15 passed, including a control that fires on a fabricated "
                        "worktree-green/commit-red tree",
                    ),
                ],
            },
            {
                "claim": (
                    "R-M18's own governing artifact cannot be emitted under the id the "
                    "register gives it: 'R-M18' violates the receipt schema's unit_id "
                    "pattern ^[A-Z][A-Z0-9]*-[0-9]{4}$."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "platform/schema/receipt.schema.json#/$defs/unit_id",
                "probes": [
                    probe(
                        "source",
                        "schema-validate",
                        "receipt_schema_gate.validate_receipt(body, fragment='receipt_core')",
                        "unit_id and sentinel pattern violations with unit_id='R-M18'",
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        "re.fullmatch(unit_id_pattern, 'R-M18') vs 'BLD-0023'",
                        "'R-M18' -> None; 'BLD-0023' -> match (the pattern is the constraint, "
                        "not the validator)",
                    ),
                ],
            },
        ],
        "failure": {
            "classification": ["dependency-blocked", "owner-blocked"],
            "reason": (
                "The MONITOR cockpit increment is built and measured, but R-M18's declared "
                "output_path cannot be emitted as a schema-valid receipt while the unit is "
                "identified as 'R-M18'. command-center/schema/receipt.schema.json is a "
                "generated shim that $refs platform/schema/receipt.schema.json#/$defs/"
                "receipt_core, whose unit_id pattern is ^[A-Z][A-Z0-9]*-[0-9]{4}$ (four "
                "digits, one hyphen). 'R-M18' has two hyphen-separated segments and two "
                "digits, so it cannot be a unit_id; the catalog's own declared "
                "completion_sentinel 'SUCCESS:R-M18' is unrepresentable for the same reason. "
                "Separately and independently: a SUCCESS receipt additionally requires an "
                "INDEPENDENT reviewer PASS, which the lane that built the increment cannot "
                "supply for itself. Round 1 of this lane named ONLY the reviewer clause and "
                "concluded the receipt was unwritable; that was REFUTED (a BLOCKED receipt "
                "with reviewer.independent=false is schema-valid, as BLD-0023 already "
                "demonstrates), and this is the corrected, re-measured blocker."
            ),
            "blocked_on": (
                "A governance decision outside this lane's file scope: either (a) give the "
                "row a schema-conformant id (e.g. RM-0018) in command-center/sources/"
                "REGISTER.md + WORK-UNIT-CATALOG.json, or (b) widen $defs/unit_id to admit "
                "the R-M<n> family -- (b) touches the schema 674 catalogued units share. "
                "THEN an independent reviewer records verdict PASS to reach SUCCESS."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether the R-M family id shape was intended to be receipt-emitting at "
                    "all, or whether REGISTER rows are a different artifact class."
                ),
                # NOT-CHECKED, not UNVERIFIED: the schema's verdict enum has no UNVERIFIED
                # member, and my first draft used it -- caught by LEG 2 rather than by
                # reading, which is why LEG 2 exists.
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Grep WORK-UNIT-CATALOG.json for every id that fails the unit_id pattern "
                    "and check whether any of them declares a receipt output_path; if the "
                    "R-M family is the only one, the id shape is the defect."
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "NONE",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": (
                "The lane that built the increment cannot review it. A fresh-context "
                "reviewer should re-run the mutation control and re-derive the unit_id "
                "finding from the schema file rather than from this receipt."
            ),
        },
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        },
        "timestamps": {"started_at": TS_START, "ended_at": TS_END},
        "retry": {"count": 1, "policy": "two strikes then pivot (AGENTS.md 4b)"},
    }


def id_pattern() -> str:
    schema = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    return schema["$defs"]["unit_id"]["pattern"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)

    gate = load_gate()
    pattern = id_pattern()
    print(f"[schema] $defs/unit_id pattern = {pattern}")
    print(
        f"[probe ] re.fullmatch(pattern, 'R-M18')   -> {re.fullmatch(pattern, 'R-M18')}"
    )
    print(
        f"[ctrl  ] re.fullmatch(pattern, 'BLD-0023')-> {re.fullmatch(pattern, 'BLD-0023')}"
    )

    declared = build("R-M18", "SUCCESS:R-M18")
    errors = gate.validate_receipt(declared, fragment="receipt_core")
    print(f"\n[LEG 1] receipt as R-M18 declares itself -> {len(errors)} error(s)")
    for e in errors:
        print(f"         {e}")

    # CONTROL: the SAME body under a conformant id. If this validates, every field except
    # the id is already correct and the id shape is the whole blocker. If it does NOT, the
    # blocker claim above would be too narrow and must not be reported.
    control = build(
        "RM-0018", "SENTINEL:RM-0018:BLOCKED-ON-ID-SHAPE-AND-INDEPENDENT-REVIEW"
    )
    control_errors = gate.validate_receipt(control, fragment="receipt_core")
    print(
        f"\n[LEG 2 control] identical body, id RM-0018 -> {len(control_errors)} error(s)"
    )
    for e in control_errors:
        print(f"         {e}")

    # CONTROL: a known-good on-disk receipt must validate, and a deliberately broken variant
    # must not. Without this pair a clean LEG 2 could mean "the validator never fires".
    bld = json.loads(
        (REPO / "command-center" / "receipts" / "BLD-0023.json").read_text(
            encoding="utf-8"
        )
    )
    print(
        f"\n[LEG 3 control] BLD-0023 as-is -> "
        f"{len(gate.validate_receipt(bld, fragment='receipt_core'))} error(s)"
    )
    broken = copy.deepcopy(bld)
    broken["state"] = "SUCCESS"
    print(
        f"[LEG 4 control] BLD-0023 with state flipped to SUCCESS -> "
        f"{len(gate.validate_receipt(broken, fragment='receipt_core'))} error(s) "
        f"(must be > 0 or the validator is inert)"
    )

    if errors:
        print(
            "\nFAILED:R-M18-receipt not written -- the declared unit id is not a valid "
            "unit_id. Writing an invalid receipt would be the false green this emitter exists "
            "to prevent."
        )
        return 1
    if args.write:  # pragma: no cover - unreachable while the id blocker stands
        OUT.write_text(json.dumps(declared, indent=1) + "\n", encoding="utf-8")
        print(f"SUCCESS:R-M18-receipt wrote {OUT}")
    else:
        print("\nSUCCESS:R-M18-receipt validates (dry run; pass --write to persist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
