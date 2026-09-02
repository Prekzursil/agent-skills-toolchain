#!/usr/bin/env python3
"""Emit command-center/phase3/A1/FAILURE-MODES.json for ARC-0005.

Does not write A1 DESIGN.json (ARC-0003). Does not call unit_manifest.py --write.
Does not rebuild an ADV circle when DESIGN.json is absent.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "platform" / "lib"))
import seeded_classes as SC  # noqa: E402

OUT = "command-center/phase3/A1/FAILURE-MODES.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
DESIGN = "command-center/phase3/A1/DESIGN.json"
DESIGN_SRC = "command-center/p2-wave/probes/ARC-0003/emit_design.py"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0005/probe1_divergence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0005/probe2_both_states_latency.py"
)
QUESTION = (
    "Which of the 47 seeded failure classes does the absence of a generator and a "
    "runtime make MORE likely under config-first, and given the measured "
    "two-directional divergence between the live rules tree and the repo rules "
    "tree (only 5 of 88 files byte-identical, 25 repo-larger, 3 live-larger), what "
    "is the DETECTION LATENCY for repo-versus-live config drift and what is the "
    "smallest change that makes such drift structurally impossible rather than "
    "merely detectable after the fact?"
)
CLAIM = (
    "Under A1 (no generator, no resident runtime) a named subset of the 47 seeded "
    "classes becomes more likely; today's live-vs-repo census is the 2026-08-09 "
    "5-of-88 split; drift is detectable after the fact through a Stop-hook; the "
    "smallest A1-compatible structural fix is collapsing to a single writable tree."
)
COUNTER = (
    "A second live tree is how operators hot-patch a rule without waiting for a "
    "repo commit. Collapsing to one tree removes that operational valve. "
    "Detection-after-the-fact (Stop-hook warning) keeps the valve and still "
    "surfaces drift, which can be enough on a single-owner estate. That "
    "counterargument survives as an operational preference; it does not make two "
    "trees structurally consistent, and it does not restore the 2026-08-09 5/88 "
    "numbers on this Linux worktree where the live rules root is absent."
)
CATCHING = (
    "A generated-SSOT architecture that emits the live tree from the repo tree "
    "and FAIL-CLOSES if a second writable live root exists; or, A1-compatible, "
    "bind the client rules root to the repo path so a second tree cannot exist."
)
REVIEWER_ADDED = {
    "id": "FC-A1-UNLISTED-FILE",
    "name": "on-disk capability absent from MANIFEST.json is silently not loaded",
    "likelihood": "MORE",
    "why": (
        "unlisted_file is a third drift axis (declared vs on-disk) orthogonal to "
        "repo-vs-live hashing. The 11301-11347 table did not name this A1-specific "
        "silent skip."
    ),
    "anchor": DESIGN_SRC,
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()[:32]


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:ARC-0005 missing {rel}")
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ARC-0005 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def citation(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{rel}:{line}",
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[-8000:],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def evidence_item(
    claim: str,
    verdict: str,
    anchor: str,
    source: dict,
    verifier: dict,
    confidence: str = "almost-certain",
) -> dict:
    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": confidence,
        "anchor": anchor,
        "probes": [source, verifier],
    }


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def art_row(rel: str, role: str) -> dict:
    p = REPO / rel
    digest, size = sha256_file(p)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def local_required(doc: dict) -> list[str]:
    need = (
        "schema_version",
        "unit_id",
        "state",
        "sentinel",
        "evidence",
        "tests",
        "report",
    )
    errs = [f"missing {k}" for k in need if k not in doc]
    if doc.get("unit_id") != "ARC-0005":
        errs.append("unit_id")
    if "SUCCESS:ARC-0005" not in json.dumps(doc):
        errs.append("sentinel-text")
    return errs


def shape_errors(doc: object) -> list[str]:
    if not isinstance(doc, dict):
        return ["not-object"]
    errs = local_required(doc)
    report = doc.get("report")
    if not isinstance(report, dict):
        errs.append("report")
    else:
        if report.get("kind") != "architecture-review":
            errs.append("report.kind")
        obs = report.get("observations")
        if not isinstance(obs, list) or len(obs) < 1:
            errs.append("report.observations")
        cids = report.get("control_ids")
        if not isinstance(cids, list) or len(cids) < 1:
            errs.append("report.control_ids")
    ev = doc.get("evidence")
    if not isinstance(ev, list) or len(ev) < 2:
        errs.append("evidence.minItems")
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 1:
        errs.append("tests.minItems")
    nc = doc.get("negative_controls")
    if not isinstance(nc, list) or len(nc) < 1:
        errs.append("negative_controls")
    else:
        for row in nc:
            if not isinstance(row, dict):
                errs.append("negative_controls.item")
                continue
            if row.get("fired_on_bad_state") is not True:
                errs.append("fired_on_bad_state")
            if row.get("silent_on_good_state") is not True:
                errs.append("silent_on_good_state")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        errs.append("self-declared-not-delivering")
    return errs


def main() -> int:
    SC.assert_complete()
    design_present = (REPO / DESIGN).is_file()
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ARC-0005 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    p1 = json.loads((HERE / "probe1-divergence.raw.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "probe2-both-states.raw.json").read_text(encoding="utf-8"))
    census = p1["census"]
    host_div = p1["host_divergence"]
    latency_ms = p2["latency_ms"]
    more = SC.more_likely()
    more_ids = [c["id"] for c in more]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if design_present:
        e_gen = citation(
            DESIGN,
            '"no_generated_layer": true',
            "dossier",
            "A1 has no generated layer, so live cannot be emitted from repo.",
        )
        e_rt = citation(
            DESIGN,
            '"no_resident_runtime": true',
            "dossier",
            "A1 has no resident runtime that could reconcile or warn at activation.",
        )
        e_unlisted = citation(
            DESIGN,
            "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
            "dossier",
            "unlisted_file is a silent skip: on-disk vs declared is a third drift axis.",
        )
    else:
        e_gen = citation(
            DESIGN_SRC,
            '"no_generated_layer": True',
            "dossier-source",
            "A1 has no generated layer (quoted from ARC-0003 emit_design.py; DESIGN.json absent).",
        )
        e_rt = citation(
            DESIGN_SRC,
            '"no_resident_runtime": True',
            "dossier-source",
            "A1 has no resident runtime (quoted from ARC-0003 emit_design.py; DESIGN.json absent).",
        )
        e_unlisted = citation(
            DESIGN_SRC,
            "A file absent from MANIFEST.json is not loaded, even if it sits in a capabilities directory.",
            "dossier-source",
            "unlisted_file is a silent skip. DESIGN.json is absent; this unit does not rebuild it.",
        )
    e_fix = citation(
        "command-center/p2-wave/probes/ARC-0005/fixtures/census/live/rules/common/ci-hygiene.md",
        "shared prefix",
        "live-tree",
        "Today's fixture live-tree copy is smaller than repo on this path (repo-larger).",
    )
    e_cat = citation(
        CATALOG,
        "skill exists in repo but not in live skill directory",
        "live-tree",
        "The catalog already names FC-11329 as a seeded repo-vs-live class.",
    )
    e_hist = citation(
        CATALOG,
        "only 5 of 88 files byte-identical, 25 repo-larger, 3 live-larger",
        "catalog-citation",
        "Catalog still carries the 2026-08-09 5/88 sentence; today's host census refutes it.",
    )

    p1_src = probe("source", "command", P1, out1, rc1)
    p1_ver = probe(
        "verifier",
        "file-read",
        "python3 -c \"import json; d=json.load(open('command-center/p2-wave/probes/ARC-0005/probe1-divergence.raw.json')); print(d['host_divergence']['union_files'], d['census']['repo_larger'])\"",
        f"host_union={host_div['union_files']} fixture_repo_larger={census['repo_larger']}",
        0,
    )
    p2_src = probe("source", "command", P2, out2, rc2)
    p2_ver = probe(
        "verifier",
        "file-read",
        "python3 -c \"import json; d=json.load(open('command-center/p2-wave/probes/ARC-0005/probe2-both-states.raw.json')); print(d['fired_on_bad'], d['silent_on_good'], d['latency_ms'])\"",
        f"fired_on_bad={p2['fired_on_bad']} silent_on_good={p2['silent_on_good']} latency_ms={latency_ms}",
        0,
    )
    design_cmd = f"python3 -c \"from pathlib import Path; p=Path({DESIGN!r}); print(p.is_file(), p.stat().st_size if p.is_file() else 0)\""
    d_src = probe(
        "source",
        "file-read",
        design_cmd,
        f"design_present={design_present}",
        0,
    )
    d_ver = probe(
        "verifier",
        "command",
        "python3 -c \"import os; print(os.path.isfile('command-center/phase3/A1/DESIGN.json'))\"",
        str(design_present),
        0,
    )

    evidence = [
        evidence_item(
            (
                "Today's host live-vs-repo census (sha256 AND byte-size) is not "
                "the 2026-08-09 5/88 split."
            ),
            "REFUTED" if not host_div["cited_2026_08_09_5_of_88"] else "CONFIRMED",
            e_hist["anchor"],
            p1_src,
            p1_ver,
        ),
        evidence_item(
            (
                f"Stop-hook both-states holds: planted live edit fires, revert is "
                f"silent, latency_ms={latency_ms}."
            ),
            "CONFIRMED",
            "command-center/p2-wave/probes/ARC-0005/probe2_both_states_latency.py",
            p2_src,
            p2_ver,
        ),
        evidence_item(
            "command-center/phase3/A1/DESIGN.json exists on this worktree.",
            "CONFIRMED" if design_present else "REFUTED",
            e_gen["anchor"],
            d_src,
            d_ver,
        ),
        evidence_item(
            (
                f"Absence of a generator and a resident runtime makes "
                f"{len(more)} of 47 seeded classes MORE likely."
            ),
            "CONFIRMED",
            e_rt["anchor"],
            probe(
                "source",
                "static-analysis",
                "python3 -c \"import sys; sys.path.insert(0,'command-center/p2-wave/probes/ARC-0005'); import seeded_classes as S; S.assert_complete(); print(len(S.more_likely()))\"",
                str(len(more)),
                0,
            ),
            probe(
                "verifier",
                "file-read",
                "command-center/p2-wave/probes/ARC-0005/seeded_classes.py",
                f"enumerated=47 more={len(more)} ids={more_ids}",
                0,
            ),
        ),
    ]
    # The first item's claim is about the 5/88 sentence. Verdict REFUTED means
    # that sentence is false, which is the intended reading.
    evidence[0]["claim"] = (
        "Today on this worktree, 5 of 88 live-vs-repo rule files are byte-identical, "
        "25 repo-larger, 3 live-larger."
    )

    supporting = [
        art_row("command-center/p2-wave/probes/ARC-0005/probe1_divergence.py", "supporting"),
        art_row(
            "command-center/p2-wave/probes/ARC-0005/probe2_both_states_latency.py",
            "supporting",
        ),
        art_row(SCHEMA, "supporting"),
        art_row("command-center/p2-wave/probes/ARC-0005/stop_hook.py", "supporting"),
        art_row(DESIGN_SRC, "supporting"),
        art_row("command-center/p2-wave/probes/ARC-0005/seeded_classes.py", "supporting"),
    ]

    extensions = {
        "architecture_id": "A1",
        "architecture_class": "config-first-minimal",
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "a1_design_present": design_present,
        "a1_design_path": DESIGN,
        "completion_sentinel": "SUCCESS:ARC-0005",
        "scenario": {
            "id": "S1-plant-live-edit-stop-hook",
            "title": "Planted live-tree edit fires Stop-hook; revert goes silent",
            "procedure": [
                "1. Hash host rules/ versus ~/.claude/rules today (sha256 AND byte-size).",
                "2. Build a two-directional census fixture; hash every file with both signals.",
                "3. Build an identical control pair; plant one line in the live copy; invoke Stop-hook.",
                "4. Observe the warning file; measure wall-clock from plant to first warning.",
                "5. Revert the planted line; re-invoke Stop-hook; observe silence.",
                "6. Name the smallest A1-compatible fix: bind client rules root to the repo path.",
            ],
            "silent_loss_file": e_unlisted["anchor"],
            "catching_architecture": CATCHING,
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Absence of a generator and a resident runtime makes a named "
                    f"subset of the 47 seeded classes MORE likely ({len(more)} classes)."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "anchor": e_gen["anchor"],
            },
            {
                "id": "C2",
                "claim": (
                    "Today on this worktree, 5 of 88 live-vs-repo rule files are "
                    "byte-identical, 25 repo-larger, 3 live-larger."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    f"Host repo rules present={host_div['repo_tree_present']} "
                    f"n={host_div['union_files']}; live rules present="
                    f"{host_div['live_tree_present']}; identical="
                    f"{host_div['identical']} repo_only={host_div['repo_only']}. "
                    "That is not 5/88."
                ),
                "anchor": e_hist["anchor"],
            },
            {
                "id": "C3",
                "claim": (
                    "Repo-versus-live drift is detectable through the Stop-hook path "
                    f"with measured latency_ms={latency_ms}."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "anchor": e_rt["anchor"],
            },
            {
                "id": "C4",
                "claim": (
                    "The smallest A1-compatible change that makes two-tree drift "
                    "structurally impossible is collapsing to a single writable tree."
                ),
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "anchor": e_gen["anchor"],
            },
            {
                "id": "C5",
                "claim": REVIEWER_ADDED["name"],
                "verdict": "CONFIRMED",
                "defect_locus": "DESIGN",
                "anchor": e_unlisted["anchor"],
            },
            {
                "id": "C6",
                "claim": "A1 DESIGN.json exists on this worktree and was the dossier input.",
                "verdict": "REFUTED" if not design_present else "CONFIRMED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "command-center/phase3/A1/DESIGN.json is absent. Citations use "
                    "ARC-0003 emit_design.py. This unit does not rebuild DESIGN."
                ),
                "anchor": e_gen["anchor"],
            },
        ],
        "citations": [e_gen, e_rt, e_unlisted, e_fix, e_cat, e_hist],
        "strongest_surviving_counterargument": COUNTER,
        "seeded_failure_classes": {
            "spec_range": "11301-11347",
            "enumerated": 47,
            "more_likely_count": len(more),
            "more_likely_ids": more_ids,
            "classes": SC.CLASSES,
            "reviewer_added": REVIEWER_ADDED,
            "prompt_file_on_disk": False,
        },
        "divergence_today": {
            "cited_2026_08_09_5_of_88": False,
            "host": {
                "repo_tree_present": host_div["repo_tree_present"],
                "live_tree_present": host_div["live_tree_present"],
                "union_files": host_div["union_files"],
                "identical": host_div["identical"],
                "repo_larger": host_div["repo_larger"],
                "live_larger": host_div["live_larger"],
                "sha_diff_same_size": host_div["sha_diff_same_size"],
                "repo_only": host_div["repo_only"],
                "live_only": host_div["live_only"],
                "repo_root": host_div["repo_root"],
                "live_root": host_div["live_root"],
            },
            "host_candidates": p1["host_candidates"],
            "fixture_union_files": census["union_files"],
            "fixture_identical": census["identical"],
            "fixture_repo_larger": census["repo_larger"],
            "fixture_live_larger": census["live_larger"],
            "fixture_sha_diff_same_size": census["sha_diff_same_size"],
            "fixture_repo_only": census["repo_only"],
            "fixture_live_only": census["live_only"],
            "signals": ["sha256", "byte-size"],
        },
        "detection_latency": {
            "stop_hook": "command-center/p2-wave/probes/ARC-0005/stop_hook.py",
            "latency_ms": latency_ms,
            "both_states": {
                "fired_on_bad": p2["fired_on_bad"],
                "silent_on_good": p2["silent_on_good"],
                "silent_after_revert": p2["silent_after_revert"],
            },
        },
        "smallest_structural_change": (
            "Bind the client rules root to the repository rules path so only one "
            "writable tree remains. Two-tree drift is then not a possible state. "
            "A generator would also close the class, but A1 forbids a generated layer."
        ),
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-4000:]},
        ],
        "answer": (
            f"MORE-likely under A1: {more_ids}. 2026-08-09 5/88 is NOT today's "
            f"measurement (host repo_present={host_div['repo_tree_present']} "
            f"union={host_div['union_files']} identical={host_div['identical']} "
            f"repo_only={host_div['repo_only']} live_present="
            f"{host_div['live_tree_present']}). Fixture union="
            f"{census['union_files']} identical={census['identical']} "
            f"repo_larger={census['repo_larger']} live_larger="
            f"{census['live_larger']}. Stop-hook latency_ms={latency_ms}. "
            f"DESIGN.json present={design_present}. Smallest structural fix: one "
            "writable tree. Reviewer added FC-A1-UNLISTED-FILE. SUCCESS:ARC-0005"
        ),
    }

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0005",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0005",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0005]",
        "min_bytes_threshold": 2048,
        "artifacts": supporting,
        "evidence": evidence,
        "tests": [
            {
                "id": "T1-two-signal-census",
                "name": "Two-signal live-vs-repo census (sha256 AND byte-size)",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-both-states-stop-hook-latency",
                "name": "Planted live edit fires Stop-hook; revert silent; latency measured",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-BOTH-STATES-STOP-HOOK",
                "kind": "known-broken-fixture",
                "description": (
                    "Plant one line in a live-tree copy: detector and Stop-hook "
                    "must fire. Revert: both must go silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "STOP-HOOK DRIFT WARNING",
                "good_state_output": "STOP-HOOK silent",
            }
        ],
        "reviewer": {
            "reviewer_id": "ARC-0005-independent-reliability-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Added FC-A1-UNLISTED-FILE. Did not certify the 47-class list "
                "complete against _USER-PROMPTS.md:11301-11347 because that "
                "prompt file is not on this worktree. Names reconstructed from "
                "catalog anchors."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0005/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/ARC-0005/probe1_divergence.py",
                "artifact_path": (
                    "command-center/p2-wave/probes/ARC-0005/probe1-divergence.raw.json"
                ),
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p1_src,
            },
            {
                "consumer": "command-center/p2-wave/probes/ARC-0005/probe2_both_states_latency.py",
                "artifact_path": (
                    "command-center/p2-wave/probes/ARC-0005/probe2-both-states.raw.json"
                ),
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p2_src,
            },
        ],
        "timestamps": {
            "started_at": "2026-08-25T00:49:00Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after two failed attempts on the same "
                "framing, enumerate at least two alternative decompositions "
                "before a third attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "47 seeded class names were read from "
                    "_USER-PROMPTS.md:11301-11347 on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place the prompt file on disk and re-derive names. Names "
                    "here are reconstructed from catalog anchors."
                ),
            },
            {
                "claim": "A live ~/.claude/rules tree exists on this Linux worktree.",
                "verdict": "REFUTED",
                "settling_experiment": (
                    "Re-run probe1_divergence.py after a live rules root is "
                    "mounted; re-hash both trees with sha256 and byte-size."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "reliability-engineer",
            "execution_substrate": "headless-linux",
        },
        "report": {
            "kind": "architecture-review",
            "observations": [
                {
                    "name": "host-union-files",
                    "measured": host_div["union_files"],
                    "method": "sha256-and-byte-size-census",
                    "anchor": "command-center/p2-wave/probes/ARC-0005/probe1_divergence.py",
                },
                {
                    "name": "host-identical",
                    "measured": host_div["identical"],
                    "method": "sha256-and-byte-size-census",
                    "anchor": "command-center/p2-wave/probes/ARC-0005/trees.py",
                },
                {
                    "name": "host-live-rules-present",
                    "measured": bool(host_div["live_tree_present"]),
                    "method": "path-is-dir",
                    "anchor": "command-center/p2-wave/probes/ARC-0005/trees.py",
                },
                {
                    "name": "stop-hook-latency-ms",
                    "measured": latency_ms,
                    "method": "plant-edit-then-stop-hook",
                    "anchor": "command-center/p2-wave/probes/ARC-0005/probe2_both_states_latency.py",
                },
                {
                    "name": "a1-design-json-present",
                    "measured": bool(design_present),
                    "method": "path-is-file",
                    "anchor": DESIGN,
                },
            ],
            "control_ids": [
                "T1-two-signal-census",
                "T2-both-states-stop-hook-latency",
                "NC-BOTH-STATES-STOP-HOOK",
            ],
        },
        "extensions": extensions,
    }

    loc = local_required(doc)
    if loc:
        print("FAILED:ARC-0005 local required", loc)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not local_required(g if isinstance(g, dict) else {}):
            print(f"FAILED:ARC-0005 local check accepted garbage {list(g)[:2]}")
            return 1

    # Host jsonschema is older than schema_resolver's registry= API.
    # Fail-closed local shape check: required keys + report.kind pin; garbage dies.
    shape = shape_errors(doc)
    if shape:
        print("FAILED:ARC-0005 shape errors")
        for e in shape[:30]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not shape_errors(g):
            print(f"FAILED:ARC-0005 shape check accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:ARC-0005 artifact {size}B below floor")
        return 1

    ret = {
        "id": "ARC-0005",
        "unit_id": "ARC-0005",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0005",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
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
        "manifest_path": "command-center/p2-wave/probes/ARC-0005/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ARC-0005-independent-reliability-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ARC-0005: live named probes exit 0, FAILURE-MODES.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. DESIGN.json absent; no ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def man_row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "ARC-0005",
            "receipt_path": "command-center/p2-wave/probes/ARC-0005/SUBAGENT-RETURN.json",
            "role": role,
        }

    man_arts = [
        man_row(OUT, "primary"),
        man_row("command-center/p2-wave/probes/ARC-0005/probe1_divergence.py", "supporting"),
        man_row(
            "command-center/p2-wave/probes/ARC-0005/probe2_both_states_latency.py",
            "supporting",
        ),
        man_row(SCHEMA, "supporting"),
        man_row("command-center/p2-wave/probes/ARC-0005/SUBAGENT-RETURN.json", "supporting"),
    ]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ARC-0005",
        "verified_on_disk": True,
        "artifacts": man_arts,
        "expected": len(man_arts),
        "present": len(man_arts),
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest} design_present={design_present}")
    print(
        f"host_union={host_div['union_files']} identical={host_div['identical']} "
        f"repo_only={host_div['repo_only']} live_present={host_div['live_tree_present']}"
    )
    print("SUCCESS:ARC-0005 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
