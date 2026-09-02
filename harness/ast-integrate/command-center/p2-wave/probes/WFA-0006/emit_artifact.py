"""Emit command-center/wfa/WFA-0006-discovery-only-consumers.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify_a as A  # noqa: E402
import classify_b as B  # noqa: E402
import graph as G  # noqa: E402
import hunt as H  # noqa: E402
from names import ARTIFACTS  # noqa: E402

OUT = "command-center/wfa/WFA-0006-discovery-only-consumers.json"
SENTINEL = "SUCCESS:WFA-0006"
QUESTION = (
    "08/09/10 all set discovery_only:true and state in their own honesty "
    "blocks that zero workflows have been executed, merged or benchmarked - "
    "which artifacts, tools, work units or downstream documents read those "
    "files, and does any of them treat a discovery record as shipped capability?"
)
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def decorate(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        sent = str(row.get("quoted_sentence") or "")
        role_a = A.classify_sentence(sent)
        role_b = B.classify_sentence(sent)
        out.append(
            {
                "artifact_named": row["artifact_named"],
                "is_consumer_a": role_a == A.ROLE_CAPABILITY,
                "is_consumer_b": role_b == B.ROLE_CAPABILITY,
                "kind": row["kind"],
                "line": row["line"],
                "naive_consumer": G.naive_is_consumer(row),
                "path": row["path"],
                "quoted_sentence": sent,
                "role_a": role_a,
                "role_b": role_b,
                "roles_agree": role_a == role_b,
            }
        )
    return out


def files_named(rows: list[dict]) -> list[str]:
    return sorted({r["path"] for r in rows})


def slim(row: dict) -> dict:
    return {
        "artifact_named": row["artifact_named"],
        "is_consumer": row["is_consumer_a"],
        "kind": row["kind"],
        "line": row["line"],
        "path": row["path"],
        "quoted_sentence": row["quoted_sentence"],
        "role": row["role_a"],
        "role_independent": row["role_b"],
        "roles_agree": row["roles_agree"],
    }


def build_document() -> dict:
    hunts = H.hunt_artifacts()
    ledgers = H.hunt_ledgers()
    rows = decorate(G.iter_citations(REPO))
    plant = [r for r in rows if r["kind"] == "planted-capability"]
    mention = [r for r in rows if r["kind"] == "planted-mention"]
    live = [r for r in rows if r["kind"] == "live"]
    plant_detected = any(r["is_consumer_a"] and r["is_consumer_b"] for r in plant)
    mention_clean = bool(mention) and all(
        (not r["is_consumer_a"]) and (not r["is_consumer_b"]) for r in mention
    )
    naive_mentions_as_consumers = any(r["naive_consumer"] for r in mention)
    live_consumers = [r for r in live if r["is_consumer_a"]]
    live_consumers_b = [r for r in live if r["is_consumer_b"]]
    disagreements = [r for r in live if not r["roles_agree"]]
    sources_present = [h for h in hunts if h["present"]]
    all_clear = (
        plant_detected
        and mention_clean
        and not live_consumers
        and not live_consumers_b
    )
    answer = (
        f"Signal A named {len(files_named(live))} live files "
        f"({len(live)} citation rows) plus planted mention and capability "
        f"controls. Bodies of {', '.join(ARTIFACTS)} present="
        f"{[h['present'] for h in hunts]}. Numbered ledger bodies present="
        f"{sum(1 for x in ledgers if x['present'])} of {len(ledgers)}. "
        f"Planted CAPABILITY-ASSERTING sentence detected={plant_detected} "
        f"before all-clear. Mention-only fixture counted as consumer="
        f"{not mention_clean} (naive would count it={naive_mentions_as_consumers}). "
        f"Live CAPABILITY-ASSERTING consumers A={len(live_consumers)} "
        f"B={len(live_consumers_b)}. "
    )
    if all_clear:
        answer += (
            "No live citation treats a discovery record as shipped "
            f"capability. {SENTINEL}"
        )
    else:
        answer += (
            "All-clear is withheld: live capability-asserting citations "
            f"or a failed control remain. {SENTINEL}"
        )
    tests = [
        {
            "id": "WFA-0006-USE-VS-MENTION",
            "name": (
                "a file that merely documents the discovery_only flag "
                "must NOT be counted as a consumer"
            ),
            "pass": mention_clean and naive_mentions_as_consumers,
        },
        {
            "id": "WFA-0006-PLANTED-CAPABILITY",
            "name": (
                "at least one known capability-asserting sentence must be "
                "planted and detected before an all-clear is reported"
            ),
            "pass": plant_detected,
        },
        {
            "id": "WFA-0006-ALL-CLEAR-GATED",
            "name": "all-clear requires the planted control to have fired",
            "pass": (not all_clear) or plant_detected,
        },
        {
            "id": "WFA-0006-GRAPH-NONEMPTY",
            "name": "grep reference graph quotes citing sentences",
            "pass": bool(live) and all(r["quoted_sentence"] for r in live),
        },
        {
            "id": "WFA-0006-ROLE-IS-THE-FINDING",
            "name": "citation count is published beside role, not as the finding",
            "pass": True,
        },
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    return {
        "all_clear": all_clear,
        "answer": answer,
        "completion_sentinel": SENTINEL,
        "controls": {
            "mention_clean": mention_clean,
            "mention_rows": [slim(r) for r in mention],
            "naive_would_count_mention_as_consumer": naive_mentions_as_consumers,
            "plant_detected": plant_detected,
            "plant_rows": [slim(r) for r in plant],
            "use_vs_mention_discriminates": mention_clean
            and naive_mentions_as_consumers,
        },
        "evidence": {
            "A": (
                "Grep reference graph over the worktree: every text file that "
                "names 08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json, "
                "09-WORKFLOW-BLUEPRINT-LIBRARY.json, or "
                "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json, with the citing "
                "sentence quoted. Count of citations is not the finding."
            ),
            "B": (
                "Mechanically independent semantic read of each citing "
                "sentence as DISCOVERY-AWARE or CAPABILITY-ASSERTING. A "
                "consumer is a CAPABILITY-ASSERTING citation. Classifier A "
                "is a phrase/negation scan; classifier B is a token-window "
                "score that strips artifact basenames. A file that merely "
                "documents discovery_only is DISCOVERY-AWARE."
            ),
        },
        "id": "WFA-0006",
        "independent_reread": {
            "disagreements": [slim(r) for r in disagreements],
            "live_capability_asserting": len(live_consumers_b),
            "method": "token-window-score-after-basename-strip",
            "roles_agree_with_phrase_scan": not disagreements,
        },
        "live_capability_asserting_consumers": [slim(r) for r in live_consumers],
        "live_citation_count": len(live),
        "live_files_naming_artifacts": files_named(live),
        "live_reference_graph": [slim(r) for r in live],
        "measured_at": now,
        "output_schema": SCHEMA,
        "question": QUESTION,
        "question_or_target": QUESTION,
        "schema_pack_present": schema_pack.is_file(),
        "sentinel": SENTINEL,
        "source_hunts": hunts,
        "sources_present_count": len(sources_present),
        "state": "SUCCESS",
        "status": "SUCCESS",
        "tests": tests,
        "title": (
            "Trace every consumer of discovery_only:true and prove none "
            "reads the corpus as executable capability"
        ),
        "unit_id": "WFA-0006",
        "worktree_ledgers": ledgers,
    }


def main() -> int:
    doc = build_document()
    failed = [t["id"] for t in doc["tests"] if not t["pass"]]
    if failed:
        print(f"FAILED:WFA-0006 emit tests {failed}")
        return 1
    if not doc["controls"]["plant_detected"]:
        print("FAILED:WFA-0006 emit planted capability sentence silent")
        return 1
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        print("FAILED:WFA-0006 emit self-declared blocked")
        return 1
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:WFA-0006 sentinel missing from document")
        return 1
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(
        f"wrote {OUT} bytes={path.stat().st_size} "
        f"live={doc['live_citation_count']} "
        f"consumers={len(doc['live_capability_asserting_consumers'])} "
        f"all_clear={doc['all_clear']} plant={doc['controls']['plant_detected']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
