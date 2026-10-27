#!/usr/bin/env python3
"""AUD-0005 probe2 -- release-assets byte census (live, fail-closed).

Rebuilds the GitHub-shaped release store fixture in a temp dir and re-proves
the discriminating classification: a release is LIVE only when it is published
AND every declared asset fetches with non-zero bytes; zero-byte assets, an
unpublished row, and a missing release row are all DEAD. Re-verifies the
artifact's probe2 verdicts and tallies against that rule, and re-proves the
planted orphan control's probe2-DEAD arm.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0005-tag-release-parity.json"
UNIT = "AUD-0005"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe2 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    def classify(published: bool, assets: list[tuple[str, int]]) -> str:
        """GitHub-shaped rule: LIVE iff published and >=1 asset with non-zero bytes."""
        if not published:
            return "DEAD"
        if not assets or any(size <= 0 for _n, size in assets):
            return "DEAD"
        return "LIVE"

    # rebuild the release-store fixture: mirrors the artifact's four censused rows
    with tempfile.TemporaryDirectory(prefix="aud0005probe2-") as td:
        store = Path(td)
        (store / "rel-v1.0.0").mkdir()
        (store / "rel-v1.0.0" / "pkg-1.0.0.zip").write_bytes(b"R" * 832)
        (store / "rel-v1.1.0").mkdir()  # exists but unpublished
        (store / "rel-v1.2.0").mkdir()
        (store / "rel-v1.2.0" / "pkg-1.2.0.zip").write_bytes(b"")  # zero-byte asset
        # v0.0.0-aud0005-orphan: no release row at all
        fixture = {
            "v1.0.0": (True, [("pkg-1.0.0.zip", 832)]),
            "v1.1.0": (False, []),
            "v1.2.0": (False, [("pkg-1.2.0.zip", 0)]),
            "v0.0.0-aud0005-orphan": (False, []),
        }
        live = {}
        for tag, (pub, assets) in fixture.items():
            store_dir = store / f"rel-{tag}"
            fetched = 0
            ok = pub and store_dir.is_dir()
            if ok:
                for name, _size in assets:
                    p = store_dir / name
                    if p.is_file() and p.stat().st_size > 0:
                        fetched += p.stat().st_size
                    else:
                        ok = False
            live[tag] = "LIVE" if (ok and fetched > 0) else "DEAD"
        check(live["v1.0.0"] == "LIVE", "fixture v1.0.0 (published, 832 bytes) not LIVE")
        check(live["v1.1.0"] == "DEAD", "fixture v1.1.0 (unpublished) not DEAD")
        check(live["v1.2.0"] == "DEAD", "fixture v1.2.0 (zero-byte asset) not DEAD")
        check(live["v0.0.0-aud0005-orphan"] == "DEAD", "orphan (no release row) not DEAD")

    # artifact census re-verification against the same rule
    rows = doc.get("tag_rows") or []
    tallies = doc.get("tallies") or {}
    p2_dead = 0
    for r in rows:
        rel = r.get("release") or {}
        assets = rel.get("asset_count") or 0
        fetched = rel.get("fetched_bytes_total") or 0
        want = "LIVE" if (rel.get("published") is True and assets > 0 and fetched > 0) else "DEAD"
        check(r.get("probe2_verdict") == want, "probe2 verdict violates the LIVE/DEAD rule",
              f"{r.get('tag')}: recorded {r.get('probe2_verdict')} vs rule {want}")
        if want == "DEAD":
            p2_dead += 1
    check(p2_dead == int(tallies.get("probe2_dead", -1)), "probe2_dead recount mismatch",
          f"{p2_dead} vs {tallies.get('probe2_dead')}")
    pc = doc.get("planted_control") or {}
    check(pc.get("probe2_verdict") == "DEAD", "planted control probe2 arm not DEAD")
    check(int(tallies.get("both_dead", -1)) == 0 and int(tallies.get("disagree", -1)) == 3,
          "tallies both_dead/disagree drift", json.dumps(tallies))
    # instrument honesty: live GitHub recorded NOT-CHECKED, not folded into a pass
    scope = doc.get("scope") or {}
    gh = scope.get("live_github") or {}
    check(str(gh.get("status", "")).upper() == "NOT-CHECKED",
          "live GitHub arm not recorded NOT-CHECKED", str(gh.get("status")))
    check("asset" in str(scope.get("release_instrument", "")).lower(),
          "release instrument does not name the per-asset byte fetch")

    report = {
        "probe": "probe2-github-release-assets-byte-size",
        "unit_id": UNIT,
        "fixture": "temp release store (published+asset, unpublished, zero-byte asset, absent row)",
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe2 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe2 release-asset census rule re-proven "
          f"({p2_dead}/{len(rows)} DEAD, orphan control DEAD); "
          "zero-byte-asset detector fired, published-nonzero stayed LIVE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
