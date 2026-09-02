"""Known-good / known-broken / mutation fixtures for Phase 14 synthesis gates."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Callable

from constants import BUCKET_UNITS, CALIBRATION_ID, FIXTURES_REL, REPO

Json = dict[str, Any]
Mutator = Callable[[Json], Json]


def _syn_0002_good() -> Json:
    return {
        "nodes": [
            {
                "id": "CAUSE-orphan-class",
                "kind": "CAUSE",
                "evidence": ["AUD-0037"],
                "children": ["SYM-orphan"],
            },
            {
                "id": "SYM-orphan",
                "kind": "SYMPTOM",
                "evidence": ["claim-1"],
                "children": [],
            },
        ],
        "edges": [{"src": "CAUSE-orphan-class", "dst": "SYM-orphan"}],
        "claims": [{"id": "claim-1", "attached_to": "SYM-orphan"}],
    }


def _syn_0002_broken() -> Json:
    doc = _syn_0002_good()
    doc["claims"].append({"id": "claim-orphan", "attached_to": None})
    doc["nodes"].append(
        {"id": "CAUSE-empty", "kind": "CAUSE", "evidence": [], "children": []}
    )
    doc["edges"].append({"src": "SYM-orphan", "dst": "CAUSE-orphan-class"})
    doc["edges"].append({"src": "CAUSE-orphan-class", "dst": "NOWHERE"})
    return doc


def _syn_0002_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    doc["claims"].append({"id": "claim-reverted-orphan", "attached_to": ""})
    return doc


def _syn_0013_good() -> Json:
    return {
        "EVIDENCE": [
            "command-center/CLAIM-REGISTRY.json:12",
            "command-center/RISK-REGISTER.md:40",
            "tools/command-center/digest.py:88",
            "rules/common/fan-out-contract.md:14",
        ],
        "quoted": ["https://example.invalid/mentioned-only"],
        "body": (
            "Synthesis cites four live anchors. A document ABOUT missing URLs "
            "may mention https://example.invalid/mentioned-only inside quotes."
        ),
        "retention_by_class": {
            "UNVERIFIED": {"source": 4, "synthesis": 4},
            "file:line": {"source": 12, "synthesis": 4},
            "URL": {"source": 3, "synthesis": 0},
        },
    }


def _syn_0013_broken() -> Json:
    return {
        "EVIDENCE": [],
        "quoted": ["command-center/CLAIM-REGISTRY.json:12"],
        "body": (
            'The digest mentioned "command-center/CLAIM-REGISTRY.json:12" '
            "but carries no EVIDENCE block."
        ),
        "retention_by_class": {"all": {"source": 19, "synthesis": 1}},
    }


def _syn_0013_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    doc["EVIDENCE"] = []
    return doc


def _syn_0016_good() -> Json:
    return {
        "dissents": [
            {
                "id": "dsnt-hatch",
                "text": "the hatch path leaks owner credentials into the bundle",
            },
            {
                "id": "dsnt-condorcet",
                "text": "ranked choice on this ballot set elects a Condorcet loser",
            },
        ],
        "synthesis_text": (
            "Owner credentials leak from the hatch path into the bundle. "
            "Ranked-choice on this ballot set elects a Condorcet loser."
        ),
        "disposals": {},
    }


def _syn_0016_broken() -> Json:
    doc = _syn_0016_good()
    doc["synthesis_text"] = (
        "Ranked-choice on this ballot set elects a Condorcet loser."
    )
    doc["disposals"] = {}
    return doc


def _syn_0016_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    doc["synthesis_text"] = "No minority positions remain."
    doc["disposals"] = {}
    return doc


def _syn_0017_good() -> Json:
    return {
        "findings": [
            {
                "id": "F-orphan-attach",
                "text": (
                    "orphan claims never attach to a cause node in the "
                    "hierarchy graph"
                ),
            },
            {
                "id": "F-archive-crlf",
                "text": "documented git archive recipe yields CRLF blobs on this box",
            },
        ]
    }


def _syn_0017_broken() -> Json:
    return {
        "findings": [
            {
                "id": "F-orphan-attach",
                "text": "orphan claims never attach to a cause node",
            },
            {
                "id": "F-orphan-rename",
                "text": "orphan_claims never attach to a cause node",
            },
        ]
    }


def _syn_0017_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    original = doc["findings"][0]["text"]
    doc["findings"].append(
        {
            "id": "F-orphan-paraphrase",
            "text": original.replace("never attach", "do not attach"),
        }
    )
    return doc


def _syn_0018_good() -> Json:
    return {
        "recipe": "git-cat-file",
        "anchors": [
            {
                "id": "A1",
                "path": "AGENTS.md",
                "capture_text": "two strikes then pivot",
                "report_text": "two strikes then pivot",
                "capture_line": 40,
                "report_line": 40,
                "file_gone": False,
            }
        ],
    }


def _syn_0018_broken() -> Json:
    return {
        "recipe": "git-cat-file",
        "anchors": [
            {
                "id": "A1",
                "path": "AGENTS.md",
                "capture_text": "two strikes then pivot",
                "report_text": "two strikes then pivot ALWAYS",
                "capture_line": 40,
                "report_line": 40,
                "file_gone": False,
            },
            {
                "id": "A2",
                "path": "missing.md",
                "capture_text": "was here",
                "report_text": "was here",
                "capture_line": 1,
                "report_line": 1,
                "file_gone": True,
            },
        ],
    }


def _syn_0018_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    doc["anchors"][0]["report_line"] = doc["anchors"][0]["capture_line"] + 3
    return doc


def _syn_0019_good() -> Json:
    return {
        "now": 1700,
        "verified_at": 1600,
        "window_seconds": 600,
        "manifest": [
            {
                "path": "command-center/synthesis/final.json",
                "hash": "abc123",
                "bytes": 200,
            }
        ],
        "files": {
            "command-center/synthesis/final.json": {
                "hash": "abc123",
                "bytes": 200,
                "content": "{'ok': true}",
            }
        },
    }


def _syn_0019_broken() -> Json:
    doc = _syn_0019_good()
    doc["files"] = {}
    return doc


def _syn_0019_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    path = doc["manifest"][0]["path"]
    doc["files"][path] = {"hash": "abc123", "bytes": 0, "content": ""}
    return doc


def _syn_0020_good() -> Json:
    return {
        "statements": [
            {
                "id": "S-archive",
                "text": "verify against the LF blob (git archive)",
                "verdict": "CONTRADICT",
                "test_id": "TST-blob-crlf",
            },
            {
                "id": "S-untested",
                "text": "the dashboard always refreshes within 50ms",
                "verdict": "UNTESTED",
                "test_id": None,
            },
        ],
        "commands": [
            {"id": "C-noexec", "text": "rm -rf /", "noexec": True, "executed": False}
        ],
    }


def _syn_0020_broken() -> Json:
    doc = _syn_0020_good()
    doc["statements"][0]["verdict"] = "AGREE"
    doc["statements"][1]["verdict"] = "AGREE"
    doc["commands"][0]["executed"] = True
    return doc


def _syn_0020_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    doc["statements"][0]["verdict"] = "AGREE"
    return doc


def _syn_0021_good() -> Json:
    return {
        "predicate_source": "shared-reducer",
        "claims": [
            {
                "id": "C-done",
                "kind": "claim",
                "text": "SYN-0011 shipped successfully",
                "label": "SUCCESS",
                "artifact_missing": False,
                "predicate_true": True,
                "counted_backed": True,
            },
            {
                "id": "R-must-complete",
                "kind": "requirement",
                "text": "the final report must be complete before the writer runs",
                "label": None,
                "artifact_missing": True,
                "predicate_true": False,
                "counted_backed": False,
            },
        ],
    }


def _syn_0021_broken() -> Json:
    return {
        "predicate_source": "shared-reducer",
        "claims": [
            {
                "id": "C-false-green",
                "kind": "claim",
                "text": "SUCCESS: the writer finished",
                "label": "SUCCESS",
                "artifact_missing": True,
                "predicate_true": False,
                "counted_backed": True,
            }
        ],
    }


def _syn_0021_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    doc["claims"][0]["artifact_missing"] = True
    doc["claims"][0]["predicate_true"] = False
    doc["claims"][0]["counted_backed"] = True
    return doc


def _syn_0030_good() -> Json:
    return {
        "join_key": "id",
        "units": ["SYN-0040"],
        "artifacts": ["art-syn-0040"],
        "tests": ["T-row"],
        "claims": ["CL-matrix"],
        "unit_to_artifact": {"SYN-0040": "art-syn-0040"},
        "artifact_to_unit": {"art-syn-0040": "SYN-0040"},
        "test_to_claim": {"T-row": "CL-matrix"},
        "claim_to_test": {"CL-matrix": "T-row"},
        "unit_to_claim": {"SYN-0040": "CL-matrix"},
        "claim_to_unit": {"CL-matrix": "SYN-0040"},
        "artifact_to_test": {"art-syn-0040": "T-row"},
        "test_to_artifact": {"T-row": "art-syn-0040"},
    }


def _syn_0030_broken() -> Json:
    doc = _syn_0030_good()
    doc["units"] = ["SYN-0040", "SYN-9999"]
    return doc


def _syn_0030_mutate(good: Json) -> Json:
    doc = copy.deepcopy(good)
    doc["join_key"] = "title"
    return doc


def _cal_silent() -> Json:
    return {"note": "inert detector always exits 0"}


SPECS: dict[str, dict[str, Any]] = {
    "SYN-0002": {
        "title": "hierarchy structural integrity",
        "good": _syn_0002_good,
        "broken": _syn_0002_broken,
        "mutate": _syn_0002_mutate,
        "mutation_name": "reintroduce-orphan-claim",
    },
    "SYN-0013": {
        "title": "digest-boundary EVIDENCE block / use-vs-mention",
        "good": _syn_0013_good,
        "broken": _syn_0013_broken,
        "mutate": _syn_0013_mutate,
        "mutation_name": "strip-EVIDENCE-block",
    },
    "SYN-0016": {
        "title": "omitted-dissent audit",
        "good": _syn_0016_good,
        "broken": _syn_0016_broken,
        "mutate": _syn_0016_mutate,
        "mutation_name": "drop-all-dissents-from-synthesis",
    },
    "SYN-0017": {
        "title": "duplicate-mechanism collapse",
        "good": _syn_0017_good,
        "broken": _syn_0017_broken,
        "mutate": _syn_0017_mutate,
        "mutation_name": "reintroduce-paraphrase-duplicate",
    },
    "SYN-0018": {
        "title": "stale-evidence re-validation",
        "good": _syn_0018_good,
        "broken": _syn_0018_broken,
        "mutate": _syn_0018_mutate,
        "mutation_name": "insert-lines-above-anchor",
    },
    "SYN-0019": {
        "title": "report-time manifest verification gate",
        "good": _syn_0019_good,
        "broken": _syn_0019_broken,
        "mutate": _syn_0019_mutate,
        "mutation_name": "truncate-listed-artifact",
    },
    "SYN-0020": {
        "title": "docs-versus-code parity",
        "good": _syn_0020_good,
        "broken": _syn_0020_broken,
        "mutate": _syn_0020_mutate,
        "mutation_name": "mark-git-archive-AGREE",
    },
    "SYN-0021": {
        "title": "completion-claim census",
        "good": _syn_0021_good,
        "broken": _syn_0021_broken,
        "mutate": _syn_0021_mutate,
        "mutation_name": "SUCCESS-with-missing-artifact",
    },
    "SYN-0030": {
        "title": "four-registry referential join",
        "good": _syn_0030_good,
        "broken": _syn_0030_broken,
        "mutate": _syn_0030_mutate,
        "mutation_name": "join-by-title",
    },
    CALIBRATION_ID: {
        "title": "planted inert detector (always silent)",
        "good": _cal_silent,
        "broken": _cal_silent,
        "mutate": lambda g: g,
        "mutation_name": "none",
    },
}


def fixture_dir(gate_id: str) -> Path:
    return REPO / FIXTURES_REL / gate_id


def materialize(gate_ids: list[str] | None = None) -> dict[str, dict[str, str]]:
    ids = list(gate_ids or (BUCKET_UNITS + [CALIBRATION_ID]))
    written: dict[str, dict[str, str]] = {}
    for gid in ids:
        spec = SPECS[gid]
        dest = fixture_dir(gid)
        dest.mkdir(parents=True, exist_ok=True)
        mapping: dict[str, str] = {}
        for label, builder in (
            ("good", spec["good"]),
            ("broken", spec["broken"]),
        ):
            path = dest / f"{label}.json"
            path.write_text(
                json.dumps(builder(), indent=1, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            mapping[label] = path.relative_to(REPO).as_posix()
        mutated = spec["mutate"](spec["good"]())
        mpath = dest / "mutated.json"
        mpath.write_text(
            json.dumps(mutated, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        mapping["mutated"] = mpath.relative_to(REPO).as_posix()
        written[gid] = mapping
    return written
