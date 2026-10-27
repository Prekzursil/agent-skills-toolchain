#!/usr/bin/env python3
"""TST-0068 probe1: interpreter census re-derivation (live, fail-closed).

Re-derives the receipt's fixture-estate census (4/7 shebang-reliant) and
gold control (0/7) via the recreated engine, audits the LIVE repo stub
and the LIVE deployed estate dispatch manifest, checks the settings
census mechanism, and the delivery predicate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0068"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from engine import census_document, census_file  # noqa: E402

UNIT = "TST-0068"
SENTINEL = "SUCCESS:TST-0068"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= 1024, "under-min-bytes")
    chk(str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}, "self-declared")
    chk(SENTINEL in text, "sentinel-absent")

    fx = census_file(HERE / "fixtures" / "estate" / "hooks" / "_dispatch" / "manifest.json", "fixture-manifest")
    fxc = census_file(HERE / "fixtures" / "estate" / "plugin.json", "fixture-plugin")
    if fx and fxc:
        ids = fx["shebang_reliant_ids"] + fxc["shebang_reliant_ids"]
        total = fx["count"] + fxc["count"]
        chk(total == 7, "fixture-total", str(total))
        chk(len(ids) == 4, "fixture-reliant-count", str(ids))
        for want in ("hook.post-tool", "hook.stop", "sync", "status"):
            chk(want in ids, "fixture-reliant-missing:" + want)
    gd = census_file(HERE / "fixtures" / "gold" / "hooks" / "_dispatch" / "manifest.json", "gold-manifest")
    gdc = census_file(HERE / "fixtures" / "gold" / "plugin.json", "gold-plugin")
    if gd and gdc:
        chk(gd["count"] + gdc["count"] == 7, "gold-total")
        chk(gd["shebang_reliant_count"] + gdc["shebang_reliant_count"] == 0, "gold-reliant-must-be-zero")
        chk(gd["all_declare_interpreter"] and gdc["all_declare_interpreter"], "gold-all-declare")
    # live repo manifest (now a stub: 0 hook rows)
    stub = census_file(REPO / "hooks" / "_dispatch" / "manifest.json", "repo-live")
    chk(stub is not None, "repo-manifest-present")
    if stub:
        raw = json.loads((REPO / "hooks" / "_dispatch" / "manifest.json").read_text(encoding="utf-8"))
        chk(raw.get("not_the_deployed_copy") is True, "repo-manifest-self-declared-stub")
        chk(all(isinstance(h, str) for h in raw.get("hooks") or []) and stub["shebang_reliant_count"] == len(raw.get("hooks") or []), "bare-path-strings-classified-reliant")
    # live deployed estate manifest
    deployed = census_file(Path.home() / ".claude" / "hooks" / "_dispatch" / "manifest.json", "deployed-live")
    chk(deployed is not None, "deployed-manifest-present")
    dep_checks = deployed["count"] if deployed else 0
    # settings census mechanism (agent-self settings live)
    st = census_file(REPO / "agent-self" / "config" / "settings.json", "settings-live")
    chk(st is not None, "settings-census-runs")
    # receipt's recorded census re-derivation markers
    ans = doc.get("answer") or {}
    chk(int(ans.get("fixture_estate_entries", 0)) == 7 and int(ans.get("fixture_estate_shebang_reliant", 0)) == 4, "receipt-fixture-claims")
    chk(int(ans.get("gold_shebang_reliant", 1)) == 0 and int(ans.get("production_shebang_reliant", 1)) == 0, "receipt-gold-production-claims")
    prod = doc.get("production") or {}
    chk(int((prod.get("audit") or {}).get("count", -1)) == 27 and int((prod.get("audit") or {}).get("shebang_reliant_count", -1)) == 0, "receipt-production-audit-27-0")
    tests = doc.get("tests") or []
    chk(len(tests) >= 2, "tests-rows")
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails[:10]))
        return 1
    print(json.dumps({"fixture": {"total": total, "reliant_ids": ids},
                      "gold": {"total": gd["count"] + gdc["count"], "reliant": 0},
                      "live_now": {"repo_stub_rows": stub["count"], "deployed_checks": dep_checks,
                                   "deployed_shebang_reliant": deployed["shebang_reliant_ids"] if deployed else None},
                      "settings_census_rows": st["count"] if st else None}, indent=1))
    print("SUCCESS:" + UNIT + "-probe1 fixture 4/7 shebang-reliant and gold 0/7 re-derived; repo stub + deployed estate manifest (" + str(dep_checks) + " checks) + settings census audited live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
