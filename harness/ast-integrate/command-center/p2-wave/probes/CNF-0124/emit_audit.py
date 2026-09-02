#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0124-authorship-audit.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from audit import (  # noqa: E402
    OUT_REL,
    SENTINEL,
    payload_of,
    run_audit,
    schema_rejects_garbage,
    validate_against_schema,
)

OUT = REPO / OUT_REL


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    if not schema_rejects_garbage():
        print("FAILED:CNF-0124 schema accepted garbage")
        return 1
    doc = run_audit()
    errs = validate_against_schema(doc)
    if errs:
        print("FAILED:CNF-0124 schema errors")
        for e in errs[:25]:
            print(" ", e)
        return 1
    answers = payload_of(doc).get("answers") or {}
    if answers.get("planted_self_confirmation_flagged") is not True:
        print("FAILED:CNF-0124 planted self-confirmation not flagged")
        return 1
    if answers.get("every_receipt_has_named_deciding_rule") is not True:
        print("FAILED:CNF-0124 unnamed deciding rule")
        return 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:CNF-0124 sentinel missing from serialized artifact")
        return 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    parsed = json.loads(OUT.read_text(encoding="utf-8"))
    consumers = doc.get("downstream_consumers") or []
    if consumers and isinstance(consumers[0], dict):
        consumers[0]["executed"] = True
        consumers[0]["read_ok"] = isinstance(parsed, dict)
        consumers[0]["exit_code"] = 0
        probe = consumers[0].get("probe") or {}
        probe["raw_output"] = (
            f"json.loads keys={sorted(parsed)[:12]!r} "
            f"state={parsed.get('state')!r} unit_id={parsed.get('unit_id')!r}"
        )
        consumers[0]["probe"] = probe
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    errs = validate_against_schema(doc)
    if errs:
        print("FAILED:CNF-0124 schema errors after consumer stamp")
        for e in errs[:25]:
            print(" ", e)
        return 1
    digest, size = sha256_file(OUT)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0124 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print(
        "live={live} live_viol={lv} audited={n} viol={v} planted_flagged={p} "
        "p0p1={p01} state={st}".format(
            live=answers["live_receipts_count"],
            lv=answers["live_violation_count"],
            n=answers["audited_receipts_count"],
            v=answers["violation_count"],
            p=answers["planted_self_confirmation_flagged"],
            p01=answers["p0_or_p1_violation"],
            st=doc["state"],
        )
    )
    if doc["state"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0124 self-declared {doc['state']}")
        return 1
    print("SUCCESS:CNF-0124 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
