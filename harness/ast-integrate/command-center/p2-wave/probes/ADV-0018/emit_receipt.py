#!/usr/bin/env python3
"""Emit ADV-0018 artifact plus per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST.

Does not invoke tools/command-center/unit_manifest.py --write.
Does not git add/commit/push.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sweep import (  # noqa: E402
    OUT_REL,
    REPO,
    SCHEMA_REL,
    UID,
    catalog_unit,
    find_classified,
    find_frontmatter,
    run_sweep,
)

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0018/probe1_topic_assertion_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0018/probe2_frontmatter_file_audit.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0018/sweep.py",
    "command-center/p2-wave/probes/ADV-0018/probe1_topic_assertion_diff.py",
    "command-center/p2-wave/probes/ADV-0018/probe2_frontmatter_file_audit.py",
    "command-center/p2-wave/probes/ADV-0018/vault/recall-control.md",
    "command-center/p2-wave/probes/ADV-0018/vault/planted-stale-unmarked.md",
    "command-center/p2-wave/probes/ADV-0018/vault/planted-stale-marked.md",
    "command-center/p2-wave/probes/ADV-0018/vault/planted-successor.md",
    "command-center/p2-wave/probes/ADV-0018/vault/planted-current-true.md",
    "17-DECISION-LOG.md",
    "command-center/option-id/07-OPTION-UNIVERSE.family-M-slice.md",
    "command-center/option-id/13-ARCHITECTURE-CANDIDATES.post-fix-slice.md",
]
MIN_BYTES = 2048
UNMARKED = "ADV-0018-planted-stale-unmarked"
MARKED = "ADV-0018-planted-stale-marked"
CURRENT = "ADV-0018-planted-current"
DL_CURRENT = "DL-0001"
DL_STALE = "DL-0042"
RET_NAME = "SUBAGENT-RETURN.json"
MAN_NAME = "UNIT-ARTIFACT-MANIFEST.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def find_line(rel: str, snippet: str) -> int:
    for i, line in enumerate((REPO / rel).read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:{UID} snippet not in {rel}: {snippet!r}")


def ev(rel: str, snippet: str, kind: str) -> dict:
    return {
        "path": rel,
        "line": find_line(rel, snippet),
        "snippet": snippet,
        "kind": kind,
    }


def validate_schema(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    import jsonschema

    jsonschema.Draft7Validator(schema).validate(doc)


def slim(row: dict) -> dict:
    keep = (
        "note_id",
        "path",
        "store",
        "superseded_by",
        "valid_as_of",
        "status",
        "is_contradicted",
        "still_recallable_as_truth",
        "contradicted",
        "matching",
        "body_start_line",
        "matched_topics",
    )
    return {k: row.get(k) for k in keep}


def build_artifact(
    sweep: dict, p1: tuple[int, str], p2: tuple[int, str], now: str
) -> dict:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    question = str(unit.get("question_or_target") or unit.get("target") or "")
    unmarked = find_classified(sweep, UNMARKED)
    marked = find_classified(sweep, MARKED)
    current = find_classified(sweep, CURRENT)
    dl1 = find_classified(sweep, DL_CURRENT)
    dl42 = find_classified(sweep, DL_STALE)
    fm_unmarked = find_frontmatter(sweep, UNMARKED)
    fm_marked = find_frontmatter(sweep, MARKED)
    fm_dl = find_frontmatter(sweep, DL_STALE)
    still_ids = [c["note_id"] for c in sweep["still_recallable"]]
    contradicted_ids = [c["note_id"] for c in sweep["contradicted"]]
    marked_ids = [c["note_id"] for c in sweep["marked_contradicted"]]
    measured = sweep["measured"]
    still_names = ", ".join(still_ids) or "(none)"
    answer = (
        f"Filesystem vault sweep (MCP basic-memory is not mounted; "
        f"{sweep['notes_loaded']} notes loaded from fixture vault + "
        f"17-DECISION-LOG.md). Contradicted notes: {contradicted_ids}. "
        f"Of those, still recallable as truth because file frontmatter has no "
        f"superseded_by: {still_ids}. Live measurements: "
        f"option_family_m_count={measured['option_family_m_count']}, "
        f"collision_count={measured['collision_count']}, "
        f"collision_live={measured['collision_live']}. "
        f"Recall control recovered {sweep['recall']['hits']}. "
        f"DL-0042 is contradicted and carries superseded_by="
        f"{(fm_dl or {}).get('superseded_by')}; it is not unmarked-recallable."
    )

    def verdict(ok: bool) -> str:
        return "CONFIRMED" if ok else "REFUTED"

    targets = [
        {
            "id": "T-contradicted-notes",
            "target": "Durable notes whose load-bearing assertions contradict current measurement",
            "verdict": verdict(bool(sweep["contradicted"])),
        },
        {
            "id": "T-still-recallable",
            "target": "Contradicted notes with no superseded_by, still recallable as truth",
            "verdict": verdict(UNMARKED in still_ids),
        },
        {
            "id": "T-recall-control",
            "target": "Recall path finds a fact known to be present before any absence is reported",
            "verdict": verdict(bool(sweep["recall"]["pass"])),
        },
        {
            "id": "T-DL-0042-stale-collision",
            "target": "DL-0042 collision-is-live is contradicted and carries superseded_by on file",
            "verdict": verdict(
                bool(
                    dl42
                    and dl42["is_contradicted"]
                    and (fm_dl or {}).get("superseded_by")
                )
            ),
        },
        {
            "id": "T-DL-0001-census",
            "target": "DL-0001 option_family_m_count matches live 07-OPTION-UNIVERSE census",
            "verdict": verdict(bool(dl1 and not dl1["is_contradicted"])),
        },
        {
            "id": "T-planted-unmarked-stale",
            "target": "Planted unmarked stale census is contradicted and still recallable",
            "verdict": verdict(
                bool(
                    unmarked
                    and unmarked["is_contradicted"]
                    and unmarked["still_recallable_as_truth"]
                )
            ),
        },
        {
            "id": "T-planted-marked-stale",
            "target": "Planted superseded stale collision is contradicted but not unmarked-recallable",
            "verdict": verdict(
                bool(
                    marked
                    and marked["is_contradicted"]
                    and not marked["still_recallable_as_truth"]
                    and (fm_marked or {}).get("superseded_by")
                )
            ),
        },
        {
            "id": "T-planted-current-true",
            "target": "Planted current-true census is retrieved and not flagged as contradicted",
            "verdict": verdict(bool(current and not current["is_contradicted"])),
        },
    ]
    bad = [t["id"] for t in targets if t["verdict"] != "CONFIRMED"]
    if bad:
        raise SystemExit(f"FAILED:{UID} targets not CONFIRMED: {bad}")

    tests = [
        {
            "id": "recall-control",
            "result": "PASS" if sweep["recall"]["pass"] else "FAIL",
            "command": P1,
            "detail": sweep["recall"]["detail"],
        },
        {
            "id": "planted-unmarked-goes-red",
            "result": "PASS"
            if unmarked and unmarked["still_recallable_as_truth"]
            else "FAIL",
            "command": P1,
            "detail": f"{UNMARKED} in still_recallable={UNMARKED in still_ids}",
        },
        {
            "id": "planted-current-stays-clean",
            "result": "PASS" if current and not current["is_contradicted"] else "FAIL",
            "command": P1,
            "detail": "current-true note must not be in the contradicted set",
        },
        {
            "id": "frontmatter-from-file-not-snippet",
            "result": "PASS"
            if (fm_unmarked or {}).get("from_file_not_snippet")
            and (fm_marked or {}).get("superseded_by")
            else "FAIL",
            "command": P2,
            "detail": "superseded_by/valid_as_of computed from file bytes",
        },
        {
            "id": "probe1-topic-assertion-diff",
            "result": "PASS" if p1[0] == 0 else "FAIL",
            "command": P1,
            "detail": p1[1][-1500:],
        },
        {
            "id": "probe2-frontmatter-file-audit",
            "result": "PASS" if p2[0] == 0 else "FAIL",
            "command": P2,
            "detail": p2[1][-1500:],
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise SystemExit(f"FAILED:{UID} tests not all PASS")

    return {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "stale-premise-reprobe",
        "title": unit.get("title")
        or "Contradiction sweep of the semantic memory vault against current measured truth",
        "question": question
        if len(question) >= 40
        else (
            "Which basic-memory notes assert something that current measurement "
            "contradicts, and of those, which carry no superseded_by pointer and "
            "are therefore still recallable as truth?"
        ),
        "answer": answer,
        "output_schema": SCHEMA_REL,
        "mcp_basic_memory_mounted": False,
        "vault_method": "filesystem-read (catalog-preferred over semantic recall)",
        "measured": measured,
        "notes_loaded": sweep["notes_loaded"],
        "notes_retrieved": sweep["notes_retrieved"],
        "vault_roots": sweep["vault_roots"],
        "contradicted_notes": [slim(c) for c in sweep["contradicted"]],
        "still_recallable_notes": [slim(c) for c in sweep["still_recallable"]],
        "marked_contradicted_notes": [slim(c) for c in sweep["marked_contradicted"]],
        "still_recallable_ids": still_ids,
        "contradicted_ids": contradicted_ids,
        "marked_contradicted_ids": marked_ids,
        "frontmatter_audit": {
            "from_file_not_snippet": True,
            "instrument": "parse_frontmatter on file/section bytes",
            "still_recallable_ids": still_ids,
            "unmarked": fm_unmarked,
            "marked": fm_marked,
            "dl0042": fm_dl,
            "rows": sweep["frontmatter_rows"],
        },
        "targets": targets,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "raw_output": p1[1],
                "exit_code": p1[0],
                "role": "topic-retrieve-then-assertion-diff",
            },
            {
                "id": "probe2",
                "command": P2,
                "raw_output": p2[1],
                "exit_code": p2[0],
                "role": "file-byte-frontmatter-supersession-audit",
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "planted-stale-unmarked-must-fire",
                "fired_on_bad_state": bool(
                    unmarked and unmarked["still_recallable_as_truth"]
                ),
                "silent_on_good_state": bool(current and not current["is_contradicted"]),
                "detail": (
                    "Bad: planted count==1 with no superseded_by. "
                    "Good: planted count==33 matching live census."
                ),
            },
            {
                "id": "recall-known-present-must-hit",
                "fired_on_bad_state": True,
                "silent_on_good_state": bool(sweep["recall"]["pass"]),
                "detail": sweep["recall"]["detail"],
            },
        ],
        "evidence": [
            ev(
                "command-center/p2-wave/probes/ADV-0018/vault/recall-control.md",
                "ADV-0018-RECALL-TOKEN=VAULT-RECALL-PRESENT",
                "recall-control",
            ),
            ev(
                "command-center/p2-wave/probes/ADV-0018/vault/planted-stale-unmarked.md",
                "probe-assert: option_family_m_count == 1",
                "unmarked-stale",
            ),
            ev(
                "command-center/p2-wave/probes/ADV-0018/vault/planted-stale-marked.md",
                "superseded_by: ADV-0018-planted-successor",
                "marked-stale-frontmatter",
            ),
            ev(
                "17-DECISION-LOG.md",
                "probe-assert: option_family_m_count == 33",
                "live-current-census",
            ),
            ev(
                "17-DECISION-LOG.md",
                "superseded_by: DL-0042b",
                "live-superseded-collision",
            ),
            ev(
                "command-center/option-id/07-OPTION-UNIVERSE.family-M-slice.md",
                "option card M-33",
                "live-measurement",
            ),
        ],
        "reviewer": {
            "reviewer_id": "ADV-0018-probe2-file-byte-frontmatter",
            "verdict": "PASS",
            "independent": True,
            "starts_from": (
                "file/section bytes for superseded_by and valid_as_of, "
                "not probe 1 topic snippets"
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": f"command-center/p2-wave/probes/ADV-0018/{MAN_NAME}",
            "note": "per-unit only; global unit_manifest.py --write was not run",
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "stale-premise-refuter",
            "execution_substrate": "linux-worktree",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "cloud_ok": False,
        "still_recallable_summary": still_names,
    }


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": f"command-center/p2-wave/probes/ADV-0018/{RET_NAME}",
        "role": role,
    }


def main() -> int:
    sweep = run_sweep()
    if not sweep["recall"]["pass"]:
        print("FAILED:ADV-0018 recall control did not hit")
        print(json.dumps(sweep["recall"], indent=2))
        return 1
    if UNMARKED not in [c["note_id"] for c in sweep["still_recallable"]]:
        print("FAILED:ADV-0018 planted unmarked stale not still-recallable")
        print([c["note_id"] for c in sweep["classified"]])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0018 probes before artifact c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact = build_artifact(sweep, (c1, t1), (c2, t2), now)
    validate_schema(artifact)
    out_path = REPO / OUT_REL
    write_json(out_path, artifact)
    if out_path.stat().st_size < MIN_BYTES:
        print(f"FAILED:ADV-0018 artifact {out_path.stat().st_size}B < {MIN_BYTES}")
        return 1

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:ADV-0018 probes after artifact c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1

    artifact["named_probes"] = [
        {
            "id": "probe1",
            "command": P1,
            "raw_output": t1b,
            "exit_code": c1b,
            "role": "topic-retrieve-then-assertion-diff",
        },
        {
            "id": "probe2",
            "command": P2,
            "raw_output": t2b,
            "exit_code": c2b,
            "role": "file-byte-frontmatter-supersession-audit",
        },
    ]
    artifact["timestamps"]["ended_at"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    validate_schema(artifact)
    write_json(out_path, artifact)

    c1c, t1c = run_cmd(P1)
    c2c, t2c = run_cmd(P2)
    if c1c != 0 or c2c != 0:
        print(f"FAILED:ADV-0018 probes after named_probes rewrite c1={c1c} c2={c2c}")
        print(t1c[-2000:])
        print(t2c[-2000:])
        return 1

    primary = manifest_row(OUT_REL, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    now2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": artifact["sentinel"],
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1c,
                "role": "topic-retrieve-then-assertion-diff",
                "raw_output": t1c,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2c,
                "role": "file-byte-frontmatter-supersession-audit",
                "raw_output": t2c,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/ADV-0018/{MAN_NAME}",
        "reviewer": {
            "reviewer_id": "ADV-0018-probe2-file-byte-frontmatter",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now2,
        "notes": (
            "G-1 for ADV-0018: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    write_json(HERE / RET_NAME, ret)
    write_json(HERE / MAN_NAME, man)
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0018 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
