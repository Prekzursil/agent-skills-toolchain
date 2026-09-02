#!/usr/bin/env python3
"""Probe 1: conflict detector control.

Plant a judge whose id matches an artifact author and assert recusal fires.
Also plant a provenance-vendor match against a live lens file, a catalog-vendor
match, and a clean pairing that must remain eligible (both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402
import conflicts as X  # noqa: E402
import panel_spec as S  # noqa: E402

PLANTED = HERE / "fixtures" / "planted-lens.json"
STANDIN = HERE / "fixtures" / "a2-authorship-standin.json"


def fail(msg: str) -> int:
    print(f"FAILED:ARC-0066-probe1 {msg}")
    return 1


def live_cursor_row(report: dict) -> tuple[dict | None, str]:
    """Prefer live A2 DESIGN; else any present lens with produced_by.vendor=cursor."""
    a2 = C.row_by_unit(report, "ARC-0010")
    if (
        a2
        and a2.get("present")
        and C.norm((a2.get("authorship") or {}).get("vendor")) == "cursor"
    ):
        return a2, "A2 DESIGN"
    for row in report.get("rows") or []:
        if not row.get("present"):
            continue
        if C.norm((row.get("authorship") or {}).get("vendor")) == "cursor":
            label = f"{row.get('unit_id')} {row.get('path')}"
            return row, label
    return None, ""


def standin_row(catalog_row: dict) -> dict:
    doc = json.loads(STANDIN.read_text(encoding="utf-8"))
    auth = C.extract_authorship(doc)
    if C.norm(auth.get("vendor")) != "cursor":
        raise SystemExit("stand-in vendor drifted from cursor")
    row = dict(catalog_row)
    row["present"] = True
    row["authorship"] = auth
    row["provenance_gap"] = None
    return row


def planted_row() -> dict:
    doc = json.loads(PLANTED.read_text(encoding="utf-8"))
    auth = C.extract_authorship(doc)
    if auth.get("author_id") != "judge.planted.self-author":
        raise SystemExit("planted fixture author_id drifted")
    return {
        "unit_id": doc.get("unit_id"),
        "path": "command-center/p2-wave/probes/ARC-0066/fixtures/planted-lens.json",
        "present": True,
        "catalog": {"vendor": "planted-catalog-vendor", "vendors": ["planted-catalog-vendor"]},
        "authorship": auth,
        "provenance_gap": None,
    }


def main() -> int:
    report = C.census()
    if report["enumerated"] != 63:
        return fail(f"enumerated={report['enumerated']} want 63")
    a2, label = live_cursor_row(report)
    if a2 is None:
        catalog_a2 = C.row_by_unit(report, "ARC-0010")
        if catalog_a2 is None:
            return fail("ARC-0010 missing from catalog")
        a2 = standin_row(catalog_a2)
        label = "stand-in A2 authorship (live DESIGN.json absent)"
        print(f"NOTE: {label}")
    if C.norm((a2.get("authorship") or {}).get("vendor")) != "cursor":
        return fail(
            f"{label} produced_by.vendor expected cursor, got {a2.get('authorship')}"
        )

    planted = planted_row()
    id_judge = {
        "judge_id": "judge.planted.self-author",
        "vendor": "google",
        "model": "gemini",
    }
    id_hit = X.recusal(id_judge, planted)
    id_codes = [r["code"] for r in id_hit["reasons"]]
    print(
        f"plant_id recused={id_hit['recused']} reasons={id_codes} "
        f"author_id={planted['authorship']['author_id']}"
    )
    if not id_hit["recused"] or "AUTHOR_ID_MATCH" not in id_codes:
        return fail("planted author_id judge was not recused")

    # Same judge against a live artifact they did not author: must stay eligible
    # (google is neither cursor nor anthropic).
    id_clean = X.recusal(id_judge, a2)
    print(f"plant_id vs {label} recused={id_clean['recused']} (want False)")
    if id_clean["recused"]:
        return fail("author_id plant leaked into an unrelated live artifact")

    cursor_judge = {
        "judge_id": "judge.cursor.grok-plant",
        "vendor": "cursor",
        "model": "grok-4.6",
    }
    prov = X.recusal(cursor_judge, a2)
    prov_codes = [r["code"] for r in prov["reasons"]]
    print(f"plant_vendor=cursor vs {label} recused={prov['recused']} reasons={prov_codes}")
    if not prov["recused"] or "PROVENANCE_VENDOR" not in prov_codes:
        return fail("cursor vendor plant did not recuse on live produced_by")

    cat_vendor = C.norm((a2.get("catalog") or {}).get("vendor"))
    if not cat_vendor:
        return fail("catalog vendor missing on target row")
    catalog_judge = {
        "judge_id": f"judge.{cat_vendor}.opus",
        "vendor": cat_vendor,
        "model": "opus",
    }
    cat = X.recusal(catalog_judge, a2)
    cat_codes = [r["code"] for r in cat["reasons"]]
    print(
        f"catalog vendor={cat_vendor} vs {label} recused={cat['recused']} "
        f"reasons={cat_codes}"
    )
    if not cat["recused"] or "CATALOG_VENDOR" not in cat_codes:
        return fail("catalog assignment vendor did not recuse")

    clean_vendor = "google"
    if clean_vendor in {cat_vendor, "cursor"}:
        clean_vendor = "mistral"
    clean = {
        "judge_id": f"judge.{clean_vendor}.clean",
        "vendor": clean_vendor,
        "model": "clean",
    }
    ok = X.recusal(clean, a2)
    print(f"clean google vs {label} recused={ok['recused']} (want False)")
    if ok["recused"]:
        return fail("clean judge was recused")

    # Self-declaration cannot waive: a conflicted judge claiming independence.
    declared_independent = dict(cursor_judge)
    declared_independent["self_declared_independent"] = True
    waived = X.recusal(declared_independent, a2)
    if not waived["recused"]:
        return fail("self-declaration waived recusal")

    q = X.quorum_check(S.SEATED, a2, S.QUORUM_MINIMUM)
    print(
        f"seated quorum on {label} eligible={q['eligible_count']} "
        f"ok={q['ok']} ids={q['eligible_judge_ids']}"
    )
    if not q["ok"]:
        return fail("seated panel drops below quorum on a present lens")

    print(
        "fired_on_planted_id=True fired_on_provenance_vendor=True "
        "fired_on_catalog_vendor=True silent_on_clean=True "
        "self_declaration_ignored=True"
    )
    print("SUCCESS:ARC-0066-probe1 conflict detector recusal fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
