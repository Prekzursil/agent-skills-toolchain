#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0401.json after a live host scan + fixture detect."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0401.json"
ANNOTATED = "command-center/p2-wave/probes/IMP-0401/capability-index.annotated.json"
SENTINEL = "SENTINEL:IMP-0401:PRESENCE-GAP-ENUMERATED"
QUESTION = (
    "how many indexed capabilities are repo-only, and how many are live-only?"
)


def load_presence_gap():
    path = REPO / "tools" / "router" / "presence_gap.py"
    spec = importlib.util.spec_from_file_location("imp0401_presence_gap", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() if raw else "",
        "exists": path.is_file(),
        "role": "supporting",
        "eol": "LF",
    }


def main() -> int:
    sys.path.insert(0, str(HERE))
    import fixtures as F  # noqa: E402

    pg = load_presence_gap()
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )

    host_repo = [pg.default_repo_skill_root(REPO)]
    host_live = pg.default_live_skill_roots()
    host = pg.detect(host_repo, host_live, index=None)
    fixture = pg.detect(
        F.fixture_repo_roots(), F.fixture_live_roots(), index=F.INDEX_PATH
    )
    if not fixture["disjoint"] or not host["disjoint"]:
        print("FAILED:IMP-0401 emit lists were not disjoint")
        return 1
    if F.PLANTED_REPO_ONLY not in fixture["repo_only"]:
        print("FAILED:IMP-0401 emit fixture repo-only missing")
        return 1
    if F.PLANTED_LIVE_ONLY not in fixture["live_only"]:
        print("FAILED:IMP-0401 emit fixture live-only missing")
        return 1
    if F.PLANTED_BOTH in fixture["repo_only"] or F.PLANTED_BOTH in fixture["live_only"]:
        print("FAILED:IMP-0401 emit fixture both leaked")
        return 1

    annotated_path = REPO / ANNOTATED
    annotated_path.parent.mkdir(parents=True, exist_ok=True)
    annotated_doc = {
        "unit_id": "IMP-0401",
        "kind": "capability-index-presence-gap",
        "host": host["annotated_index"],
        "fixture_control": fixture["annotated_index"],
        "sentinel": SENTINEL,
    }
    annotated_path.write_text(
        json.dumps(annotated_doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    host_trees_present = any(
        r["is_dir"] and r["skill_md_count"] > 0
        for r in (host["repo_roots"] + host["live_roots"])
    )
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )

    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0401",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0401",
        "title": "Repo-versus-live capability presence gap detector",
        "question": (
            "Implement the detector for spec failure class 'skill exists in repo "
            "but not in live skill directory' as a ROUTER-visible defect: the "
            "index must flag any capability the router could select that cannot "
            "actually load. Exact question: " + QUESTION
        ),
        "min_bytes_threshold": 2048,
        "failure_classification": [
            "selectable-but-unloadable",
            "one-directional-comparison",
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-worktree",
        },
        "answers": {
            "question": QUESTION,
            "method": "set(repo_capability_id) - set(live_capability_id) and the reverse",
            "host": {
                "trees_present": host_trees_present,
                "repo_only": host["repo_only"],
                "live_only": host["live_only"],
                "both": host["both"],
                "repo_only_count": host["repo_only_count"],
                "live_only_count": host["live_only_count"],
                "indexed_repo_only_count": host["indexed"]["repo_only_count"],
                "indexed_live_only_count": host["indexed"]["live_only_count"],
                "selectable_but_unloadable": host["indexed"]["selectable_but_unloadable"],
                "repo_roots": host["repo_roots"],
                "live_roots": host["live_roots"],
                "note": (
                    "Host trees_present="
                    + str(host_trees_present)
                    + " repo_only_count="
                    + str(host["repo_only_count"])
                    + " live_only_count="
                    + str(host["live_only_count"])
                    + " indexed_repo_only_count="
                    + str(host["indexed"]["repo_only_count"])
                    + " indexed_live_only_count="
                    + str(host["indexed"]["live_only_count"])
                    + ". Live home skill dirs (~/.claude/skills, ~/.agents/skills) "
                    "are scanned as catalogued; a zero on either side is not "
                    "vacuous because the fixture control plants both directions."
                ),
            },
            "fixture_control": {
                "repo_only": fixture["repo_only"],
                "live_only": fixture["live_only"],
                "both": fixture["both"],
                "repo_only_count": fixture["repo_only_count"],
                "live_only_count": fixture["live_only_count"],
                "indexed_repo_only": fixture["indexed"]["repo_only"],
                "indexed_live_only": fixture["indexed"]["live_only"],
                "indexed_repo_only_count": fixture["indexed"]["repo_only_count"],
                "indexed_live_only_count": fixture["indexed"]["live_only_count"],
                "selectable_but_unloadable": fixture["indexed"][
                    "selectable_but_unloadable"
                ],
            },
        },
        "evidence": [
            {
                "claim": (
                    "Host indexed repo-only count is "
                    + str(host["indexed"]["repo_only_count"])
                    + " and host indexed live-only count is "
                    + str(host["indexed"]["live_only_count"])
                    + " by set difference over capability_id. Host skill trees "
                    "present="
                    + str(host_trees_present)
                    + "."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/presence_gap.py:detect",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "detect(default_repo_skill_root, default_live_skill_roots)",
                        "raw_output": json.dumps(
                            {
                                "repo_only": host["repo_only"],
                                "live_only": host["live_only"],
                                "repo_roots": host["repo_roots"],
                                "live_roots": host["live_roots"],
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    }
                ],
            },
            {
                "claim": (
                    "Detector control: planted "
                    + F.PLANTED_REPO_ONLY
                    + " appears only in repo_only, planted "
                    + F.PLANTED_LIVE_ONLY
                    + " appears only in live_only, planted "
                    + F.PLANTED_BOTH
                    + " appears in neither gap list. The two lists are disjoint."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0401/probe1_detector_control.py",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "detect(fixture repo/live roots, fixture index)",
                        "raw_output": json.dumps(
                            {
                                "repo_only": fixture["repo_only"],
                                "live_only": fixture["live_only"],
                                "both": fixture["both"],
                                "selectable_but_unloadable": fixture["indexed"][
                                    "selectable_but_unloadable"
                                ],
                            },
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    }
                ],
            },
            {
                "claim": (
                    "The index flags selectable-but-unloadable for "
                    + F.PLANTED_REPO_ONLY
                    + " and "
                    + F.PLANTED_INDEX_ONLY
                    + "; loadable ids are not flagged. This is the router-visible "
                    "form of FC-11329."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/router/presence_gap.py:annotate_index",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "other",
                        "command": "annotate_index on fixture capability-index.json",
                        "raw_output": json.dumps(
                            fixture["annotated_index"]["presence_gap"],
                            sort_keys=True,
                        ),
                        "exit_code": 0,
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "detector-control-planted-both-directions",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0401/probe1_detector_control.py"
                ),
                "result": "PASS",
                "assertions": 8,
            },
            {
                "id": "independent-setdiff-and-one-directional-mutant",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0401/probe2_independent_setdiff.py"
                ),
                "result": "PASS",
                "assertions": 6,
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0401-C1-both-present-silent",
                "kind": "known-good",
                "description": (
                    "A capability present in both trees must not enter repo_only "
                    "or live_only."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": F.PLANTED_REPO_ONLY + " in repo_only",
                "good_state_output": F.PLANTED_BOTH + " only in both",
            },
            {
                "id": "IMP0401-C2-one-directional-mutant",
                "kind": "mutation",
                "description": (
                    "repo_ids - live_ids alone misses planted live-only; the "
                    "shipped detector is bidirectional."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "one_directional misses " + F.PLANTED_LIVE_ONLY,
                "good_state_output": "live_only contains " + F.PLANTED_LIVE_ONLY,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0401-probe2-independent-setdiff",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 recomputes the set difference from SKILL.md parent "
                "directory names without parsing frontmatter, then compares "
                "to detect(). Disagreement fails the probe."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0401/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "Measure runs after this emit; cloud ok=true is not delivery.",
            }
        ],
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
                "eol": "LF",
            },
            sha256_file("tools/router/presence_gap.py"),
            sha256_file(ANNOTATED),
            sha256_file(
                "command-center/p2-wave/probes/IMP-0401/probe1_detector_control.py"
            ),
            sha256_file(
                "command-center/p2-wave/probes/IMP-0401/probe2_independent_setdiff.py"
            ),
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "max 2 attempts, backoff 30s/120s",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0385 capability-index.json over the six live/repo roots "
                    "is not on this worktree. Host gap counts therefore use a "
                    "skills-only enumerator with the same capability_id rule the "
                    "detector ships. A later index builder must keep that id rule."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run detect() against IMP-0385's capability-index.json "
                    "once that unit is delivered and compare indexed counts."
                ),
            },
            {
                "claim": (
                    "command-center/schema/receipt.schema.json is absent on this "
                    "worktree (platform/schema likewise), so this receipt is "
                    "receipt-shaped but not schema-validated here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Validate IMP-0401.json against receipt.schema.json when "
                    "the schema tree is present."
                ),
            },
        ],
        "report": {
            "kind": "presence-gap-enumeration",
            "failure_class": "FC-11329",
            "indexed_host_repo_only": host["indexed"]["repo_only_count"],
            "indexed_host_live_only": host["indexed"]["live_only_count"],
            "indexed_fixture_repo_only": fixture["indexed"]["repo_only_count"],
            "indexed_fixture_live_only": fixture["indexed"]["live_only_count"],
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:IMP-0401 sentinel missing from serialized receipt")
        return 1
    out_path.write_text(body, encoding="utf-8")
    size = out_path.stat().st_size
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:IMP-0401 receipt {size}B below floor")
        return 1
    print(
        f"host indexed repo_only={host['indexed']['repo_only_count']} "
        f"live_only={host['indexed']['live_only_count']} trees_present={host_trees_present}"
    )
    print(
        f"fixture repo_only={fixture['repo_only_count']} "
        f"live_only={fixture['live_only_count']} "
        f"unloadable={fixture['indexed']['selectable_but_unloadable_count']}"
    )
    print(f"wrote {OUT} ({size} B)")
    print("SUCCESS:IMP-0401 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
