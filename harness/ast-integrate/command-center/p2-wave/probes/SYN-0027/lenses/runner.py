"""Apply SYN-0014, SYN-0015, SYN-0017, SYN-0022 to subjects, unmodified."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import identity as lens_identity  # noqa: E402
import syn_0014  # noqa: E402
import syn_0015  # noqa: E402
import syn_0017  # noqa: E402
import syn_0022  # noqa: E402
from role import substring_as_use  # noqa: E402

REPO = HERE.parents[4]
QUOTE_PHRASE = "every unit passes"
PLANTED_BAND = "almost certain"

FIXTURE_QUOTE = (
    "command-center/p2-wave/probes/SYN-0027/fixtures/lens-quoting-every-unit-passes.md"
)
FIXTURE_PLANT = (
    "command-center/p2-wave/probes/SYN-0027/fixtures/planted-unanchored-certainty.md"
)
FIXTURE_GOOD = (
    "command-center/p2-wave/probes/SYN-0027/fixtures/good-anchored-certainty.md"
)
FIXTURE_OVERCLAIM = (
    "command-center/p2-wave/probes/SYN-0027/fixtures/planted-overclaim.md"
)
FIXTURE_SCOPED = (
    "command-center/p2-wave/probes/SYN-0027/fixtures/scoped-quantifier.md"
)
FIXTURE_DEDUP = (
    "command-center/p2-wave/probes/SYN-0027/fixtures/mechanism-pairs.json"
)
FIXTURE_PREMISE = (
    "command-center/p2-wave/probes/SYN-0027/fixtures/premise-records.json"
)
FIXTURE_META = (
    "command-center/p2-wave/probes/SYN-0027/fixtures/meta-review-standin.json"
)

LENSES = (
    ("SYN-0014", syn_0014.scan_path),
    ("SYN-0015", syn_0015.scan_path),
    ("SYN-0017", syn_0017.scan_path),
    ("SYN-0022", syn_0022.scan_path),
)


def catalog_meta_review_paths() -> list[dict[str, Any]]:
    catalog = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    wanted = {f"SYN-{i:04d}" for i in range(14, 27)}
    rows = []
    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = unit.get("id")
        if uid not in wanted:
            continue
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        fp = REPO / rel if rel else None
        present = bool(fp and fp.is_file() and fp.stat().st_size > 0)
        rows.append(
            {
                "unit_id": uid,
                "path": rel,
                "present": present,
                "bytes": fp.stat().st_size if present else 0,
            }
        )
    rows.sort(key=lambda r: str(r["unit_id"]))
    return rows


def apply_lenses(paths: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        rel = path
        try:
            rel = path.relative_to(REPO)
        except ValueError:
            pass
        for _lid, scan in LENSES:
            for row in scan(path):
                row["source_path"] = rel.as_posix() if hasattr(rel, "as_posix") else str(rel)
                findings.append(row)
    return findings


def use_vs_mention_control() -> dict[str, Any]:
    path = REPO / FIXTURE_QUOTE
    text = path.read_text(encoding="utf-8")
    idx = text.find(QUOTE_PHRASE)
    from role import classify_text_span

    role = (
        classify_text_span(text, idx, idx + len(QUOTE_PHRASE))
        if idx >= 0
        else "ABSENT"
    )
    mutant = substring_as_use(text, QUOTE_PHRASE)
    findings = syn_0015.scan_path(path)
    use_defects = [
        f
        for f in findings
        if f.get("counted_as_defect")
        and QUOTE_PHRASE in (f.get("sentence") or f.get("span") or "").lower()
    ]
    # Also any USE defect whose span is the phrase itself.
    use_defects += [
        f
        for f in findings
        if f.get("counted_as_defect")
        and str(f.get("span") or "").lower() in {"every", "all"}
        and QUOTE_PHRASE in (f.get("sentence") or "").lower()
    ]
    # Dedup by id
    seen = set()
    uniq = []
    for f in use_defects:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        uniq.append(f)
    passed = role == "MENTION" and mutant == "USE" and not uniq
    return {
        "passed": passed,
        "quoted_phrase": QUOTE_PHRASE,
        "self_flagged_as_use_defect": bool(uniq),
        "role_on_quoted_span": role,
        "substring_matcher_role": mutant,
        "both_states_discriminate": role == "MENTION" and mutant == "USE",
        "finding_ids_if_self_flagged": [f["id"] for f in uniq],
        "fixture": FIXTURE_QUOTE,
    }


def known_present_control() -> dict[str, Any]:
    plant = REPO / FIXTURE_PLANT
    good = REPO / FIXTURE_GOOD
    bad = [f for f in syn_0014.scan_path(plant) if f.get("counted_as_defect")]
    good_hits = [f for f in syn_0014.scan_path(good) if f.get("counted_as_defect")]
    fired = any(
        "almost" in str(f.get("span") or "").lower()
        or f.get("band_or_hedge") == "almost-certain"
        for f in bad
    )
    return {
        "fired": fired,
        "silent_on_good": not good_hits,
        "plant": "unanchored USE-voice 'almost certain' in a lens-output stand-in",
        "plant_fixture": FIXTURE_PLANT,
        "good_fixture": FIXTURE_GOOD,
        "bad_finding_ids": [f["id"] for f in bad],
        "good_finding_ids": [f["id"] for f in good_hits],
        "both_states_discriminate": fired and not good_hits,
    }


def overclaim_plant_control() -> dict[str, Any]:
    path = REPO / FIXTURE_OVERCLAIM
    scoped = REPO / FIXTURE_SCOPED
    bad = [f for f in syn_0015.scan_path(path) if f.get("counted_as_defect")]
    good = [f for f in syn_0015.scan_path(scoped) if f.get("counted_as_defect")]
    fired = any("no unit" in str(f.get("span") or "").lower() for f in bad)
    return {
        "fired": fired,
        "silent_on_scoped": not good,
        "plant_fixture": FIXTURE_OVERCLAIM,
        "scoped_fixture": FIXTURE_SCOPED,
        "bad_ids": [f["id"] for f in bad],
        "good_ids": [f["id"] for f in good],
    }


def artifact_field(doc: dict[str, Any], key: str, default: Any = None) -> Any:
    """Read a SYN-0027 field from the receipt, then extensions, then report.

    receipt_core sets additionalProperties:false, so the catalog shim will
    reject top-level extras. Probe-facing payload lives under report/extensions.
    """
    if not isinstance(doc, dict):
        return default
    for root in (doc, doc.get("extensions"), doc.get("report")):
        if isinstance(root, dict) and key in root:
            val = root[key]
            if val is not None:
                return val
    return default


def labels_ok(findings: list[dict[str, Any]]) -> tuple[bool, bool]:
    labeled = all(f.get("use_or_mention") in {"USE", "MENTION"} for f in findings)
    mention_as_defect = any(
        f.get("use_or_mention") == "MENTION" and f.get("counted_as_defect")
        for f in findings
    )
    return labeled, not mention_as_defect


def run() -> dict[str, Any]:
    ident = lens_identity.check()
    uvm = use_vs_mention_control()
    kpc = known_present_control()
    ovc = overclaim_plant_control()
    dedup = syn_0017.planted_control(REPO / FIXTURE_DEDUP)
    live = catalog_meta_review_paths()
    fixture_paths = [
        REPO / FIXTURE_QUOTE,
        REPO / FIXTURE_PLANT,
        REPO / FIXTURE_GOOD,
        REPO / FIXTURE_OVERCLAIM,
        REPO / FIXTURE_SCOPED,
        REPO / FIXTURE_DEDUP,
        REPO / FIXTURE_PREMISE,
        REPO / FIXTURE_META,
    ]
    live_paths = [REPO / r["path"] for r in live if r["present"]]
    findings = apply_lenses(fixture_paths + live_paths)
    labeled, mention_ok = labels_ok(findings)
    defects = [f for f in findings if f.get("counted_as_defect")]
    mentions = [f for f in findings if f.get("use_or_mention") == "MENTION"]
    return {
        "lens_identity": ident,
        "use_vs_mention_control": uvm,
        "known_present_control": kpc,
        "overclaim_plant_control": ovc,
        "dedup_planted_control": dedup,
        "production_corpus": live,
        "production_present": sum(1 for r in live if r["present"]),
        "production_absent": sum(1 for r in live if not r["present"]),
        "findings": findings,
        "defect_count": len(defects),
        "mention_count": len(mentions),
        "finding_count": len(findings),
        "every_finding_labeled": labeled,
        "mention_never_counted_as_defect": mention_ok,
        "fixture_paths": [
            p.relative_to(REPO).as_posix() for p in fixture_paths if p.is_file()
        ],
    }
