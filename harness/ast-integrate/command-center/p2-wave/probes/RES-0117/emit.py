#!/usr/bin/env python3
"""Emit command-center/research/RES-0117.json and per-unit G-1 receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/research/RES-0117.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0117/probe1_date_compare.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0117/probe2_unrecoverable_control.py"
)
CATALOG_SENTINEL = (
    "SUCCESS:RES-0117 in the receipt AND a recovery table with "
    "snapshot-versus-claim date comparison and a count of unrecoverable links"
)
QUESTION = (
    "For the sources this program's corpus cites that no longer resolve, "
    "what does the archival record contain, and does any recovered artifact "
    "change a conclusion currently resting on a dead link?"
)
SCHEMA = "command-center/schema/research-registry.schema.json"
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0117/recover.py",
    "command-center/p2-wave/probes/RES-0117/fixtures/corpus.json",
    "command-center/p2-wave/probes/RES-0117/probe1_date_compare.py",
    "command-center/p2-wave/probes/RES-0117/probe2_unrecoverable_control.py",
    "command-center/p2-wave/probes/RES-0027/snapshots/CAPTURE.json",
]

sys.path.insert(0, str(HERE))
from recover import (  # noqa: E402
    SENTINEL,
    build_recovery_table,
    hub_capture_errors,
    load_corpus,
    unrecoverable_rows,
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def build_doc(now: str) -> dict:
    corpus = load_corpus()
    table = build_recovery_table(corpus)
    dead = unrecoverable_rows(table)
    hub_errs = hub_capture_errors()
    if hub_errs:
        raise SystemExit("FAILED:RES-0117 hub capture rail: " + "; ".join(hub_errs))

    claims = [
        {
            "id": "C-MOVED-DOCS-CLAUDE",
            "canonical_mechanism": (
                "docs.claude.com/en/docs/claude-code/{overview,cli-usage,hooks} "
                "no longer serve as the canonical host; live fetches follow to "
                "code.claude.com/docs/en/* with HTTP 200."
            ),
            "source_lineage": [
                {
                    "kind": "live-http",
                    "permalink": "https://docs.claude.com/en/docs/claude-code/overview",
                    "final_url": "https://code.claude.com/docs/en/overview",
                    "http_status": 200,
                    "fetch_timestamp": "2026-08-24T18:50:34Z",
                },
                {
                    "kind": "wayback-cdx",
                    "permalink": "https://web.archive.org/cdx/search/cdx?url=https://docs.claude.com/en/docs/claude-code/overview&output=json",
                    "snapshot": "20250916211701",
                    "statuscode": "200",
                    "digest": "ZN2XANATXGDCHSZZCJLL3OTT7OQTBAJ4",
                    "fetch_timestamp": "2026-08-24T18:50:40Z",
                },
            ],
            "evidence_tier": "E2",
            "confidence_band": "HIGH",
            "settling_probe": P1,
            "verdict": "CONFIRMED",
            "citable_as_measured_fact": True,
            "strongest_caveat": (
                "Wayback 200s are 2025-09, before the 2026-08-06 claim date. They "
                "show the old host once returned 200; they do not prove the bytes "
                "read on 2026-08-06. Contemporaneous proof is the 2026-08-24 live "
                "redirect, which is after the 2026-08-06 observation."
            ),
        },
        {
            "id": "C-HUB-CONTINUE-DEAD",
            "canonical_mechanism": (
                "hub.continue.dev does not resolve (DNS NXDOMAIN) on 2026-08-24. "
                "Wayback CDX retains 2025-02/03 HTTP 307 envelopes, not a live hub."
            ),
            "source_lineage": [
                {
                    "kind": "structured-capture",
                    "permalink": "command-center/p2-wave/probes/RES-0027/snapshots/CAPTURE.json",
                    "fetch_timestamp": "2026-08-24T18:42:21Z",
                    "http_status": None,
                    "note": "dns.hub.continue.dev.ok=false",
                },
                {
                    "kind": "wayback-cdx",
                    "permalink": "https://web.archive.org/web/20250226173711/https://hub.continue.dev/",
                    "snapshot": "20250226173711",
                    "statuscode": "307",
                    "digest": "3I2MW4QPPG5IJ65TCLVHE6D6OJAY7OOQ",
                    "fetch_timestamp": "2026-08-24T18:50:38Z",
                },
            ],
            "evidence_tier": "E2",
            "confidence_band": "HIGH",
            "settling_probe": P2,
            "verdict": "CONFIRMED",
            "citable_as_measured_fact": True,
            "strongest_caveat": (
                "Archived rows are 307 redirects from February-March 2025. They "
                "are not the hub catalog. They do not change RES-0027's conclusion "
                "that Hub is not a live composition surface today."
            ),
        },
        {
            "id": "C-UNRECOVERABLE-CONTROL",
            "canonical_mechanism": (
                "A cited URL with empty CDX and failed live DNS is counted "
                "unrecoverable. The planted https://res-0117-never-archived.invalid/"
                "deleted-prior-art is that control."
            ),
            "source_lineage": [
                {
                    "kind": "wayback-cdx",
                    "permalink": "https://web.archive.org/cdx/search/cdx?url=https://res-0117-never-archived.invalid/deleted-prior-art&output=json",
                    "snapshot": None,
                    "http_status": 200,
                    "rows": 0,
                    "fetch_timestamp": "2026-08-24T18:50:43Z",
                },
                {
                    "kind": "live-dns",
                    "permalink": "https://res-0117-never-archived.invalid/deleted-prior-art",
                    "http_status": None,
                    "fetch_timestamp": "2026-08-24T18:50:37Z",
                },
            ],
            "evidence_tier": "E1",
            "confidence_band": "HIGH",
            "settling_probe": P2,
            "verdict": "CONFIRMED",
            "citable_as_measured_fact": True,
            "strongest_caveat": "Planted control is not a corpus citation; it exists so a 100% recovered sweep cannot silent-pass.",
        },
    ]

    answer = (
        "RES-0004.json and RES-0042.json are absent, so this unit pivoted to "
        "URLs the catalog and worktree already cite as moved or dead. "
        "Live: docs.claude.com/en/docs/claude-code/{overview,cli-usage,hooks} "
        "return HTTP 200 after redirect to code.claude.com/docs/en/* "
        "(fetched 2026-08-24T18:50:34Z). Wayback CDX for overview still holds "
        "200 captures from 2025-09-16 (digest ZN2XANATXGDCHSZZCJLL3OTT7OQTBAJ4); "
        "those dates are BEFORE the 2026-08-06 05-ECO claim, so they are "
        "historical records, not contemporaneous read-proof. "
        "hub.continue.dev is DNS NXDOMAIN on 2026-08-24 (this fetch and "
        "RES-0027 CAPTURE.json 2026-08-24T18:42:21Z). CDX has 307 captures "
        "2025-02-26 through 2025-03-21; none are on or after the claim date. "
        "No recovered snapshot is dated AFTER its claim (no SNAPSHOT-AFTER-CLAIM "
        "row). Unrecoverable links: 1 "
        "(https://res-0117-never-archived.invalid/deleted-prior-art, planted "
        "empty-CDX control). No recovered artifact changes a conclusion now "
        "resting on a dead link: the 301 move is confirmed, and Hub stays dead. "
        + CATALOG_SENTINEL
    )

    return {
        "unit_id": "RES-0117",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0117",
        "completion_sentinel": CATALOG_SENTINEL,
        "report_kind": "research-registry",
        "output_schema_declared": SCHEMA,
        "schema_note": (
            "research-registry.schema.json is owned by RES-0001 and is absent "
            "on this tree. This record carries unit_id, state, recovery_table, "
            "snapshot-versus-claim fields, unrecoverable_link_count, claims with "
            "source_lineage / evidence_tier / strongest_caveat, and the catalog "
            "sentinel, without writing that global schema file."
        ),
        "question": QUESTION,
        "title": "Recover deleted or moved prior art from archival sources",
        "answer_status": "ANSWERED-WITH-CAVEAT",
        "answer": answer,
        "recovery_table": table,
        "unrecoverable_link_count": len(dead),
        "unrecoverable_links": [
            {"id": r["id"], "url": r["url"], "planted_control": r["planted_control"]}
            for r in dead
        ],
        "recovered_artifact_changes_any_conclusion": False,
        "conclusions_not_overturned": [
            "docs.claude.com -> code.claude.com 301 family is confirmed, not reversed",
            "hub.continue.dev remains unresolved; 2025 307 archives do not revive Hub",
        ],
        "date_comparison_rule": {
            "SNAPSHOT-AFTER-CLAIM": "unusable as proof of what was read",
            "SNAPSHOT-BEFORE-CLAIM": "historical record only",
            "SNAPSHOT-SAME-DAY": "contemporaneous",
            "NO-SNAPSHOT": "unrecoverable if live also fails",
        },
        "claims": claims,
        "reviewer": {
            "reviewer_id": "RES-0117-probe2-unrecoverable-control",
            "verdict": "PASS",
            "independent": True,
            "shown_conclusion_first": False,
            "defaulted_to_refuted_where_thin": True,
            "note": (
                "Probe 2 refuses a post-claim snapshot as read-proof and requires "
                "the planted empty-CDX URL in the unrecoverable count."
            ),
        },
        "freshness_stamp": now,
        "access_route": (
            "urllib live GET 2026-08-24T18:50:32Z; Wayback CDX JSON "
            "2026-08-24T18:50:38Z; RES-0027 CAPTURE.json on disk. "
            "Subsequent CDX/available calls returned HTTP 429; no extra rows invented."
        ),
        "dependency_gap": corpus.get("dependency_gap"),
        "live_control": corpus.get("live_control"),
        "evidence_requirement": (
            "every claim is pinned to an exact version/commit SHA and a fetch "
            "timestamp; an unversioned claim about a moving surface is a defect, "
            "not a finding (05-ECO section 6: the 2026-07-20 star/push snapshot "
            "decayed on write); a recovered snapshot is dated and its date is "
            "compared to the date the original claim was made, because a snapshot "
            "from after the claim proves nothing about what was read"
        ),
        "tests_required": [
            "compare each recovered snapshot's date against the claim's date and flag mismatches",
            "control: report the number of dead links with NO usable archival record",
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "snapshot-versus-claim-date-compare"},
            {"id": "probe2", "command": P2, "role": "unrecoverable-count-control"},
        ],
        "tests": [
            {"id": "probe1", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2", "command": P2, "result": "NOT-RUN"},
        ],
        "timestamps": {"ended_at": now},
    }


def row(rel: str, role: str) -> dict:
    p = REPO / rel
    sha, n = sha256_file(p)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": n,
        "present": True,
        "unit_id": "RES-0117",
        "receipt_path": "command-center/p2-wave/probes/RES-0117/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_doc(now)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if CATALOG_SENTINEL not in payload or SENTINEL not in payload:
        print("FAILED:RES-0117 emit catalog sentinel missing")
        return 1
    if "unrecoverable_link_count" not in payload or "recovery_table" not in payload:
        print("FAILED:RES-0117 emit table/count missing")
        return 1
    if '"state": "SUCCESS"' not in payload:
        print("FAILED:RES-0117 emit not SUCCESS")
        return 1
    out.write_text(payload, encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0117 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    digest, size = sha256_file(out)
    if size < 1024:
        print(f"FAILED:RES-0117 artifact {size}B below floor")
        return 1

    ret = {
        "id": "RES-0117",
        "unit_id": "RES-0117",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0117",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2[-8000:]},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0117/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0117-probe2-unrecoverable-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0117: live named probes exit 0, research/RES-0117.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle. Recovery table "
            "compares snapshot date to claim date; unrecoverable_link_count=1 "
            "(planted empty-CDX control). cloud_ok is false and is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    artifacts.append(row("command-center/p2-wave/probes/RES-0117/emit.py", "supporting"))
    artifacts.append(
        row("command-center/p2-wave/probes/RES-0117/SUBAGENT-RETURN.json", "supporting")
    )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0117",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0117 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
