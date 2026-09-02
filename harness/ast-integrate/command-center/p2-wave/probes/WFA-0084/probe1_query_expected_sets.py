#!/usr/bin/env python3
"""Probe 1: each query type matches an independently computed expected set.

Also: empty selector returns EMPTY (ids=[]), never an ERROR a caller could
read as zero. Results carry the artifact version they were computed from.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import expected as E  # noqa: E402
import query as Q  # noqa: E402

from contract import OUT_REL, SENTINEL  # noqa: E402

ART = REPO / OUT_REL
FIX = HERE / "fixtures"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0084-probe1 {msg}")
    return 1


def expected_does_not_import_query() -> bool:
    tree = ast.parse((HERE / "expected.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "query" or alias.name.startswith("query."):
                    return False
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod == "query" or mod.startswith("query."):
                return False
    return True


def main() -> int:
    if not expected_does_not_import_query():
        return fail("expected.py imports query.py; evidence A is not independent")

    qi = Q.load_fixture_interface(HERE)
    mismatches = []
    empty_ok = []
    nonempty = []
    for qtype, selector in E.CASES:
        got = qi.query(qtype, selector)
        want = E.ids_for(FIX, qtype, selector)
        if not got.get("ok"):
            mismatches.append((qtype, selector, "interface-error", got.get("error"), want))
            continue
        got_ids = list(got.get("ids") or [])
        if got_ids != want:
            mismatches.append((qtype, selector, got_ids, want))
            continue
        av = got.get("artifact_version") or {}
        if not av.get("corpus_sha256") or not av.get("files"):
            return fail(f"{qtype}/{selector} missing artifact_version")
        if got.get("interface_version") != Q.INTERFACE_VERSION:
            return fail("interface_version drift")
        if got.get("schema_fingerprint") != Q.SCHEMA_FINGERPRINT:
            return fail("schema_fingerprint drift")
        if want == []:
            if got.get("status") != "EMPTY" or got.get("empty") is not True:
                return fail(f"{qtype}/{selector} zero hits not EMPTY")
            if got.get("ids") != []:
                return fail(f"{qtype}/{selector} empty ids not []")
            if got.get("error") is not None:
                return fail(f"{qtype}/{selector} empty carried error")
            empty_ok.append(f"{qtype}:{selector}")
        else:
            if got.get("status") != "OK" or got.get("empty") is not False:
                return fail(f"{qtype}/{selector} hits not OK")
            nonempty.append(f"{qtype}:{selector}={len(want)}")

    if mismatches:
        print(json.dumps(mismatches[:8], sort_keys=True))
        return fail(f"expected-set mismatches n={len(mismatches)}")

    bogus = qi.query("not-a-type", "x")
    if bogus.get("ids") == []:
        return fail("error result used ids=[] which a caller could read as zero")
    if bogus.get("ok") is not False or bogus.get("status") != "ERROR":
        return fail(f"unknown type not ERROR {bogus}")
    if bogus.get("ids") is not None:
        return fail("error ids must be null")
    try:
        Q.require_ids(bogus)
        return fail("require_ids did not raise on ERROR")
    except Q.QueryError:
        pass
    try:
        Q.require_ids(qi.query("family", "no-such-family"))
    except Q.QueryError:
        return fail("require_ids raised on legitimate empty")

    fusible = set(Q.require_ids(qi.query("fusibility", "fusible")))
    naive = E.load_compat_pairs(FIX)
    if not fusible or not (len(fusible) < len(naive)):
        return fail(
            f"fusible={len(fusible)} naive_compat={len(naive)} conflict subtraction missing"
        )

    if not ART.is_file():
        return fail("handoff artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    recorded = ((doc.get("evidence") or {}).get("signal_a") or {}).get("cases_matched")
    if recorded != len(E.CASES):
        return fail(f"artifact signal_a cases_matched={recorded} live={len(E.CASES)}")

    print(
        json.dumps(
            {
                "probe": "probe1-query-expected-sets",
                "unit_id": "WFA-0084",
                "cases": len(E.CASES),
                "empty_selectors": empty_ok,
                "nonempty": nonempty,
                "fusible": sorted(fusible),
                "naive_compat": sorted(naive),
                "corpus_sha256": qi.artifact_version["corpus_sha256"],
            },
            sort_keys=True,
        )
    )
    print(
        f"cases={len(E.CASES)} empty={len(empty_ok)} nonempty={len(nonempty)} "
        f"fusible={len(fusible)} naive={len(naive)}"
    )
    print("SUCCESS:WFA-0084-probe1 query types match independent expected sets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
