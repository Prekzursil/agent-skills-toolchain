#!/usr/bin/env python3
"""Probe 2: already-published T+0 RED control and braces vulnerable/patched date-cut."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import measure as M  # noqa: E402
import scan as S  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:RES-0132-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    live = M.run()
    db = S.CaptureDB()
    t0 = S.parse_ts("2024-05-01T00:00:00Z")
    t30 = S.parse_ts("2024-05-31T00:00:00Z")
    product_t0 = S.parse_ts("2026-07-25T00:00:00Z")
    assert t0 and t30 and product_t0

    lodash = S.package_verdict(
        db, {"name": "lodash", "version": "4.17.11", "ecosystem": "npm"}, t0
    )
    requests_old = S.package_verdict(
        db, {"name": "requests", "version": "2.25.1", "ecosystem": "PyPI"}, t0
    )
    braces_vuln_t0 = S.package_verdict(
        db, {"name": "braces", "version": "3.0.2", "ecosystem": "npm"}, t0
    )
    braces_vuln_t30 = S.package_verdict(
        db, {"name": "braces", "version": "3.0.2", "ecosystem": "npm"}, t30
    )
    braces_patched = S.package_verdict(
        db, {"name": "braces", "version": "3.0.3", "ecosystem": "npm"}, t30
    )
    lodash_product = S.package_verdict(
        db, {"name": "lodash", "version": "4.17.11", "ecosystem": "npm"}, product_t0
    )

    fires = lodash["verdict"] == "RED" and requests_old["verdict"] == "RED"
    silent_patched = braces_patched["verdict"] == "GREEN"
    date_cut = braces_vuln_t0["verdict"] == "GREEN" and braces_vuln_t30["verdict"] == "RED"
    both_states = fires and silent_patched and date_cut

    print(
        json.dumps(
            {
                "lodash_t0": lodash["verdict"],
                "lodash_t0_ids": lodash["advisory_ids"],
                "requests_2_25_1_t0": requests_old["verdict"],
                "requests_t0_ids": requests_old["advisory_ids"],
                "braces_3_0_2_t0": braces_vuln_t0["verdict"],
                "braces_3_0_2_t30": braces_vuln_t30["verdict"],
                "braces_3_0_3_t30": braces_patched["verdict"],
                "lodash_still_red_at_product_t0": lodash_product["verdict"] == "RED",
                "second_signal_all_agree": live["second_signal"]["all_agree_utc_date"],
                "fires_on_already_published": fires,
                "silent_on_patched_pin": silent_patched,
                "date_cut_works": date_cut,
                "both_states": both_states,
            },
            sort_keys=True,
        )
    )

    if not fires:
        return fail("already-published control was not RED at T+0")
    if "GHSA-jf85-cpcp-j695" not in lodash["advisory_ids"] and not any(
        i.startswith("GHSA-jf85") for i in lodash["advisory_ids"]
    ):
        # Cluster first_id may be an earlier alias; require the CVE-2019-10744 cluster.
        cluster_ids = set(lodash["advisory_ids"])
        aliases = set()
        for cl in lodash.get("clusters") or []:
            aliases.update(cl.get("ghsa_ids") or [])
            aliases.update(cl.get("member_ids") or [])
        if "GHSA-jf85-cpcp-j695" not in cluster_ids and "GHSA-jf85-cpcp-j695" not in aliases:
            return fail("lodash T+0 missed GHSA-jf85-cpcp-j695 cluster")
    if "GHSA-j8r2-6x86-q33q" not in requests_old["advisory_ids"]:
        aliases = set(requests_old["advisory_ids"])
        for cl in requests_old.get("clusters") or []:
            aliases.update(cl.get("ghsa_ids") or [])
            aliases.update(cl.get("member_ids") or [])
        if "GHSA-j8r2-6x86-q33q" not in aliases:
            return fail("requests 2.25.1 T+0 missed GHSA-j8r2-6x86-q33q")
    if not date_cut:
        return fail("braces@3.0.2 date cut did not go GREEN→RED")
    if not silent_patched:
        return fail("braces@3.0.3 patched pin was not GREEN at T+30")
    if lodash_product["verdict"] != "RED":
        return fail("lodash not RED at product T+0; date cut may be blind")
    if not live["second_signal"]["all_agree_utc_date"]:
        return fail("GitHub/OSV UTC dates disagree")
    if not both_states:
        return fail("both_states false")

    if doc.get("control_t0_all_red") is not True:
        return fail("artifact control_t0_all_red is not true")
    braces = doc.get("both_states_braces") or {}
    if braces.get("date_cut_works") is not True:
        return fail("artifact braces date_cut_works is not true")
    if braces.get("t30_patched") != "GREEN":
        return fail("artifact patched pin not GREEN")
    if doc.get("lodash_still_red_at_product_t0") is not True:
        return fail("artifact lodash_still_red_at_product_t0 is not true")
    sig = doc.get("second_signal") or {}
    if sig.get("all_agree_utc_date") is not True:
        return fail("artifact second_signal disagree")

    art_lock = {r["id"]: r for r in (doc.get("lockfiles") or [])}
    for lid in ("control-red-npm-lodash-4.17.11", "control-red-pip-requests-2.25.1"):
        row = art_lock.get(lid)
        if not row:
            return fail(f"artifact missing {lid}")
        if row.get("T+0", {}).get("verdict") != "RED":
            return fail(f"artifact {lid} T+0 not RED")
        live_row = next(r for r in live["lockfiles"] if r["id"] == lid)
        if live_row["T+0"]["verdict"] != "RED":
            return fail(f"live {lid} T+0 not RED")

    rev = doc.get("reviewer") or {}
    if rev.get("verdict") != "PASS" or rev.get("independent") is not True:
        return fail("reviewer record missing")

    tests = {t["id"]: t.get("result") for t in (doc.get("tests") or []) if isinstance(t, dict)}
    if tests.get("both-states-already-published-control") != "PASS":
        return fail("artifact both-states test not PASS")

    print("reviewer_id=" + str(rev.get("reviewer_id")))
    print("SUCCESS:RES-0132-probe2 both-states control-red and patched-pin silence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
