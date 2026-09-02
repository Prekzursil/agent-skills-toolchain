"""Contracted 29-artifact corpus for AUD-0074.

Live Prompt-One files (harness-restore) are searched first. If they are
absent or cannot carry a pre-correction version pin — so the known
2026-08-07 doc-13 control would be inert — a fixture pack of the 29
contracted names is written and used. Origin is recorded, never mixed
silently.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
CORPUS_DIR = FIX / "corpus"
DOC13 = "13-ARCHITECTURE-CANDIDATES.md"
CORRECTION_AT = "2026-08-07T00:00:00Z"

# Catalog-attested names where known; remaining numbered companions fill
# the contracted 29. Doc 13 is 13-ARCHITECTURE-CANDIDATES.md.
SPECS: list[tuple[str, str, list[tuple[str, str]], str]] = [
    (
        "00-CURRENT-STATE-INVENTORY.md",
        "2026-07-15T00:00:00Z",
        [],
        "Root inventory of the Prompt-One working tree. No upstream cites.",
    ),
    (
        "01-BLOCKER-REPRODUCTION.md",
        "2026-07-16T00:00:00Z",
        [("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z")],
        "Repro notes for the first blocker; derives from the inventory.",
    ),
    (
        "02-BLOCKER-ROOT-CAUSE.md",
        "2026-07-17T00:00:00Z",
        [
            ("01-BLOCKER-REPRODUCTION.md", "2026-07-16T00:00:00Z"),
            ("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z"),
        ],
        "Root-cause write-up downstream of the repro and the inventory.",
    ),
    (
        "03-PLUGIN-LIFECYCLE-MAP.md",
        "2026-07-18T00:00:00Z",
        [("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z")],
        "Plugin install/enable/disable lifecycle mapped from the inventory.",
    ),
    (
        "04-CAPABILITY-SURFACE.md",
        "2026-07-18T12:00:00Z",
        [("03-PLUGIN-LIFECYCLE-MAP.md", "2026-07-18T00:00:00Z")],
        "Capability surface derived from the lifecycle map.",
    ),
    (
        "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
        "2026-07-19T00:00:00Z",
        [("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z")],
        "Ecosystem index; shards live in an older tree (recorded, not silently merged).",
    ),
    (
        "06-PROGRAM-B-SCOPE-DOSSIER.md",
        "2026-07-19T12:00:00Z",
        [
            ("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z"),
            ("05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md", "2026-07-19T00:00:00Z"),
        ],
        "Program B scope dossier.",
    ),
    (
        "07-OPTION-UNIVERSE.md",
        "2026-07-20T00:00:00Z",
        [
            ("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z"),
            ("05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md", "2026-07-19T00:00:00Z"),
        ],
        "Option-universe family M cards. Distinct namespace from architecture MECH cards.",
    ),
    (
        "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "2026-07-21T00:00:00Z",
        [("07-OPTION-UNIVERSE.md", "2026-07-20T00:00:00Z")],
        "Workflow candidate registry keyed to option cards.",
    ),
    (
        "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
        "2026-07-22T00:00:00Z",
        [
            ("08-WORKFLOW-CANDIDATE-REGISTRY.json", "2026-07-21T00:00:00Z"),
            ("07-OPTION-UNIVERSE.md", "2026-07-20T00:00:00Z"),
        ],
        "Blueprint library derived from the candidate registry.",
    ),
    (
        "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
        "2026-07-23T00:00:00Z",
        [
            ("08-WORKFLOW-CANDIDATE-REGISTRY.json", "2026-07-21T00:00:00Z"),
            ("09-WORKFLOW-BLUEPRINT-LIBRARY.json", "2026-07-22T00:00:00Z"),
        ],
        "Merge/composition maps so a fused workflow can be decomposed.",
    ),
    (
        "11-COUNCIL-SPECIFICATION.md",
        "2026-07-24T00:00:00Z",
        [("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z")],
        "Council specification (protocols and presets are a separate artifact).",
    ),
    (
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "2026-07-24T12:00:00Z",
        [("11-COUNCIL-SPECIFICATION.md", "2026-07-24T00:00:00Z")],
        "Council protocol and preset library.",
    ),
    (
        DOC13,
        "2026-07-25T00:00:00Z",
        [
            ("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z"),
            ("03-PLUGIN-LIFECYCLE-MAP.md", "2026-07-18T00:00:00Z"),
            ("07-OPTION-UNIVERSE.md", "2026-07-20T00:00:00Z"),
        ],
        "Architecture candidates. Known correction 2026-08-07: mechanism cards re-prefixed MECH-NN; bare M-NN tokens removed.",
    ),
    (
        "14-NO-REGRESSION-CONTRACT.md",
        "2026-08-08T00:00:00Z",
        [(DOC13, "2026-08-08T00:00:00Z")],
        "No-regression contract citing the POST-correction doc 13 (MECH-NN).",
    ),
    (
        "15-IMPLEMENTATION-PRECONDITIONS.md",
        "2026-08-08T12:00:00Z",
        [
            (DOC13, "2026-08-08T00:00:00Z"),
            ("14-NO-REGRESSION-CONTRACT.md", "2026-08-08T00:00:00Z"),
        ],
        "Implementation preconditions citing the corrected architecture set.",
    ),
    (
        "16-VERIFICATION-PLAN.md",
        "2026-07-01T00:00:00Z",
        [("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z")],
        "Early verification plan. Created before the doc-13 correction but does NOT cite doc 13. A timestamp-only detector that ignored citations would over-flag this file; the citation+timestamp instrument must stay silent.",
    ),
    (
        "17-DECISION-LOG.md",
        "2026-08-04T00:00:00Z",
        [
            (DOC13, "2026-08-01T00:00:00Z"),
            ("07-OPTION-UNIVERSE.md", "2026-07-20T00:00:00Z"),
        ],
        "Decision log line 175 (known case): states the M-NN option-id collision as a present-tense open blocker, citing doc 13 as it stood before the 2026-08-07 MECH re-prefix.",
    ),
    (
        "18-OWNER-RULINGS.md",
        "2026-08-05T00:00:00Z",
        [
            ("17-DECISION-LOG.md", "2026-08-04T00:00:00Z"),
            (DOC13, "2026-08-01T00:00:00Z"),
        ],
        "Owner rulings repeating the pre-correction doc 13 citation via the decision log.",
    ),
    (
        "19-RISK-REGISTER.md",
        "2026-07-26T00:00:00Z",
        [("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z")],
        "Risk register derived from the inventory only.",
    ),
    (
        "20-INTERFACE-CONTRACT.md",
        "2026-07-27T00:00:00Z",
        [("10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json", "2026-07-23T00:00:00Z")],
        "Interface contract for merge maps.",
    ),
    (
        "21-DATA-MODEL.md",
        "2026-07-28T00:00:00Z",
        [("07-OPTION-UNIVERSE.md", "2026-07-20T00:00:00Z")],
        "Data model for option cards.",
    ),
    (
        "22-RUNTIME-TOPOLOGY.md",
        "2026-08-09T00:00:00Z",
        [(DOC13, "2026-08-08T00:00:00Z")],
        "Runtime topology citing POST-correction doc 13.",
    ),
    (
        "23-SECURITY-MODEL.md",
        "2026-07-29T00:00:00Z",
        [("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z")],
        "Security model from the inventory.",
    ),
    (
        "24-OBSERVABILITY.md",
        "2026-08-09T12:00:00Z",
        [("15-IMPLEMENTATION-PRECONDITIONS.md", "2026-08-08T12:00:00Z")],
        "Observability plan downstream of preconditions.",
    ),
    (
        "25-MIGRATION-PLAN.md",
        "2026-08-03T00:00:00Z",
        [(DOC13, "2026-08-02T00:00:00Z")],
        "Migration plan citing pre-correction architecture mechanism ids.",
    ),
    (
        "26-ACCEPTANCE-GATES.md",
        "2026-07-30T00:00:00Z",
        [("09-WORKFLOW-BLUEPRINT-LIBRARY.json", "2026-07-22T00:00:00Z")],
        "Acceptance gates for blueprints.",
    ),
    (
        "27-OPEN-QUESTIONS.md",
        "2026-07-31T00:00:00Z",
        [("00-CURRENT-STATE-INVENTORY.md", "2026-07-15T00:00:00Z")],
        "Open questions list.",
    ),
    (
        "33-INTEGRATION.md",
        "2026-08-06T00:00:00Z",
        [
            (DOC13, "2026-08-01T00:00:00Z"),
            ("17-DECISION-LOG.md", "2026-08-04T00:00:00Z"),
            ("10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json", "2026-07-23T00:00:00Z"),
        ],
        "Integration wrap-up citing pre-correction doc 13 and the decision log.",
    ),
]

CONTRACTED_IDS = [s[0] for s in SPECS]
LIVE_ROOTS = [
    HERE / "fixtures" / "harness-restore-20260806",
    HERE / "fixtures" / "corpus",
    Path.home() / ".claude" / "harness-restore-20260806",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    REPO,
    REPO / "command-center" / "sources",
]


def corrections() -> list[dict[str, Any]]:
    return [
        {
            "id": "doc13-mech-reprefix-2026-08-07",
            "source": DOC13,
            "corrected_at": CORRECTION_AT,
            "description": (
                "MECH re-prefix of architecture mechanism cards "
                "(bare M-NN tokens removed from doc 13 on 2026-08-07)"
            ),
        }
    ]


def _body(name: str, created: str, cites: list[tuple[str, str]], prose: str) -> str:
    cite_lines = "\n".join(f"[cite:{t} version={v}]" for t, v in cites) or "(no outbound cites)"
    if name.endswith(".json"):
        return (
            json.dumps(
                {
                    "artifact": name,
                    "created_at": created,
                    "prose": prose,
                    "lineage": cite_lines,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
    extra = ""
    if name == DOC13:
        extra = (
            f"\ncorrected_at: {CORRECTION_AT}\n"
            "correction: mechanism cards re-prefixed MECH-NN; this file is the "
            "corrected source. Downstream cites bound to a pre-2026-08-07 version "
            "are stale.\n"
        )
    if name == "17-DECISION-LOG.md":
        extra = (
            "\nLine 175 (known case): the M-NN option-id collision remains an "
            "open present-tense blocker (Queued as P2-09), pointing at "
            f"{DOC13} as of 2026-08-01, before the MECH re-prefix.\n"
        )
    return (
        f"# {name}\n\n"
        f"created_at: {created}\n\n"
        f"{prose}\n"
        f"{extra}\n"
        f"## lineage\n{cite_lines}\n"
    )


def write_fixtures() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for name, created, cites, prose in SPECS:
        (CORPUS_DIR / name).write_text(
            _body(name, created, cites, prose), encoding="utf-8", newline="\n"
        )
    (FIX / "corrections.json").write_text(
        json.dumps({"corrections": corrections()}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _scan_live() -> tuple[Path | None, int]:
    best: Path | None = None
    best_n = 0
    for root in LIVE_ROOTS:
        if not root.is_dir():
            continue
        n = sum(1 for name in CONTRACTED_IDS if (root / name).is_file())
        if n > best_n:
            best, best_n = root, n
    return best, best_n


def load() -> dict[str, Any]:
    write_fixtures()
    live_root, live_n = _scan_live()
    # Live files on this worktree almost never carry a pre-correction version
    # pin; using mtime of a restored tree would make the known doc-13 control
    # inert. Fixtures are used unless a live tree has nearly all 29 files AND
    # at least one file still has a [cite:] pin to doc 13 with version < correction.
    use_live = False
    why = (
        f"live hits {live_n}/29"
        + (f" under {live_root}" if live_root else " (no live root)")
        + "; fixture pack used so the 2026-08-07 doc-13 control is measurable"
    )
    if live_root is not None and live_n >= 20:
        pinned = 0
        for name in CONTRACTED_IDS:
            p = live_root / name
            if not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if "[cite:" + DOC13 in text and "version=2026-08-0" in text:
                pinned += 1
        if pinned:
            use_live = True
            why = f"live tree {live_root} hits={live_n} cite-pins-to-doc13={pinned}"

    records: list[dict[str, Any]] = []
    origin = "live" if use_live else "fixture"
    root = live_root if use_live else CORPUS_DIR
    for name, created, _cites, _prose in SPECS:
        path = root / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            rec_origin = origin
        else:
            path = CORPUS_DIR / name
            text = path.read_text(encoding="utf-8")
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            rec_origin = "fixture-fill"
        records.append(
            {
                "id": name,
                "path": str(path.relative_to(REPO))
                if str(path).startswith(str(REPO))
                else str(path),
                "text": text,
                "created_at": created,
                "mtime": mtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "origin": rec_origin,
                "bytes": len(text.encode("utf-8")),
            }
        )
    return {
        "origin": origin,
        "why": why,
        "live_root": str(live_root) if live_root else None,
        "live_hits": live_n,
        "records": records,
        "corrections": corrections(),
        "contracted": list(CONTRACTED_IDS),
    }
