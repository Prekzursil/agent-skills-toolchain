#!/usr/bin/env python3
"""Probe 1: table shape, dual rails, capture re-hash, both-states missing column.

Starts from the artifact and the capture files. A planted row that drops
installed_client must fail; the live table must pass.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from facts import load_bytes, sha256_bytes  # noqa: E402
from schema_local import domain, garbage_accepted, iter_errors  # noqa: E402

UNIT = "RES-0053"
ART = REPO / "command-center/research/RES-0053.json"
SENTINEL = (
    "SUCCESS:RES-0053 in the receipt AND a per-registry revocation table "
    "with a separate installed-client column and one cited incident"
)
NEED_REGISTRIES = {
    "npm",
    "pypi",
    "crates.io",
    "vs-code-marketplace",
    "jetbrains-marketplace",
    "chrome-web-store",
}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0053-probe1 {msg}")
    return 1


def table_ok(doc: dict) -> tuple[bool, str]:
    body = domain(doc)
    rows = body.get("revocation_table")
    if not isinstance(rows, list) or len(rows) < 6:
        return False, "table-short"
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            return False, "row-not-object"
        rid = row.get("registry")
        ic = row.get("installed_client")
        act = row.get("registry_action")
        if not isinstance(rid, str) or not rid:
            return False, "missing-registry"
        if not isinstance(act, str) or len(act) < 8:
            return False, "missing-registry_action"
        if not isinstance(ic, str) or len(ic) < 24:
            return False, f"missing-installed_client:{rid}"
        if "installed_client" not in row:
            return False, f"no-installed_client-key:{rid}"
        seen.add(rid)
    missing = NEED_REGISTRIES - seen
    if missing:
        return False, f"missing-registries:{sorted(missing)}"
    incident = body.get("cited_incident") or {}
    ux = incident.get("what_installed_users_experienced")
    if not isinstance(ux, str) or len(ux) < 40:
        return False, "incident-ux-thin"
    return True, "ok"


def rails_ok(doc: dict) -> tuple[bool, str]:
    for claim in domain(doc).get("claims") or []:
        rails = claim.get("rails") or []
        kinds = {r.get("kind") for r in rails if isinstance(r, dict)}
        if len(rails) < 2:
            return False, f"{claim.get('id')}:need-two-rails"
        if "api" not in kinds or "prose" not in kinds:
            # incident claim uses api+prose; chrome uses api-labeled help
            if kinds != {"api", "prose"}:
                return False, f"{claim.get('id')}:kinds={kinds}"
        for r in rails:
            for key in ("permalink", "fetch_timestamp", "http_status", "sha256"):
                if r.get(key) in (None, ""):
                    return False, f"{claim.get('id')}:missing-{key}"
            path = r.get("captured_path")
            if not path:
                return False, f"{claim.get('id')}:no-captured_path"
            fp = REPO / path
            if not fp.is_file():
                return False, f"absent:{path}"
            digest = sha256_bytes(fp.read_bytes())
            if digest != r.get("sha256"):
                return False, f"sha-mismatch:{path}"
            cid = Path(path).stem
            if load_bytes(cid) != fp.read_bytes():
                return False, f"body-mismatch:{cid}"
    return True, "ok"


def main() -> int:
    if not ART.is_file():
        return fail("artifact-absent")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errs = iter_errors(doc)
    if errs:
        loc = "/".join(str(p) for p in errs[0].absolute_path) or "<root>"
        return fail(f"schema:{loc}:{errs[0].message}")
    vacuous = garbage_accepted()
    if vacuous is not None:
        return fail(f"schema-vacuous:{list(vacuous)[:3]}")
    kind_mutant = copy.deepcopy(doc)
    if isinstance(kind_mutant.get("report"), dict):
        kind_mutant["report"]["kind"] = "audit-finding"
        if not iter_errors(kind_mutant):
            return fail("kind-pin-silent")
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        return fail("sentinel-absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    ok, why = table_ok(doc)
    if not ok:
        return fail(why)
    ok, why = rails_ok(doc)
    if not ok:
        return fail(why)

    mutant = copy.deepcopy(doc)
    del domain(mutant)["revocation_table"][0]["installed_client"]
    m_ok, m_why = table_ok(mutant)
    if m_ok:
        return fail("missing-installed_client-mutant-silent")
    live_ok, _ = table_ok(doc)
    if not live_ok:
        return fail("live-table-failed")

    print(f"table_ok={live_ok} mutant_missing_column_fires={not m_ok} ({m_why})")
    print(f"registries={sorted(NEED_REGISTRIES)}")
    print("SUCCESS:RES-0053-probe1 table dual-rail rehash both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
