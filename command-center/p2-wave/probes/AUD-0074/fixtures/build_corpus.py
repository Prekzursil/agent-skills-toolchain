#!/usr/bin/env python3
"""Build the AUD-0074 fixture corpus from the AUD-0067 29-artifact contract.

Honest scope: live Windows Prompt-One trees are NOT mounted on this single-checkout
Linux substrate (AUD-0067 measured current_repo_root_fresh=0). This rebuilds a
citation-bearing fixture corpus so Probe 1/2 and the doc-13 control can run
without inventing live-tree SUCCESS.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus"
VERSIONS = HERE / "versions"
AUD0067 = (
    Path(__file__).resolve().parents[4]
    / "audit"
    / "AUD-0067-prompt-one-artifact-census.json"
)

# Known F-B-02 / doc-13 MECH re-prefix correction (catalog inputs).
DOC13 = "13-ARCHITECTURE-CANDIDATES.md"
CORRECTION_AT = "2026-08-07T12:00:00+00:00"
CORRECTION_EPOCH = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc).timestamp()

# Explicit citation edges planted among contract basenames (citer -> cited).
# Includes the known stale-downstream case: 17-DECISION-LOG cites doc-13 while
# still carrying the pre-correction F-B-02 present-tense collision wording.
PLANTED_EDGES: list[tuple[str, str]] = [
    ("01-BLOCKER-REPRODUCTION.md", "00-CURRENT-STATE-INVENTORY.md"),
    ("02-BLOCKER-ROOT-CAUSE.md", "01-BLOCKER-REPRODUCTION.md"),
    ("03-PLUGIN-LIFECYCLE-MAP.md", "00-CURRENT-STATE-INVENTORY.md"),
    ("05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md", "04-MARKETPLACE-CURRENT-STATE.md"),
    ("06-EXISTING-WORK-ADOPT-EXTEND-RETIRE.md", "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md"),
    ("07-OPTION-UNIVERSE.md", "06-EXISTING-WORK-ADOPT-EXTEND-RETIRE.md"),
    ("08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md", "07-OPTION-UNIVERSE.md"),
    ("09-WORKFLOW-BLUEPRINT-LIBRARY.md", "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md"),
    ("10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md", "09-WORKFLOW-BLUEPRINT-LIBRARY.md"),
    ("11-COUNCIL-SPECIFICATION.md", "10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md"),
    ("12-COUNCIL-PROTOCOLS-AND-PRESETS.md", "11-COUNCIL-SPECIFICATION.md"),
    ("13-ARCHITECTURE-CANDIDATES.md", "07-OPTION-UNIVERSE.md"),
    ("13-ARCHITECTURE-CANDIDATES.md", "11-COUNCIL-SPECIFICATION.md"),
    ("14-NO-REGRESSION-CONTRACT.md", "13-ARCHITECTURE-CANDIDATES.md"),
    ("15-IMPLEMENTATION-PRECONDITIONS.md", "13-ARCHITECTURE-CANDIDATES.md"),
    ("15-IMPLEMENTATION-PRECONDITIONS.md", "14-NO-REGRESSION-CONTRACT.md"),
    ("16-GRILL-QUEUE.md", "15-IMPLEMENTATION-PRECONDITIONS.md"),
    ("17-DECISION-LOG.md", "13-ARCHITECTURE-CANDIDATES.md"),
    ("17-DECISION-LOG.md", "16-GRILL-QUEUE.md"),
    ("18-OPEN-UNKNOWNS-AND-PROBES.md", "17-DECISION-LOG.md"),
    ("18-OPEN-UNKNOWNS-AND-PROBES.md", "13-ARCHITECTURE-CANDIDATES.md"),
]


def contract_basenames() -> list[str]:
    doc = json.loads(AUD0067.read_text(encoding="utf-8"))
    assert doc.get("state") == "SUCCESS", "AUD-0067 must be SUCCESS on disk"
    inv = doc["extensions"]["inventory"]
    out: list[str] = []
    for row in inv:
        name = row["artifact"]
        if name.startswith("("):
            # item29 diagrams directory sentinel from AUD-0067
            name = "19-DIAGRAMS"
        out.append(name)
    assert len(out) == 29, len(out)
    return out


def write_file(path: Path, text: str, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    os.utime(path, (mtime, mtime))


def body_for(name: str, cites: list[str], *, stale_doc13: bool = False) -> str:
    lines = [
        f"# {name} (AUD-0074 fixture reconstruction)",
        "",
        f"as_of_note: fixture-reconstruction; not a live Prompt-One Windows tree byte.",
        "",
    ]
    if name == DOC13:
        # Live corpus copy uses POST-correction MECH namespace (corrected 2026-08-07).
        post = (VERSIONS / f"{DOC13}.post-correction").read_text(encoding="utf-8")
        lines.append("<!-- live corpus holds post-correction MECH-NN form -->")
        lines.append(post)
        lines.append("")
    elif name == "17-DECISION-LOG.md" and stale_doc13:
        stale = (HERE / "control" / "17-DECISION-LOG.stale.md").read_text(
            encoding="utf-8"
        )
        lines.append(stale)
        lines.append("")
        lines.append(
            "Still depends on pre-correction doc-13 M-NN mechanism namespace "
            f"(see {DOC13})."
        )
        lines.append("")
    else:
        lines.append("Fixture stub for citation-edge measurement.")
        lines.append("")

    if cites:
        lines.append("## Citations")
        for c in cites:
            lines.append(f"- depends on `{c}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    names = contract_basenames()
    cite_map: dict[str, list[str]] = {n: [] for n in names}
    for src, dst in PLANTED_EDGES:
        if src in cite_map and dst in names:
            cite_map[src].append(dst)

    # Timestamps: most artifacts after correction; plant known-stale 17-DECISION-LOG
    # and 15-IMPLEMENTATION-PRECONDITIONS BEFORE the correction so Probe 2 flags them.
    after = CORRECTION_EPOCH + 86400 * 3  # 2026-08-10
    before = CORRECTION_EPOCH - 86400 * 2  # 2026-08-05

    CORPUS.mkdir(parents=True, exist_ok=True)
    for name in names:
        path = CORPUS / name
        if name == "19-DIAGRAMS":
            path.mkdir(parents=True, exist_ok=True)
            marker = path / "README.md"
            write_file(
                marker,
                "# diagrams fixture dir\n\nSee `13-ARCHITECTURE-CANDIDATES.md`.\n",
                after,
            )
            os.utime(path, (after, after))
            continue

        stale = name == "17-DECISION-LOG.md"
        mtime = before if name in {
            "17-DECISION-LOG.md",
            "15-IMPLEMENTATION-PRECONDITIONS.md",
        } else after
        # Doc-13 itself is the corrected live file → mtime after correction.
        if name == DOC13:
            mtime = CORRECTION_EPOCH + 3600
        text = body_for(name, cite_map.get(name, []), stale_doc13=stale)
        write_file(path, text, mtime)

    meta = {
        "unit": "AUD-0074",
        "kind": "fixture-reconstruction",
        "contract_items": 29,
        "aud0067_state": "SUCCESS",
        "doc13_correction_at": CORRECTION_AT,
        "planted_edges": [{"from": a, "to": b} for a, b in PLANTED_EDGES],
        "stale_planted_citers": [
            "17-DECISION-LOG.md",
            "15-IMPLEMENTATION-PRECONDITIONS.md",
        ],
        "scope_note": (
            "Single-checkout Linux cursor-cloud: live Prompt-One Windows roots "
            "unmounted; corpus is fixture-reconstruction keyed to AUD-0067 inventory."
        ),
    }
    (HERE / "corpus-meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(f"BUILT corpus items={len(names)} edges_planted={len(PLANTED_EDGES)}")
    print(f"DOC13_CORRECTION_AT={CORRECTION_AT}")
    print("SUCCESS:AUD-0074-build-corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
