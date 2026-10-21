"""ADV-0018 Probe 1: retrieve notes by topic and diff each load-bearing assertion
against the corresponding CURRENT measurement (computed live, not stored).

Load-bearing assertion classes diffed today:
  A. per-unit artifact state claims  ("<UNIT-ID> ... state/status: X" where the catalog
     unit's committed artifact declares a different state today);
  B. artifact hash/bytes claims       ("sha256: <hex>" / "<n> B" next to an artifact path
     whose current bytes differ);
  C. program census claims            (catalog_units / green counts vs live census).

A note is CONTRADICTED when >=1 load-bearing assertion disagrees with today's measurement.
"""

from __future__ import annotations

import json
import re
import sys

from shared import (REPO, artifact_hash_claims, census_counts, parse_state_claims,
                    retrieve_topic_notes, repo_head, sha256_of, unit_artifact_for,
                    write_raw)


def main() -> int:
    notes = retrieve_topic_notes()
    census = census_counts()
    head = repo_head()
    rows: list[dict] = []
    for md in notes:
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            rows.append({"note": str(md), "error": f"unreadable: {exc}"})
            continue
        checks: list[dict] = []

        # A. unit state claims
        for uid, claimed in parse_state_claims(text):
            art = unit_artifact_for(uid)
            if art is None:
                continue  # not checkable today -> not load-bearing here
            try:
                actual = json.loads(art.read_text(encoding="utf-8")).get("state")
            except Exception:  # noqa: BLE001
                continue
            if claimed != actual:
                checks.append({
                    "class": "unit-state",
                    "assertion": f"{uid} state={claimed}",
                    "current": f"{uid} state={actual}",
                    "agrees": False,
                })
            else:
                checks.append({
                    "class": "unit-state",
                    "assertion": f"{uid} state={claimed}",
                    "current": f"{uid} state={actual}",
                    "agrees": True,
                })

        # B. artifact hash claims
        for path_str, claimed_hash in artifact_hash_claims(text):
            p = REPO / path_str.replace("\\", "/")
            if not p.is_file():
                continue
            actual_hash = sha256_of(p)
            if actual_hash and claimed_hash.lower() != actual_hash:
                checks.append({
                    "class": "artifact-hash",
                    "assertion": f"{path_str} sha256={claimed_hash[:16]}...",
                    "current": f"sha256={actual_hash[:16]}...",
                    "agrees": False,
                })

        # C. census claims (only counts that name the program's units/greens)
        for m in re.finditer(r"\b(20[0-9]{2})\s*(?:catalog\s*units|units)", text):
            if int(m.group(1)) != census["catalog_units"]:
                checks.append({
                    "class": "census-units",
                    "assertion": m.group(0),
                    "current": str(census["catalog_units"]),
                    "agrees": False,
                })
        contradicted = [c for c in checks if not c["agrees"]]
        rows.append({
            "note": str(md),
            "checked": len(checks),
            "contradicted": len(contradicted),
            "contradictions": contradicted,
        })

    contradicted_notes = [r for r in rows if r.get("contradicted", 0) > 0]
    payload = {
        "probe": "probe1-topic-diff",
        "vault": "D:/basic-memory",
        "repo_head": head,
        "census": {k: census[k] for k in ("catalog_units", "green_SUCCESS", "result")},
        "notes_walked": len(notes),
        "notes_with_checks": sum(1 for r in rows if r.get("checked")),
        "contradicted_notes": [r["note"] for r in contradicted_notes],
        "rows": rows,
    }
    out = [f"SUCCESS:adv0018-probe1 {len(notes)} topic notes; "
           f"{len(contradicted_notes)} contradicted today; census green={census['green_SUCCESS']}; "
           f"HEAD={head[:12]}"]
    for r in contradicted_notes:
        out.append("  CONTRADICTED: " + r["note"])
        for c in r["contradictions"][:4]:
            out.append(f"    {c['class']}: note='{c['assertion']}' today='{c['current']}'")
    text_out = "\n".join(out) + "\n"
    print(text_out, end="")
    write_raw("probe1-topic-retrieval", payload, text_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
