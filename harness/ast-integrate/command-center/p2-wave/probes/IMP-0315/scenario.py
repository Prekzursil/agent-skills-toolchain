"""Five recorded councils for IMP-0315 rebuild/replay probes.

Each spec is played through EventStore with deterministic timestamps so the
JSONL and the derived artifact are stable. The log is the recording; the
artifact JSON is the byte-compared original.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.council.artifacts.store import EventStore, canonical_dumps  # noqa: E402

FIXTURE_NAMES = (
    "c-unanimous-alpha",
    "c-split-dissent",
    "c-pause-resume",
    "c-confidence-dip",
    "c-no-decision",
)


def _play(store: EventStore, spec: dict[str, Any]) -> None:
    store.start(spec["id"], spec["participants"], spec["seed"])
    paused_after = spec.get("pause_after_round")
    for rnd in spec["rounds"]:
        n = int(rnd["round"])
        store.open_round(n)
        for turn in rnd["turns"]:
            store.record_turn(turn["actor"], turn["text"], n)
        for vote in rnd["votes"]:
            store.cast_vote(vote["actor"], vote["choice"], n)
        for conf in rnd["confidence"]:
            store.update_confidence(conf["actor"], conf["value"], n)
        for diss in rnd.get("dissent") or []:
            store.record_dissent(diss["actor"], diss["claim"], n)
        if paused_after is not None and n == paused_after:
            store.pause(reason="recorded-mid-council")
            store.resume()
    d = spec["decision"]
    store.commit_decision(d["kind"], d.get("value"), d["rule_id"], d["tally"])
    store.complete()


def specs() -> list[dict[str, Any]]:
    a, s, p = "architect", "skeptic", "pragmatist"
    return [
        {
            "id": "c-unanimous-alpha",
            "seed": "seed-alpha",
            "participants": [a, s, p],
            "rounds": [
                {
                    "round": 1,
                    "turns": [
                        {"actor": a, "text": "Ship the store as log-derived views."},
                        {"actor": s, "text": "Need a rebuild byte-compare first."},
                        {"actor": p, "text": "Record three rounds then freeze the log."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "ship"},
                        {"actor": s, "choice": "ship"},
                        {"actor": p, "choice": "ship"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.41},
                        {"actor": s, "value": 0.38},
                        {"actor": p, "value": 0.44},
                    ],
                    "dissent": [],
                },
                {
                    "round": 2,
                    "turns": [
                        {"actor": a, "text": "Rebuild matched the original artifact."},
                        {"actor": s, "text": "Hash chain held after the first pause drill."},
                        {"actor": p, "text": "Keep dissent as its own event kind."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "ship"},
                        {"actor": s, "choice": "ship"},
                        {"actor": p, "choice": "ship"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.66},
                        {"actor": s, "value": 0.61},
                        {"actor": p, "value": 0.70},
                    ],
                    "dissent": [],
                },
                {
                    "round": 3,
                    "turns": [
                        {"actor": a, "text": "Unanimous. Commit."},
                        {"actor": s, "text": "No minority report on this council."},
                        {"actor": p, "text": "Artifact schema council-artifact/v1."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "ship"},
                        {"actor": s, "choice": "ship"},
                        {"actor": p, "choice": "ship"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.91},
                        {"actor": s, "value": 0.88},
                        {"actor": p, "value": 0.90},
                    ],
                    "dissent": [],
                },
            ],
            "decision": {
                "kind": "DECIDED",
                "value": "ship-event-store",
                "rule_id": "unanimous-3",
                "tally": {"ship": 9},
            },
        },
        {
            "id": "c-split-dissent",
            "seed": "seed-split",
            "participants": [a, s, p],
            "rounds": [
                {
                    "round": 1,
                    "turns": [
                        {"actor": a, "text": "Accept the compact transcript."},
                        {"actor": s, "text": "Compaction drops claim ids. Dissent."},
                        {"actor": p, "text": "Keep ids; compress prose only."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "accept"},
                        {"actor": s, "choice": "reject"},
                        {"actor": p, "choice": "accept"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.55},
                        {"actor": s, "value": 0.22},
                        {"actor": p, "value": 0.48},
                    ],
                    "dissent": [
                        {
                            "actor": s,
                            "claim": "compaction that drops claim-id C-441 is dissent-loss (spec 11342)",
                        }
                    ],
                },
                {
                    "round": 2,
                    "turns": [
                        {"actor": a, "text": "Ids survive; I still vote accept."},
                        {"actor": s, "text": "Minority report must remain verbatim."},
                        {"actor": p, "text": "Carry the dissent into the artifact."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "accept"},
                        {"actor": s, "choice": "reject"},
                        {"actor": p, "choice": "accept"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.62},
                        {"actor": s, "value": 0.19},
                        {"actor": p, "value": 0.57},
                    ],
                    "dissent": [
                        {
                            "actor": s,
                            "claim": "compaction that drops claim-id C-441 is dissent-loss (spec 11342)",
                        }
                    ],
                },
            ],
            "decision": {
                "kind": "DECIDED",
                "value": "accept-with-minority",
                "rule_id": "majority-2-1",
                "tally": {"accept": 4, "reject": 2},
            },
        },
        {
            "id": "c-pause-resume",
            "seed": "seed-pause",
            "participants": [a, s, p],
            "pause_after_round": 1,
            "rounds": [
                {
                    "round": 1,
                    "turns": [
                        {"actor": a, "text": "Round 1 claim: resume must restore votes."},
                        {"actor": s, "text": "Park here. Do not drop the skeptic vote."},
                        {"actor": p, "text": "Pause after this round."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "continue"},
                        {"actor": s, "choice": "continue"},
                        {"actor": p, "choice": "continue"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.50},
                        {"actor": s, "value": 0.47},
                        {"actor": p, "value": 0.51},
                    ],
                    "dissent": [],
                },
                {
                    "round": 2,
                    "turns": [
                        {"actor": a, "text": "Resumed. Round-1 votes still present."},
                        {"actor": s, "text": "Minority empty is fine; votes are not."},
                        {"actor": p, "text": "Finish and freeze."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "ship"},
                        {"actor": s, "choice": "ship"},
                        {"actor": p, "choice": "ship"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.77},
                        {"actor": s, "value": 0.74},
                        {"actor": p, "value": 0.80},
                    ],
                    "dissent": [],
                },
            ],
            "decision": {
                "kind": "DECIDED",
                "value": "resume-preserved-votes",
                "rule_id": "resume-round-k",
                "tally": {"continue": 3, "ship": 3},
            },
        },
        {
            "id": "c-confidence-dip",
            "seed": "seed-dip",
            "participants": [a, s, p],
            "rounds": [
                {
                    "round": 1,
                    "turns": [
                        {"actor": a, "text": "High confidence on replay identity."},
                        {"actor": s, "text": "Wait: live model calls are not reproducible."},
                        {"actor": p, "text": "Then bound the claim to recorded payloads."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "bound-claim"},
                        {"actor": s, "choice": "bound-claim"},
                        {"actor": p, "choice": "bound-claim"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.84},
                        {"actor": s, "value": 0.33},
                        {"actor": p, "value": 0.60},
                    ],
                    "dissent": [],
                },
                {
                    "round": 2,
                    "turns": [
                        {"actor": a, "text": "Confidence dipped; evidence is the log."},
                        {"actor": s, "text": "Recover if rebuild stays byte-identical."},
                        {"actor": p, "text": "Trajectory must show the dip, not hide it."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "bound-claim"},
                        {"actor": s, "choice": "bound-claim"},
                        {"actor": p, "choice": "bound-claim"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.45},
                        {"actor": s, "value": 0.40},
                        {"actor": p, "value": 0.42},
                    ],
                    "dissent": [],
                },
                {
                    "round": 3,
                    "turns": [
                        {"actor": a, "text": "Dip recorded. Recovering."},
                        {"actor": s, "text": "Same log, same artifact."},
                        {"actor": p, "text": "Ship the bounded claim."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "bound-claim"},
                        {"actor": s, "choice": "bound-claim"},
                        {"actor": p, "choice": "bound-claim"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.73},
                        {"actor": s, "value": 0.71},
                        {"actor": p, "value": 0.75},
                    ],
                    "dissent": [],
                },
            ],
            "decision": {
                "kind": "DECIDED",
                "value": "replay-recorded-payloads-only",
                "rule_id": "confidence-trajectory-visible",
                "tally": {"bound-claim": 9},
            },
        },
        {
            "id": "c-no-decision",
            "seed": "seed-node",
            "participants": [a, s, p],
            "rounds": [
                {
                    "round": 1,
                    "turns": [
                        {"actor": a, "text": "Proof of impossibility: no shared option."},
                        {"actor": s, "text": "I will not convert this to FAIL."},
                        {"actor": p, "text": "NO-DECISION is a first-class kind."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "no-decision"},
                        {"actor": s, "choice": "no-decision"},
                        {"actor": p, "choice": "hold"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.58},
                        {"actor": s, "value": 0.64},
                        {"actor": p, "value": 0.35},
                    ],
                    "dissent": [
                        {
                            "actor": p,
                            "claim": "a hold is not a no-decision; keep both labels",
                        }
                    ],
                },
                {
                    "round": 2,
                    "turns": [
                        {"actor": a, "text": "Still no shared option."},
                        {"actor": s, "text": "Do not coerce NO-DECISION into FAIL."},
                        {"actor": p, "text": "Dissent stands."},
                    ],
                    "votes": [
                        {"actor": a, "choice": "no-decision"},
                        {"actor": s, "choice": "no-decision"},
                        {"actor": p, "choice": "hold"},
                    ],
                    "confidence": [
                        {"actor": a, "value": 0.70},
                        {"actor": s, "value": 0.72},
                        {"actor": p, "value": 0.31},
                    ],
                    "dissent": [
                        {
                            "actor": p,
                            "claim": "a hold is not a no-decision; keep both labels",
                        }
                    ],
                },
            ],
            "decision": {
                "kind": "NO-DECISION",
                "value": None,
                "rule_id": "no-shared-option",
                "tally": {"no-decision": 4, "hold": 2},
            },
        },
    ]


def record_one(log_path: Path, spec: dict[str, Any]) -> bytes:
    if log_path.exists():
        log_path.unlink()
    store = EventStore.create(log_path)
    _play(store, spec)
    return store.artifact_bytes()


def write_fixtures(root: Path) -> list[dict[str, Any]]:
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in specs():
        d = root / spec["id"]
        d.mkdir(parents=True, exist_ok=True)
        log = d / "events.jsonl"
        art = d / "artifact.json"
        blob = record_one(log, spec)
        art.write_bytes(blob)
        rows.append(
            {
                "id": spec["id"],
                "events": str(log),
                "artifact": str(art),
                "bytes": len(blob),
            }
        )
    (root / "index.json").write_text(
        canonical_dumps({"councils": [r["id"] for r in rows], "n": len(rows)}) + "\n",
        encoding="utf-8",
    )
    return rows


def fixture_root() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def main() -> int:
    rows = write_fixtures(fixture_root())
    print(json.dumps({"wrote": len(rows), "ids": [r["id"] for r in rows]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
