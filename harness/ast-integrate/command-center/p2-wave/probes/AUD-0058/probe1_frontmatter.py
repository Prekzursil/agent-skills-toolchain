#!/usr/bin/env python3
"""Named probe 1: frontmatter census and declared load-class classification.

Signal: YAML-fence parse + `paths` key presence. This probe does not read a
turn-zero context bag. Planted lazy (paths present) must classify LAZY;
planted always-on and the no-frontmatter rule must classify ALWAYS-ON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classifier import classify_tree  # noqa: E402
from common import OUT, UNIT  # noqa: E402
from fixtures import ensure_fixtures  # noqa: E402
from inventory import repo_skill_tree  # noqa: E402
from measure import live_census  # noqa: E402

ART = OUT


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:AUD-0058" not in blob:
        return fail("sentinel absent")

    src = ensure_fixtures()
    classified = classify_tree(src)
    by_id = {r["id"]: r for r in classified}
    for sid, want in (
        ("always-on", "ALWAYS-ON"),
        ("lazy-scoped", "LAZY"),
        ("rules.common.no-frontmatter.md", "ALWAYS-ON"),
        ("demoted-star", "LAZY"),
    ):
        got = (by_id.get(sid) or {}).get("declared_load_class")
        if got != want:
            return fail(f"declared class {sid} want {want} got {got}", by_id.get(sid))
    if by_id["rules.common.no-frontmatter.md"]["has_frontmatter"] is not False:
        return fail("bare rule unexpectedly has frontmatter")
    if by_id["lazy-scoped"]["paths_key_present"] is not True:
        return fail("lazy fixture missing paths key")
    if by_id["always-on"]["paths_key_present"] is not False:
        return fail("always-on fixture has paths key")

    live = live_census()
    repo = repo_skill_tree()
    repo_rows = classify_tree(repo) if repo.is_dir() else []
    art_repo = (doc.get("measurement") or {}).get("live") or {}
    if art_repo.get("repo_skill_md_count") != len(
        [r for r in repo_rows if r["kind"] == "skill"]
    ):
        return fail(
            "artifact repo_skill_md_count != live census",
            {
                "art": art_repo.get("repo_skill_md_count"),
                "live": len([r for r in repo_rows if r["kind"] == "skill"]),
            },
        )
    live_ids = [r["id"] for r in repo_rows]
    art_ids = [r.get("id") for r in (art_repo.get("repo_rows") or [])]
    if live_ids != art_ids:
        return fail("artifact repo skill ids != live classify", {"live": live_ids, "art": art_ids})

    rec1 = (doc.get("named_probe_records") or {}).get("probe1") or {}
    if rec1.get("lazy_classified") is not True:
        return fail("artifact did not record lazy_classified")
    if rec1.get("bare_always_on") is not True:
        return fail("artifact did not record bare_always_on")

    out = {
        "probe": "probe1-frontmatter",
        "unit_id": UNIT,
        "pass": True,
        "fixture_count": len(classified),
        "declared": {k: by_id[k]["declared_load_class"] for k in by_id},
        "repo_skill_ids": live_ids,
        "repo_skill_md_count": len([r for r in repo_rows if r["kind"] == "skill"]),
        "lazy_classified": True,
        "bare_always_on": True,
        "always_on_not_lazy": True,
        "artifact_matches_live": True,
    }
    (HERE / "probe1-frontmatter.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:AUD-0058-probe1 frontmatter load-class census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
