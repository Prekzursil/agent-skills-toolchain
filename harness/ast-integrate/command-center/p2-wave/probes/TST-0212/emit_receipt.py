#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0212.json from live redactor runs.

Does not write SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST (write_receipts.py
does that after named probes pass). Does not call unit_manifest.py --write.
Never prints a secret body.
"""
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
sys.path.insert(0, str(REPO / "tools" / "lib"))

import jsonschema  # noqa: E402

from fixtures import (  # noqa: E402
    FIXED_MASK_BODY,
    length_secrets,
    mask_via_mjs,
    mask_via_python,
    prefix_samples,
    public_row,
)
from security import (  # noqa: E402
    DIAGNOSTIC_PREFIXES,
    MIN_BODY_CHARS,
    fixed_width_holds,
    mask_secret,
    utf8_len,
)

UNIT = "TST-0212"
OUT = "command-center/receipts/TST-0212.json"
SCHEMA_REL = "command-center/schema/security-report.schema.json"
TEST_SCHEMA_REL = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0212"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0212/probe1_prefix_and_fixed_width.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0212/probe2_per_char_mask_fails.py"
)
QUESTION = (
    "Does the redactor keep a diagnostic prefix (sk-, ghp_, hf_) while masking "
    "the remainder with a FIXED-WIDTH replacement, so the mask does not reveal "
    "the secret's length? PASS requires identical mask width for secrets of "
    "different lengths."
)
IMPL_PY = "tools/lib/security.py"
IMPL_MJS = "tools/lib/security.mjs"


def sha_file(rel: str) -> tuple[int, str, bool]:
    path = REPO / rel
    if not path.is_file():
        return 0, "", False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return len(raw), hashlib.sha256(raw).hexdigest(), True


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def first_json(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def validate(doc: dict, schema_rel: str) -> list[str]:
    schema = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = [
        f"{list(e.path)}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            errs.append(f"{schema_rel} accepted garbage")
            break
    return errs


def live_measure() -> dict:
    secrets = length_secrets()
    raw_lens = [utf8_len(s) for s in secrets]
    mjs = mask_via_mjs(secrets)
    py = mask_via_python(secrets)
    rows = [public_row(s, m) for s, m in zip(secrets, mjs)]
    family = []
    for prefix, token in prefix_samples():
        masked = mask_secret(token)
        family.append(
            {
                "prefix": prefix,
                "masked": masked,
                "prefix_readable": masked.startswith(prefix),
                "mask_body": masked[len(prefix) :],
            }
        )
    bare = {p: mask_secret(p) for p in DIAGNOSTIC_PREFIXES}
    short = mask_secret("sk-SHORT")
    return {
        "raw_secret_byte_lengths": raw_lens,
        "raw_lengths_distinct": len(set(raw_lens)) == 5,
        "mjs_renders": mjs,
        "python_renders": py,
        "twins_agree": mjs == py,
        "rows": rows,
        "masked_byte_lengths": [r["masked_byte_len"] for r in rows],
        "fixed_width_holds": fixed_width_holds(mjs),
        "prefixes_readable": all(r["prefix_readable"] for r in rows),
        "bodies_absent": all(r["body_absent_from_mask"] for r in rows),
        "fixed_mask_body": FIXED_MASK_BODY,
        "prefix_family": family,
        "bare_prefix_unchanged": all(bare[p] == p for p in DIAGNOSTIC_PREFIXES),
        "short_body_unchanged": short == "sk-SHORT",
        "min_body_chars": MIN_BODY_CHARS,
    }


def main() -> int:
    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:TST-0212 emit named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    p1 = first_json(out1)
    p2 = first_json(out2)
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:TST-0212 emit probe pass=false")
        return 1

    try:
        measured = live_measure()
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:TST-0212 emit live measure: {exc}")
        return 1
    if not measured["twins_agree"]:
        print("FAILED:TST-0212 emit mjs/python disagree")
        return 1
    if not measured["raw_lengths_distinct"]:
        print("FAILED:TST-0212 emit fixture lengths not distinct")
        return 1
    if not measured["fixed_width_holds"]:
        print("FAILED:TST-0212 emit fixed-width failed")
        return 1
    if not measured["prefixes_readable"] or not measured["bodies_absent"]:
        print("FAILED:TST-0212 emit prefix/body checks")
        return 1
    if not all(s["prefix_readable"] for s in measured["prefix_family"]):
        print("FAILED:TST-0212 emit prefix family")
        return 1
    if not measured["bare_prefix_unchanged"]:
        print("FAILED:TST-0212 emit bare prefix was masked")
        return 1

    py_b, py_s, py_ok = sha_file(IMPL_PY)
    js_b, js_s, js_ok = sha_file(IMPL_MJS)
    if not (py_ok and js_ok):
        print("FAILED:TST-0212 emit missing redactor implementation")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    renders = measured["mjs_renders"]
    masked_lens = measured["masked_byte_lengths"]
    answer = (
        "YES: the live redactor in tools/lib/security.mjs (Python twin "
        "tools/lib/security.py) keeps diagnostic prefixes sk-/ghp_/hf_ and "
        f"replaces the remainder with the fixed body {FIXED_MASK_BODY!r}. "
        f"Five planted sk- secrets of byte lengths {measured['raw_secret_byte_lengths']} "
        f"rendered as {renders} with identical utf-8 lengths {masked_lens}. "
        "A per-character remainder mask on the same secrets produced unequal "
        "widths and failed the fixed-width assertion."
    )
    doc = {
        "answer": answer,
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
                "sha256_note": "self-hash omitted; live digest is UNIT-ARTIFACT-MANIFEST.json",
            },
            {
                "path": IMPL_MJS,
                "exists": True,
                "role": "implementation",
                "bytes": js_b,
                "sha256": js_s,
            },
            {
                "path": IMPL_PY,
                "exists": True,
                "role": "implementation-twin",
                "bytes": py_b,
                "sha256": py_s,
            },
        ],
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "a real credential was used; only planted TESTONLY tokens",
            "tools/lib/security.mjs existed before this unit; it was implemented here",
        ],
        "evidence": [
            {
                "claim": (
                    "Five planted sk- secrets of differing lengths render to "
                    f"{renders} (signal a)."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_MJS}:maskSecret",
                "signal": "a-rendered-masks",
            },
            {
                "claim": (
                    "utf-8 byte lengths of those five renders are equal: "
                    f"{masked_lens} (signal b). Pre-mask lengths were distinct: "
                    f"{measured['raw_secret_byte_lengths']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{IMPL_PY}:fixed_width_holds",
                "signal": "b-byte-length-equality",
            },
            {
                "claim": (
                    "Both-states: prefixes sk-/ghp_/hf_ remain readable after "
                    "masking; a per-character remainder mask fails fixed-width."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/TST-0212/"
                    "probe2_per_char_mask_fails.py"
                ),
                "signal": "negative-control-per-character-mask",
            },
        ],
        "fixed_mask_body": FIXED_MASK_BODY,
        "id": UNIT,
        "implementation": {
            "mjs": {"path": IMPL_MJS, "bytes": js_b, "sha256": js_s},
            "python": {"path": IMPL_PY, "bytes": py_b, "sha256": py_s},
        },
        "measured": {
            "bare_prefix_unchanged": measured["bare_prefix_unchanged"],
            "bodies_absent": measured["bodies_absent"],
            "fixed_width_holds": measured["fixed_width_holds"],
            "masked_byte_lengths": masked_lens,
            "prefix_family": measured["prefix_family"],
            "prefixes_readable": measured["prefixes_readable"],
            "raw_secret_byte_lengths": measured["raw_secret_byte_lengths"],
            "renders": renders,
            "twins_agree": measured["twins_agree"],
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "result": "PASS",
                "role": "prefix-readable-and-fixed-width-across-five-lengths",
            },
            {
                "id": "probe2",
                "command": P2,
                "result": "PASS",
                "role": "per-character-mask-fails-fixed-width",
            },
        ],
        "notes": (
            "G-1 for TST-0212: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild. SUCCESS:TST-0212"
        ),
        "output_schema": SCHEMA_REL,
        "probe1_raw": p1,
        "probe2_raw": p2,
        "question": QUESTION,
        "report_kind": "security_report",
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0212-probe2-per-character-mask",
            "scope_not_agreement": True,
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "tests": [
            {
                "id": "probe1-prefix-and-fixed-width",
                "name": "prefix readable; five lengths share one mask width",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-per-char-mask-fails",
                "name": "per-character mask fails the fixed-width assertion",
                "command": P2,
                "result": "PASS",
            },
        ],
        "tests_required": {
            "both_states_prefix_still_readable": True,
            "negative_per_character_mask_fails_fixed_width": True,
        },
        "title": "Masking keeps the zero-entropy prefix and leaks no length",
        "ts": now,
        "unit_id": UNIT,
    }

    errs = validate(doc, SCHEMA_REL) + validate(doc, TEST_SCHEMA_REL)
    if errs:
        print("FAILED:TST-0212 emit schema")
        print("\n".join(errs[:20]))
        return 1

    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:TST-0212 emit sentinel missing")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
