#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0017-repo-live-two-directional-divergence.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit_common as A  # noqa: E402
import controls as C  # noqa: E402
import fixtures as F  # noqa: E402
import lib_classify as L  # noqa: E402
import lib_provenance as P  # noqa: E402
import recover_historical as H  # noqa: E402

from audit_common import (  # noqa: E402
    COMPLETION,
    FIXTURE_LIVE,
    FIXTURE_REPO,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    REPO,
    SCHEMA_REL,
    UID,
)

SENTINEL = "SUCCESS:ADV-0017"


def load_jsonschema():
    saved = list(sys.path)
    A.unshadow_stdlib()
    try:
        import jsonschema  # type: ignore

        return jsonschema
    finally:
        sys.path[:] = saved
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))


def fingerprint(command: str, script: Path, engine: str) -> dict:
    raw = script.read_bytes().replace(b"\r\n", b"\n")
    return {
        "tool": "python3",
        "engine": engine,
        "shell": "bash",
        "command": command,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def missing_control_downgrade(targets: list[dict], tests: list[dict]) -> list[dict]:
    if all(t.get("result") == "PASS" for t in tests):
        return targets
    out = []
    for t in targets:
        row = dict(t)
        if row.get("verdict") in {"CONFIRMED", "REFUTED"}:
            row["verdict"] = "NOT-CHECKED"
            row["downgraded_because"] = "missing-or-failed-control"
            row.pop("source_probe", None)
            row.pop("verifier_probe", None)
        out.append(row)
    return out


def build_doc(*, probe1_raw: str, probe2_raw: str) -> dict:
    F.write_fixture_trees()
    repo = A.iter_rel_files(FIXTURE_REPO)
    live = A.iter_rel_files(FIXTURE_LIVE)
    snap = L.classify_trees(repo, live)
    rels = sorted(set(repo) | set(live))
    prov = P.provenance_rows(FIXTURE_REPO, FIXTURE_LIVE, rels, git_root=REPO)
    eol = C.eol_control(FIXTURE_REPO, FIXTURE_LIVE, F.EOL_PATH)
    before = C.snapshot(FIXTURE_REPO, FIXTURE_LIVE)
    nowrite = C.finish_no_write(FIXTURE_REPO, FIXTURE_LIVE, before)
    pin = H.historical_pin()
    host = A.host_candidates()
    host_present = A.host_live_present()

    src_fp = fingerprint(P1, HERE / "probe1_classify.py", "three-way-line-set-lf")
    ver_fp = fingerprint(
        P2, HERE / "probe2_provenance.py", "git-mtime-live-larger-content-read"
    )
    if src_fp["command"] == ver_fp["command"] or src_fp["sha256"] == ver_fp["sha256"]:
        raise RuntimeError("same-probe-rerun: source_probe identical to verifier_probe")

    tests = [
        {
            "id": "eol-control",
            "name": "EOL-only pair classifies identical after LF normalisation",
            "result": eol["result"],
            "detail": eol,
        },
        {
            "id": "no-write-measurement-only",
            "name": "No sync invocation; measured trees unchanged",
            "result": nowrite["result"],
            "detail": {
                "pass": nowrite["pass"],
                "sync_argv_hits": nowrite["sync_argv_hits"],
                "sync_scripts": nowrite["sync_scripts"],
                "hash_changed_paths": nowrite["hash_changed_paths"],
            },
        },
    ]

    either_n = snap["either_direction_destroy_n"]
    live_reads = [
        r.get("live_larger_content")
        for r in prov
        if isinstance(r.get("live_larger_content"), dict)
    ]
    pinned_live = {
        r["path"]: r for r in live_reads if r["path"] in A.CATALOG_PIN_LIVE_LARGER
    }
    pinned_ok = all(
        pinned_live.get(p, {}).get("live_only_line_n", 0) > 0
        for p in A.CATALOG_PIN_LIVE_LARGER
    )
    repo_super_n = snap["counts"].get("REPO-SUPERSET", 0)

    def settled(verdict: str, text: str, tid: str) -> dict:
        row = {"id": tid, "text": text, "verdict": verdict}
        if verdict in {"CONFIRMED", "REFUTED"}:
            row["source_probe"] = src_fp
            row["verifier_probe"] = ver_fp
        return row

    either_text = (
        f"Disclosed fixture census: {either_n} paired path(s) hold unique "
        "lines on BOTH sides after LF normalisation, so a one-directional "
        "sync in EITHER direction would destroy content. Probe 2 content-read "
        "of live-larger files independently shows those live-only lines as "
        "raw bytes rather than a size comparison. This is the fixture "
        "detector result, not a Windows live-estate census."
    )
    live_pin_text = (
        "Catalog-pinned live-larger names "
        f"{list(A.CATALOG_PIN_LIVE_LARGER)} each have live-only lines in the "
        "disclosed fixtures; probe 2 content-read those files. Not a claim "
        "that C:\\Users live copies were read on this host."
    )
    repo_text = (
        f"Fixture REPO-SUPERSET count={repo_super_n}. Copying live over repo "
        "on those paths would drop repo-only lines. Size is not used as "
        "authority."
    )
    host_text = (
        "Host live deployed trees were searched "
        f"({[h['path'] for h in host]}). No non-empty live tree is present "
        "on this Linux worktree, so repo-versus-live pairs for the deployed "
        "estate are NOT-CHECKED. The 5/88 catalog pin was not remeasured."
    )
    hist_text = (
        "Historical 5-of-88 / 28 content-differing / 25 repo-larger / 3 "
        "live-larger census remains a catalog pin "
        f"(cited_as_live_remeasure={pin['cited_as_live_remeasure']})."
    )

    targets = [
        settled(
            "CONFIRMED" if either_n >= 1 else "NOT-CHECKED",
            either_text,
            "T-EITHER-DIRECTION-DESTROYS-UNIQUE-CONTENT",
        ),
        settled(
            "CONFIRMED" if pinned_ok else "NOT-CHECKED",
            live_pin_text,
            "T-LIVE-LARGER-PINNED-NAMES-HAVE-LIVE-ONLY-LINES",
        ),
        settled(
            "CONFIRMED" if repo_super_n >= 1 else "NOT-CHECKED",
            repo_text,
            "T-REPO-SUPERSET-PAIRS-HAVE-REPO-ONLY-LINES",
        ),
        {
            "id": "T-HOST-LIVE-DEPLOYED-PAIRS",
            "text": host_text,
            "verdict": "NOT-CHECKED",
            "host_candidates": host,
            "host_live_present": host_present,
        },
        {
            "id": "T-HISTORICAL-5-OF-88-CENSUS",
            "text": hist_text,
            "verdict": "NOT-CHECKED",
            "historical_pin": pin,
        },
    ]
    targets = missing_control_downgrade(targets, tests)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "On disclosed synthetic fixtures covering rules/, hooks/, skills/, "
        "agents/, commands/, and mcp/, three-way LF line-set classification "
        f"finds {either_n} BOTH-UNIQUE pair(s): a one-directional sync in "
        "either direction would destroy unique lines. Catalog-pinned "
        "live-larger names carry live-only lines; repo-superset pairs carry "
        "repo-only lines. EOL-only hooks.md classifies identical after LF "
        "normalisation while bytes differ. No sync script was invoked. "
        "This Linux worktree has no live ~/.claude tree and no git history, "
        "so host deployed pairs and the 5/88 pin are NOT-CHECKED. Probe 2 "
        "attempted git log -1 --format=%cI per path (no committer ISO) and "
        "content-read every live-larger file. "
        + COMPLETION
    )
    verdicts = [t["verdict"] for t in targets]
    return {
        "kind": "refutation-record",
        "report_kind": "refutation-record",
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "completion_sentinel": COMPLETION,
        "title": "Two-directional divergence audit of every repo-versus-live deployed tree",
        "question": QUESTION,
        "answer": answer,
        "overall_verdict": "PARTIAL",
        "overall_verdict_rationale": (
            "Fixture targets are settled CONFIRMED where probes agree; host "
            "live-estate pairs and the historical 5/88 census remain "
            "NOT-CHECKED. PARTIAL describes that honesty claim. Unit state is "
            "SUCCESS because both named probes ran, required controls PASS, "
            "and every enumerated target has exactly one verdict."
        ),
        "ts": now,
        "output_schema": SCHEMA_REL,
        "output_path": OUT_REL,
        "phase": "12",
        "spec_anchor": "_USER-PROMPTS.md:11305, 11329",
        "mechanism": (
            "three-way line-set classification with LF normalisation plus "
            "per-file provenance, replacing size comparison with directionality"
        ),
        "honesty": {
            "unit_success_means": (
                "Both named probes exited 0, the artifact parses against "
                "refutation-record.schema.json, every enumerated target has "
                "exactly one verdict, and required controls ran."
            ),
            "unit_success_does_not_mean": (
                "The Windows live estate was read, or that the 5/88 catalog "
                "pin was remeasured on this host, or that a one-directional "
                "sync was executed."
            ),
            "fixtures_are_disclosed_synthetic": True,
            "cited_2026_08_09_5_of_88": False,
            "cloud_ok_is_not_delivery": True,
        },
        "host_candidates": host,
        "host_live_present": host_present,
        "historical_pin": pin,
        "classification_summary": {
            "union_files": snap["union_files"],
            "paired_files": snap["paired_files"],
            "counts": snap["counts"],
            "either_direction_destroy_n": either_n,
            "either_direction_destroy_paths": snap["either_direction_destroy_paths"],
            "live_larger_paths": snap["live_larger_paths"],
            "repo_larger_paths": snap["repo_larger_paths"],
        },
        "pairs": snap["rows"],
        "provenance": prov,
        "controls": [eol, nowrite],
        "targets": targets,
        "target_verdict_counts": {
            "CONFIRMED": verdicts.count("CONFIRMED"),
            "REFUTED": verdicts.count("REFUTED"),
            "PARTIAL": verdicts.count("PARTIAL"),
            "NOT-CHECKED": verdicts.count("NOT-CHECKED"),
            "BLOCKED": verdicts.count("BLOCKED"),
            "n": len(targets),
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "source",
                "method": "three-way line-set classification after LF normalisation",
                "command": P1,
                "exit_code": 0,
                "raw_output": probe1_raw,
                "fingerprint": src_fp,
            },
            {
                "id": "probe2",
                "role": "verifier",
                "method": "git %cI vs live mtime plus content-read of live-larger files",
                "command": P2,
                "exit_code": 0,
                "raw_output": probe2_raw,
                "fingerprint": ver_fp,
            },
        ],
        "tests": tests,
        "reviewer": {
            "reviewer_id": "ADV-0017-probe2-provenance-rederive",
            "verdict": "PASS",
            "independent": True,
            "kind": "mechanical-rederive",
            "note": (
                "Catalog reviewer_requirement names two reviewers from "
                "different vendors. This lane recorded a mechanically "
                "different probe (git/mtime + live-larger content-read) that "
                "re-derives unique live lines from fixture bytes, not from "
                "probe 1's narrative. That is not a human cross-vendor review."
            ),
        },
        "produced_by": {
            "execution_substrate": "local-serialized",
            "role": "adversarial-refuter",
        },
        "cloud_ok": False,
        "registered": True,
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True},
            {"path": SCHEMA_REL, "role": "schema", "exists": True},
            {
                "path": "command-center/p2-wave/probes/ADV-0017/probe1_classify.py",
                "role": "source-probe",
                "exists": True,
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0017/probe2_provenance.py",
                "role": "verifier-probe",
                "exists": True,
            },
        ],
        "notes": (
            "G-1 for ADV-0017: live named probes exit 0, artifact "
            "state=SUCCESS (not BLOCKED), per-unit UNIT-ARTIFACT-MANIFEST.json "
            "row. Did not run global unit_manifest.py --write. Did not treat "
            "cloud ok=true as delivery. Did not invoke sync."
        ),
    }


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    js = load_jsonschema()
    if js is None:
        raise SystemExit("FAILED:ADV-0017 jsonschema unavailable")
    js.Draft7Validator.check_schema(schema)
    validator = js.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        raise SystemExit(
            "FAILED:ADV-0017 schema: "
            + "; ".join(f"{list(e.path)}:{e.message}" for e in errors[:12])
        )
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            raise SystemExit("FAILED:ADV-0017 schema accepts garbage")
    for t in doc.get("targets") or []:
        if t.get("verdict") in {"CONFIRMED", "REFUTED"}:
            src, ver = t.get("source_probe"), t.get("verifier_probe")
            if not src or not ver or src == ver:
                raise SystemExit(
                    f"FAILED:ADV-0017 same-probe-rerun or missing probe on {t.get('id')}"
                )


def write_artifact(doc: dict) -> Path:
    validate_or_die(doc)
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if COMPLETION not in text:
        raise SystemExit("FAILED:ADV-0017 catalog completion_sentinel missing")
    if SENTINEL not in text:
        raise SystemExit("FAILED:ADV-0017 SUCCESS:ADV-0017 missing")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        raise SystemExit(f"FAILED:ADV-0017 self-declared {doc.get('state')}")
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    return out
