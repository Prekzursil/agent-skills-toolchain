#!/usr/bin/env python3
"""Named probe 2: deliberate-violation build is flagged; credential bodies omitted."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from auditor import (
    audit_archive,
    credential_body_leaked,
    dump_report_text,
    load_rules,
)
from constants import (
    OUTPUT_REL,
    PLANTED_CREDENTIAL_BODY,
    PLANTED_ENV,
    PLANTED_GIT,
    PLANTED_OVERSIZE,
    POLLUTED_ZIP_REL,
    REPO,
    SENTINEL,
    UNIT_ID,
)
from contract import domain, schema_errors, schema_rejects_garbage
from scenario import write_polluted_zip


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0102-probe2 {msg}")
    return 1


def assert_no_canary(label: str, text: str) -> str | None:
    if credential_body_leaked(text, PLANTED_CREDENTIAL_BODY):
        return f"{label} contains planted credential body"
    return None


def main() -> int:
    art_path = REPO / OUTPUT_REL
    if not art_path.is_file() or art_path.stat().st_size <= 0:
        return fail("confirmation artifact missing")
    text = art_path.read_text(encoding="utf-8")
    leaked = assert_no_canary("artifact", text)
    if leaked:
        return fail(leaked)
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != UNIT_ID:
        return fail(f"unit_id {doc.get('unit_id')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    vacuous = schema_rejects_garbage()
    if vacuous:
        return fail(vacuous)
    errs = schema_errors(doc)
    if errs:
        return fail("schema-invalid " + "; ".join(errs[:8]))

    payload = domain(doc)
    control = payload.get("deliberate_violation_control") or {}
    if control.get("built") is not True or control.get("flagged") is not True:
        return fail("control not built+flagged in artifact")
    if control.get("credential_bodies_omitted") is not True:
        return fail("artifact did not record credential_bodies_omitted")
    if PLANTED_GIT not in (control.get("planted_paths") or []):
        return fail("planted .git/config missing from artifact control")

    rules = load_rules()
    with tempfile.TemporaryDirectory(prefix="cnf0102-p2-") as tmp:
        polluted = Path(tmp) / "polluted.zip"
        write_polluted_zip(polluted, int(rules["max_single_file_bytes"]))
        report = audit_archive(polluted, rules)
        report_text = dump_report_text(report)
        leaked = assert_no_canary("auditor-report", report_text)
        if leaked:
            return fail(leaked)
        by_path = {e["path"]: e["flags"] for e in report["entries"]}
        if PLANTED_GIT not in by_path:
            return fail("planted .git/config missing from archive listing")
        if "repo-metadata" not in by_path[PLANTED_GIT]:
            return fail(".git/config not flagged repo-metadata")
        if PLANTED_ENV not in by_path:
            return fail("planted .env missing from archive listing")
        if "credential-filename" not in by_path[PLANTED_ENV]:
            return fail(".env not flagged credential-filename")
        if PLANTED_OVERSIZE not in by_path:
            return fail("planted oversized member missing from archive listing")
        if "oversized-file" not in by_path[PLANTED_OVERSIZE]:
            return fail("oversized member not flagged")
        flagged = [p for p, flags in by_path.items() if flags]
        if PLANTED_GIT not in flagged:
            return fail("primary violation not in flagged set")

        # Confirm the body is inside the zip but was not copied into the report.
        import zipfile

        with zipfile.ZipFile(polluted, "r") as zf:
            planted_body = zf.read(PLANTED_ENV).decode("utf-8")
        if planted_body != PLANTED_CREDENTIAL_BODY:
            return fail("polluted zip credential member missing planted body")
        if PLANTED_CREDENTIAL_BODY in json.dumps(report, default=str):
            return fail("auditor report json contains planted body")

    stored = REPO / POLLUTED_ZIP_REL
    if stored.is_file():
        stored_rep = audit_archive(stored, rules)
        leaked = assert_no_canary("stored-polluted-report", dump_report_text(stored_rep))
        if leaked:
            return fail(leaked)
        stored_flags = {
            e["path"]: e["flags"] for e in stored_rep["entries"]
        }
        if "repo-metadata" not in stored_flags.get(PLANTED_GIT, []):
            return fail("stored polluted zip did not flag .git/config")

    print(
        "control_flagged=True repo-metadata=True credential-filename=True "
        "oversized-file=True credential_bodies_omitted=True"
    )
    print("SUCCESS:CNF-0102-probe2 deliberate-violation control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
