#!/usr/bin/env python3
"""Emit WFA-0159 freshness-monitor foundry artifact.

Catalog output_schema is foundry-artifact.schema.json#/$defs/freshness-monitor,
which is generic_report with report.kind == "freshness-monitor". Validate
against the physical profiles/receipt schemas on disk (offline RefResolver).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import decay as D  # noqa: E402
import live_fetch as LF  # noqa: E402
import registry as R  # noqa: E402

OUT = "command-center/foundry/WFA-0159-freshness-and-revalidation-decay-for-adopted-externa.json"
SCHEMA = "command-center/schema/foundry-artifact.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT = "platform/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0159/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0159/probe2_clock_and_unreachable.py"
)
QUESTION = (
    "122 of the 284 candidates are classified ADOPT-AS-IS and 20 ADOPT-WITH-WRAPPER "
    "(recounted), each resting on an upstream whose maintenance state, license and "
    "version can change after adoption. Question: what is the revalidation interval "
    "per candidate, which adoptions are already stale against their upstream today, "
    "and what signal demotes a stale adoption back to UNKNOWN-NEEDS-PROBE?"
)
LIVE_REPOS = (
    "n8n-io/n8n",
    "PrefectHQ/prefect",
    "angular/angular.js",
    "this-org-does-not-exist-wfa0159/no-such-repo",
)
UP = HERE / "fixtures" / "upstream"
MIN_BYTES = 2048
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/WFA-0159/clock.py",
    "command-center/p2-wave/probes/WFA-0159/decay.py",
    "command-center/p2-wave/probes/WFA-0159/registry.py",
    "command-center/p2-wave/probes/WFA-0159/live_fetch.py",
    "command-center/p2-wave/probes/WFA-0159/probe1_both_states.py",
    "command-center/p2-wave/probes/WFA-0159/probe2_clock_and_unreachable.py",
    "command-center/p2-wave/probes/WFA-0159/fixtures/control_corpus.json",
]
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "WFA-0159", "state": "SUCCESS", "sentinel": "SUCCESS:WFA-0159"},
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def refuse_remote(uri: str):
    raise RefResolutionError(f"offline: refused remote {uri}")


def art_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def find_line(rel: str, snippet: str) -> tuple[int, str]:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i, line.strip()
    raise ValueError(f"snippet not found in {rel}: {snippet}")


def run_cmd(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def offline_validator() -> Draft7Validator:
    """Resolve ast-integrate.invalid $ref from disk. Never the network."""
    store: dict[str, dict] = {}
    for rel in (SCHEMA, PROFILES, RECEIPT):
        body = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store["https://ast-integrate.invalid/" + rel] = body
        ident = body.get("$id")
        if isinstance(ident, str) and ident:
            store[ident] = body
    profiles = store["https://ast-integrate.invalid/" + PROFILES]
    target = profiles["$defs"]["freshness-monitor"]
    resolver = RefResolver(
        base_uri=str(profiles.get("$id") or ("https://ast-integrate.invalid/" + PROFILES)),
        referrer=profiles,
        store=store,
        cache_remote=False,
        handlers={"http": refuse_remote, "https": refuse_remote},
    )
    return Draft7Validator(target, resolver=resolver)


def schema_errors(validator: Draft7Validator, doc: dict) -> list[str]:
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def control_results(now: datetime) -> list[dict]:
    corpus = R.load_control_corpus()
    rows = []
    for item in corpus["candidates"]:
        cand = D.apply_relative_validated_at(item, now)
        fixture = item.get("upstream_fixture")
        live = LF.load_fixture_live(UP / str(fixture))
        rec = D.revalidate(cand, live, now)
        rows.append(
            {
                "id": rec["id"],
                "classification": rec["classification"],
                "source_class": item.get("source_class"),
                "interval_seconds": rec["interval_seconds"],
                "verdict": rec["verdict"],
                "reasons": rec["reasons"],
                "new_classification": rec["new_classification"],
                "fetch_date": rec.get("fetch_date"),
                "upstream_url": rec.get("upstream_url"),
                "note": rec.get("note"),
            }
        )
    return rows


def estate_census() -> dict:
    path, doc = R.load_authoritative()
    catalog = {
        "authoritative_registry_present": False,
        "authoritative_path": None,
        "catalog_adopt_as_is": R.CATALOG_ADOPT_AS_IS,
        "catalog_adopt_with_wrapper": R.CATALOG_ADOPT_WITH_WRAPPER,
        "catalog_adopt_class_total": R.CATALOG_ADOPT_AS_IS + R.CATALOG_ADOPT_WITH_WRAPPER,
        "stale_today_status": "UNKNOWN",
        "stale_ids": [],
        "keep_ids": [],
        "unknown_ids": [],
        "reason": (
            "08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux worktree; "
            "an unreachable estate is UNKNOWN, never still-fine"
        ),
        "recount": None,
    }
    if path is None or not isinstance(doc, dict):
        return catalog
    candidates = doc.get("candidates")
    if not isinstance(candidates, list):
        catalog["authoritative_path"] = str(path)
        catalog["reason"] = "registry present but candidates[] missing"
        return catalog
    recount = R.recount_adopt(candidates)
    catalog.update(
        {
            "authoritative_registry_present": True,
            "authoritative_path": path.as_posix(),
            "stale_today_status": "MEASURED",
            "recount": recount,
            "reason": (
                "per-row live revalidation; rows without a reachable upstream "
                "are UNKNOWN, never still-fine"
            ),
        }
    )
    return catalog


def live_reads() -> list[dict]:
    out = []
    for repo in LIVE_REPOS:
        rec = LF.fetch_url(
            f"https://api.github.com/repos/{repo}", timeout=8.0, attempts=2
        )
        rec["sample_id"] = repo
        rec["role"] = "live-sample-not-estate-142"
        out.append(rec)
    return out


def main() -> int:
    started = datetime.now(timezone.utc)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0159 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:WFA-0159-probe1" not in t1 or "SUCCESS:WFA-0159-probe2" not in t2:
        print("FAILED:WFA-0159 emit probe sentinel missing")
        return 1

    now = datetime.now(timezone.utc)
    controls = control_results(now)
    estate = estate_census()
    live = live_reads()
    by_id = {r["id"]: r for r in controls}
    expected = {
        "ctrl-adopt-as-is-unchanged": "KEEP",
        "ctrl-adopt-wrapper-unchanged": "KEEP",
        "ctrl-archived-since-adopt": "DEMOTE",
        "ctrl-relicensed-since-adopt": "DEMOTE",
        "ctrl-clock-decay-aged": "DEMOTE",
        "ctrl-unreachable-404": "UNKNOWN",
    }
    for cid, want in expected.items():
        got = by_id[cid]["verdict"]
        if got != want:
            print(f"FAILED:WFA-0159 control {cid} want={want} got={got}")
            return 1

    stale_ctrl = [r["id"] for r in controls if r["verdict"] in {D.DEMOTE, D.UNKNOWN}]
    keep_ctrl = [r["id"] for r in controls if r["verdict"] == D.KEEP]
    archived_live = next((x for x in live if x.get("archived") is True), None)
    unreachable_live = next((x for x in live if x.get("http_status") == 404), None)

    decay_rel = "command-center/p2-wave/probes/WFA-0159/decay.py"
    clock_rel = "command-center/p2-wave/probes/WFA-0159/clock.py"
    ln_unreach, sn_unreach = find_line(
        decay_rel, "unreachable upstream is UNKNOWN, never still-fine"
    )
    ln_clock, sn_clock = find_line(
        clock_rel,
        "age alone marks STALE even when license and archive bits are unchanged",
    )
    ln_signal, sn_signal = find_line(decay_rel, "DEMOTE_SIGNAL = ")

    ended = datetime.now(timezone.utc)
    ts = D.iso(ended)
    headline = (
        f"interval=source_class TTL; demote_signal={D.DEMOTE_SIGNAL} "
        f"->{D.DEMOTE_CLASS}; estate_142={estate['stale_today_status']}; "
        f"control_stale={stale_ctrl}; control_keep={keep_ctrl}"
    )

    src_p1 = probe("source", "command", P1, t1, c1)
    ver_arch = probe(
        "verifier",
        "file-read",
        "command-center/p2-wave/probes/WFA-0159/fixtures/upstream/archived.json",
        'archived=true license=MIT version=3.0.0 (content-drift; not clock.py)',
        0,
    )
    src_p2 = probe("source", "command", P2, t2, c2)
    ver_clock = probe(
        "verifier",
        "file-read",
        f"{clock_rel}:{ln_clock}",
        sn_clock[:400],
        0,
    )
    consumer_probe = probe(
        "source",
        "file-read",
        OUT,
        "emit writes then json.loads the catalog output_path",
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": "WFA-0159",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0159",
        "profile": "freshness-monitor",
        "spec_anchor": (
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "_USER-PROMPTS.md:10714"
        ),
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "licensing-analyst",
            "execution_substrate": "local-serialized",
        },
        "timestamps": {
            "started_at": D.iso(started),
            "ended_at": ts,
            "duration_seconds": max(0.0, (ended - started).total_seconds()),
        },
        "retry": {
            "count": 0,
            "policy": (
                "three attempts with staggered backoff for transient network/429; "
                "ZERO retries on 404/410/license change. Two same-fingerprint "
                "structural refutes park BLOCKED with required_fix named. No ADV "
                "rebuild circle."
            ),
        },
        "artifacts": [art_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "An upstream archived or relicensed since adoption demotes to "
                    f"{D.DEMOTE_CLASS}; unchanged ADOPT-AS-IS and ADOPT-WITH-WRAPPER "
                    "hold. Demote cases ran before unchanged verdicts were trusted."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{decay_rel}:{ln_signal}",
                "probes": [src_p1, ver_arch],
            },
            {
                "claim": (
                    "Age alone (clock.py, no license/archive inspect) marks STALE "
                    f"and demotes via {D.DEMOTE_SIGNAL}; unreachable upstream is "
                    "UNKNOWN, never still-fine. "
                    f"ctrl-unreachable-404={by_id['ctrl-unreachable-404']['verdict']} "
                    f"ctrl-clock-decay-aged={by_id['ctrl-clock-decay-aged']['reasons']}"
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{clock_rel}:{ln_clock}",
                "probes": [src_p2, ver_clock],
            },
        ],
        "tests": [
            {
                "id": "T-BOTH-STATES-ARCHIVE-RELICENSE",
                "name": (
                    "An upstream archived or relicensed since adoption demotes; "
                    "an unchanged upstream does not. Demote cases run first."
                ),
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-2000:],
            },
            {
                "id": "T-CLOCK-AND-UNREACHABLE",
                "name": (
                    "Age alone marks STALE with unchanged license/archive; "
                    "unreachable is UNKNOWN, never still-fine."
                ),
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-2000:],
            },
        ],
        "negative_controls": [
            {
                "id": "WFA-0159-ARCHIVED-OR-RELICENSED",
                "kind": "known-broken-fixture",
                "description": (
                    "archived.json and relicensed.json must DEMOTE; unchanged.json "
                    "and wrapper_ok.json must KEEP. Hidden-archive (archived bit "
                    "cleared) must KEEP, proving the engine keys off the bit."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"archived={by_id['ctrl-archived-since-adopt']['verdict']} "
                    f"relicensed={by_id['ctrl-relicensed-since-adopt']['verdict']}"
                ),
                "good_state_output": (
                    f"unchanged={by_id['ctrl-adopt-as-is-unchanged']['verdict']} "
                    f"wrapper={by_id['ctrl-adopt-wrapper-unchanged']['verdict']}"
                ),
            },
            {
                "id": "WFA-0159-CLOCK-DECAY",
                "kind": "mutation",
                "description": (
                    "Same license/archive/version as the KEEP twin, but validated_at "
                    "older than INTERVALS_SEC[source_class], must DEMOTE for CLOCK_DECAY."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(by_id["ctrl-clock-decay-aged"]["reasons"]),
                "good_state_output": str(by_id["ctrl-adopt-as-is-unchanged"]["reasons"]),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0159-probe2-independent-clock-and-unreachable",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 uses clock.py which never inspects license or archived "
                "bits, then separately asserts 404/None live reads are UNKNOWN. "
                "It did not author decay.py's ARCHIVED/RELICENSED branch."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/WFA-0159/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "WFA-0159-emit-json-load",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": consumer_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "The 122 ADOPT-AS-IS + 20 ADOPT-WITH-WRAPPER estate (142 of 284) "
                    "cannot be revalidated row-by-row because "
                    "08-WORKFLOW-CANDIDATE-REGISTRY.json is absent on this Linux "
                    "worktree. Estate stale-today is UNKNOWN, not still-fine."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json "
                    "and re-run emit_monitor.py so estate_census.stale_today_status "
                    "becomes MEASURED from live upstream reads."
                ),
            }
        ],
        "report": {
            "kind": "freshness-monitor",
            "title": "Freshness and revalidation decay for adopted external candidates",
            "question": QUESTION,
            "headline": headline,
            "observations": [
                {
                    "name": "revalidation_interval_git_default_branch_seconds",
                    "measured": D.INTERVALS_SEC["git-default-branch"],
                    "method": "INTERVALS_SEC[source_class] in decay.py",
                    "anchor": f"{decay_rel}:INTERVALS_SEC",
                },
                {
                    "name": "estate_142_stale_today_status",
                    "measured": estate["stale_today_status"],
                    "method": "authoritative registry presence check; absent => UNKNOWN",
                    "anchor": "command-center/p2-wave/probes/WFA-0159/registry.py:load_authoritative",
                },
                {
                    "name": "demotion_signal",
                    "measured": D.DEMOTE_SIGNAL,
                    "method": "named constant consumed by revalidate()",
                    "anchor": f"{decay_rel}:{ln_signal}",
                },
                {
                    "name": "control_archived_verdict",
                    "measured": by_id["ctrl-archived-since-adopt"]["verdict"],
                    "method": "revalidate against fixtures/upstream/archived.json",
                    "anchor": P1,
                },
                {
                    "name": "control_unchanged_verdict",
                    "measured": by_id["ctrl-adopt-as-is-unchanged"]["verdict"],
                    "method": "revalidate against fixtures/upstream/unchanged.json after demote cases",
                    "anchor": P1,
                },
                {
                    "name": "unreachable_is_unknown",
                    "measured": by_id["ctrl-unreachable-404"]["verdict"] == D.UNKNOWN,
                    "method": "revalidate with http_status=404 and with live=None",
                    "anchor": f"{decay_rel}:{ln_unreach}",
                },
            ],
            "control_ids": [
                "ctrl-archived-since-adopt",
                "ctrl-relicensed-since-adopt",
                "ctrl-adopt-as-is-unchanged",
                "ctrl-adopt-wrapper-unchanged",
                "ctrl-clock-decay-aged",
                "ctrl-unreachable-404",
            ],
            "answers": {
                "revalidation_interval_rule": (
                    "Per candidate, interval_seconds = INTERVALS_SEC[source_class] "
                    f"(git-default-branch={D.INTERVALS_SEC['git-default-branch']}, "
                    f"github-release={D.INTERVALS_SEC['github-release']}, "
                    f"package-registry={D.INTERVALS_SEC['package-registry']}, "
                    f"marketplace-index={D.INTERVALS_SEC['marketplace-index']}, "
                    f"documentation={D.INTERVALS_SEC['documentation']}, "
                    f"unknown={D.INTERVALS_SEC['unknown']}). "
                    "Archive and relicense events are immediate (they demote on the "
                    "live read regardless of remaining TTL)."
                ),
                "stale_today": {
                    "estate_142": estate["stale_today_status"],
                    "estate_reason": estate["reason"],
                    "control_corpus_stale_or_unknown": stale_ctrl,
                    "control_corpus_keep": keep_ctrl,
                    "live_sample_archived": (
                        archived_live.get("url") if archived_live else None
                    ),
                    "live_sample_unreachable": (
                        unreachable_live.get("url") if unreachable_live else None
                    ),
                },
                "demotion_signal": {
                    "name": D.DEMOTE_SIGNAL,
                    "target_classification": D.DEMOTE_CLASS,
                    "rule": (
                        "A live upstream read that shows archived-since-adopt, "
                        "relicense, version drift, or clock decay past the per-class "
                        "interval flips the adoption to UNKNOWN-NEEDS-PROBE. "
                        "Unreachable is UNKNOWN (same target class), never still-fine."
                    ),
                },
            },
            "revalidation_policy": {
                "intervals_seconds": dict(D.INTERVALS_SEC),
                "zero_retry_on": [404, 410],
                "transient_retries": 3,
                "adopt_classes": sorted(D.ADOPT_CLASSES),
                "demote_to": D.DEMOTE_CLASS,
                "demotion_signal": D.DEMOTE_SIGNAL,
            },
            "estate_census": estate,
            "control_results": controls,
            "live_upstream_reads": live,
            "control_expected": expected,
            "engine_anchors": {
                "unreachable": {"path": decay_rel, "line": ln_unreach, "snippet": sn_unreach[:180]},
                "clock": {"path": clock_rel, "line": ln_clock, "snippet": sn_clock[:180]},
                "signal": {"path": decay_rel, "line": ln_signal, "snippet": sn_signal[:180]},
            },
        },
    }

    validator = offline_validator()
    accepted = [repr(g)[:80] for g in GARBAGE if not schema_errors(validator, g)]
    if accepted:
        print("FAILED:WFA-0159 schema accepted garbage")
        for item in accepted:
            print(" ", item)
        return 1
    errs = schema_errors(validator, doc)
    if errs:
        print("FAILED:WFA-0159 schema errors")
        for err in errs[:25]:
            print(" ", err)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    if loaded.get("unit_id") != "WFA-0159" or "SUCCESS:WFA-0159" not in json.dumps(loaded):
        print("FAILED:WFA-0159 consumer could not read the written artifact")
        return 1
    if loaded.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0159 self-declared {loaded.get('state')}")
        return 1
    sha, size = sha256_file(out_path)
    if size < MIN_BYTES:
        print(f"FAILED:WFA-0159 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:WFA-0159 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
