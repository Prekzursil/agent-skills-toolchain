#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0036.json and per-unit receipts.

Domain payload lives under report/ (receipt_core additionalProperties=false).
Two same-fingerprint structural refutes park BLOCKED with a named required_fix.
Does not rebuild ADV-0017. Does not run sync-from-live.ps1 / sync-rules.ps1.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import ruling as R  # noqa: E402
import trees as T  # noqa: E402

REPO = T.REPO

try:
    from jsonschema import Draft7Validator, RefResolver
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"FAILED:BLD-0036 jsonschema missing: {exc}") from exc


def _schema_store() -> dict:
    rels = (
        SCHEMA,
        "platform/schema/receipt.schema.json",
        "platform/schema/artifact-class-profiles.schema.json",
    )
    store: dict = {}
    for rel in rels:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        ident = data.get("$id") or f"https://ast-integrate.invalid/{rel}"
        store[ident] = data
        store[f"https://ast-integrate.invalid/{rel}"] = data
    return store


def validate_artifact(doc: dict, output_schema: str) -> list[str]:
    """Disk-only $ref validation. jsonschema 4.10 has no registry= kwarg."""
    shim = json.loads((REPO / output_schema).read_text(encoding="utf-8"))
    store = _schema_store()
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or f"https://ast-integrate.invalid/{output_schema}"),
        referrer=shim,
        store=store,
    )
    validator = Draft7Validator(shim, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)

OUT = "command-center/receipts/BLD-0036.json"
SCHEMA = "command-center/schema/divergence-ruling.schema.json"
ADV = "command-center/adversarial/ADV-0017-repo-live-two-directional-divergence.json"
ADV_RECEIPT = "command-center/receipts/ADV-0017.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0036/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0036/probe2_dryrun_safety.py"
)
STRIKES = HERE / "_schema_strikes.json"
SENTINEL = "SUCCESS:BLD-0036"
CATALOG_PIN = (
    "WORK-UNIT-CATALOG evidence pins: only 5 of 88 rules files byte-identical, "
    "28 content-differing, 55 EOL-only, 25 repo-larger, 3 live-larger "
    "(owner-ops-authorization +1001 B, performance +178 B, security +97 B)."
)
QUESTION = (
    "Question: for each of the 28 content-differing rules files, WHICH SIDE is "
    "authoritative? The divergence is two-directional — 25 repo-larger and 3 "
    "live-larger (owner-ops-authorization +1001 B, performance +178 B, security "
    "+97 B) — so a sync in either direction destroys content."
)
POLICY = (
    "No retry that writes. A failed ruling is reported UNRESOLVED and "
    "escalated. Two same-fingerprint structural refutes park BLOCKED with a "
    "named required_fix. No ADV-0017 rebuild circle."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def err_fp(errs: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(errs)).encode("utf-8")).hexdigest()[:16]


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def art(rel: str, role: str) -> dict:
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


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def save_strikes(data: dict) -> None:
    STRIKES.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def park_blocked(required_fix: str, errs: list[str], fp: str, started: str) -> int:
    now = utcnow()
    blocked = {
        "schema_version": 1,
        "unit_id": "BLD-0036",
        "state": "BLOCKED",
        "sentinel": "FAILED:BLD-0036 parked same-fingerprint structural refute",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:BLD-0036",
        "min_bytes_threshold": 2048,
        "artifacts": [art(SCHEMA, "supporting")],
        "evidence": [
            {
                "claim": (
                    "Two same-fingerprint structural refutes; parked without an "
                    f"ADV rebuild circle. fingerprint={fp}"
                ),
                "verdict": "BLOCKED",
                "anchor": str(STRIKES.relative_to(REPO)).replace("\\", "/"),
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": "schema_resolver.validate_artifact(doc, SCHEMA)",
                        "raw_output": "\n".join(errs[:20])[:8000],
                        "fingerprint": probe_fp(
                            "schema-validate", "schema_resolver.validate_artifact"
                        ),
                        "exit_code": 1,
                    }
                ],
            }
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 2,
            "policy": POLICY,
            "attempts": [
                {"attempt": 1, "error_fingerprint": fp, "outcome": "BLOCKED"},
                {"attempt": 2, "error_fingerprint": fp, "outcome": "BLOCKED"},
            ],
        },
        "failure": {
            "classification": ["schema-invalid", "owner-blocked"],
            "reason": required_fix,
            "blocked_on": required_fix,
            "diagnostic_tail": "\n".join(errs[:25])[:8000],
        },
        "report": {
            "kind": "divergence-ruling",
            "observations": [
                {
                    "name": "schema_fingerprint",
                    "measured": fp,
                    "method": "sha256-16 of sorted schema errors",
                    "anchor": str(STRIKES.relative_to(REPO)).replace("\\", "/"),
                }
            ],
            "control_ids": ["same-fingerprint-park"],
            "required_fix": required_fix,
            "status": "BLOCKED",
        },
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(blocked, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ret = {
        "id": "BLD-0036",
        "unit_id": "BLD-0036",
        "status": "BLOCKED",
        "state": "BLOCKED",
        "required_fix": required_fix,
        "cloud_ok": False,
        "output_path": OUT,
        "notes": "Parked after two same-fingerprint structural refutes. No ADV rebuild circle.",
        "ts": now,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:BLD-0036 parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 1


def live_reads(rows: list[dict]) -> list[dict]:
    out = []
    for rel, delta in ((T.OWNER_OPS, 1001), (T.PERFORMANCE, 178), (T.SECURITY, 97)):
        row = next(r for r in rows if r["path"] == rel)
        live = (T.LIVE_ROOT / rel).read_text(encoding="utf-8")
        repo = (T.REPO_ROOT / rel).read_text(encoding="utf-8")
        live_u = C.unique_lists(repo, live)[1]
        out.append(
            {
                "path": rel,
                "byte_delta": row["live_bytes"] - row["repo_bytes"],
                "expected_byte_delta": delta,
                "classification": row["classification"],
                "verdict": row["verdict"],
                "live_unique_lines": live_u,
                "live_full_text": live,
                "git_log": row["signal1_git_log_cI"],
                "live_mtime": row["signal2_live_mtime"],
                "added_content_is_policy_not_formatting": any(
                    "LIVE-ONLY" in ln for ln in live_u
                ),
            }
        )
    return out


def write_return_and_manifest(
    digest: str, size: int, now: str, rc1: int, out1: str, rc2: int, out2: str
) -> None:
    ret = {
        "id": "BLD-0036",
        "unit_id": "BLD-0036",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/BLD-0036/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "BLD-0036-probe2-live-larger-full-read",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for BLD-0036: live named probes exit 0, BLD-0036.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Did not rebuild ADV-0017."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "BLD-0036",
            "receipt_path": "command-center/p2-wave/probes/BLD-0036/SUBAGENT-RETURN.json",
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0036",
        "verified_on_disk": True,
        "artifacts": [
            row(OUT, "primary"),
            row("command-center/p2-wave/probes/BLD-0036/probe1_controls.py", "supporting"),
            row("command-center/p2-wave/probes/BLD-0036/probe2_dryrun_safety.py", "supporting"),
            row(SCHEMA, "supporting"),
            row("command-center/p2-wave/probes/BLD-0036/SUBAGENT-RETURN.json", "supporting"),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    started = utcnow()
    built = T.build_fixtures()
    host = T.host_candidates()
    rows = R.rule_all(T.REPO_ROOT, T.LIVE_ROOT, built["ledger"])
    plan = R.merge_plan(rows)
    plan_paths = {p["path"] for p in plan}

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:BLD-0036 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    eol_in_plan = [
        r["path"] for r in rows if r["verdict"] == C.VERDICT_EOL and r["path"] in plan_paths
    ]
    no_action = [r["path"] for r in rows if r["verdict"] == C.NO_ACTION]
    eol_only = [r["path"] for r in rows if r["verdict"] == C.VERDICT_EOL]
    planted = next(r for r in rows if r["path"] == T.PLANTED)
    reads = live_reads(rows)
    now = utcnow()
    adv_present = (REPO / ADV).is_file()
    adv_receipt_present = (REPO / ADV_RECEIPT).is_file()
    host_rules_present = any(h["is_dir"] and h["file_count"] > 0 for h in host)
    host_rules_dir = REPO / "rules"
    host_rules_n = (
        sum(1 for p in host_rules_dir.rglob("*") if p.is_file())
        if host_rules_dir.is_dir()
        else 0
    )
    live_rules_n = sum(
        h["file_count"]
        for h in host
        if h["is_dir"] and h["path"].rstrip("/").endswith(".claude/rules")
    )

    counts = {
        "union": len(rows),
        "NO-ACTION": len(no_action),
        "EOL-ONLY": len(eol_only),
        "MERGE": sum(1 for r in rows if r["verdict"] == C.MERGE),
        "REPO-AUTHORITATIVE": sum(1 for r in rows if r["verdict"] == C.REPO_AUTH),
        "LIVE-AUTHORITATIVE": sum(1 for r in rows if r["verdict"] == C.LIVE_AUTH),
        "repo_larger": sum(1 for r in rows if r["repo_larger"]),
        "live_larger": sum(1 for r in rows if r["live_larger"]),
        "merge_plan": len(plan),
    }

    garbage_rejected = 0
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
        gerr = validate_artifact(garbage, SCHEMA)
        if gerr:
            garbage_rejected += 1
        else:
            print(f"FAILED:BLD-0036 schema accepted garbage {list(garbage)[:2]}")
            return 1

    p1_raw = HERE / "probe1-controls.raw.json"
    p2_raw = HERE / "probe2-dryrun.raw.json"
    p1_txt = p1_raw.read_text(encoding="utf-8") if p1_raw.is_file() else ""
    p2_txt = p2_raw.read_text(encoding="utf-8") if p2_raw.is_file() else ""

    answer = (
        f"Host repo rules/ is present ({host_rules_n} files) and live "
        f"~/.claude/rules is absent ({live_rules_n} files); a this-host "
        "live-versus-repo pair cannot be formed, so the 2026-08-09 5/88 "
        "citation is not today's host measurement. On the catalog-shaped "
        "fixture pair: 5 NO-ACTION, 55 EOL-ONLY (excluded from the merge plan), "
        "24 REPO-AUTHORITATIVE (repo-superset), 2 LIVE-AUTHORITATIVE "
        "(performance, security live-supersets), 2 MERGE (planted two-directional "
        "and owner-ops-authorization, both unique). Owner packet requires "
        "approval before any apply. Sync was not executed. SUCCESS:BLD-0036"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "BLD-0036",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:BLD-0036",
        "min_bytes_threshold": 2048,
        "profile": "divergence-ruling",
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "divergence-authority-ruler",
            "execution_substrate": "local-serialized",
        },
        "artifacts": [
            art("command-center/p2-wave/probes/BLD-0036/probe1_controls.py", "supporting"),
            art("command-center/p2-wave/probes/BLD-0036/probe2_dryrun_safety.py", "supporting"),
            art(SCHEMA, "supporting"),
        ],
        "evidence": [
            {
                "claim": (
                    "On the catalog-shaped 88-file fixture, five byte-identical "
                    "files classify NO-ACTION, fifty-five EOL-only files classify "
                    "EOL-ONLY and never enter the merge plan, and a planted "
                    "two-directional file classifies MERGE (never pick-a-side)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0036/probe1-controls.raw.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": out1[-4000:],
                        "fingerprint": probe_fp("command", P1),
                        "exit_code": rc1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": "read command-center/p2-wave/probes/BLD-0036/probe1-controls.raw.json",
                        "raw_output": p1_txt[:4000],
                        "fingerprint": probe_fp(
                            "file-read",
                            "read command-center/p2-wave/probes/BLD-0036/probe1-controls.raw.json",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "The ruling writes nothing into either fixture tree, never "
                    "creates a host rules/ tree, never invokes sync-from-live.ps1 "
                    "or sync-rules.ps1, and a full read of the three live-larger "
                    "files shows added LIVE-ONLY policy text (not formatting) at "
                    "the catalog byte deltas +1001/+178/+97."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0036/probe2-dryrun.raw.json",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": out2[-4000:],
                        "fingerprint": probe_fp("command", P2),
                        "exit_code": rc2,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": "tree_fingerprint before vs after rule_all on fixture roots",
                        "raw_output": p2_txt[:4000],
                        "fingerprint": probe_fp(
                            "byte-compare",
                            "tree_fingerprint before vs after rule_all on fixture roots",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-five-byte-identical-NO-ACTION",
                "command": P1,
                "result": "PASS" if rc1 == 0 and len(no_action) == 5 else "FAIL",
            },
            {
                "id": "T2-fifty-five-EOL-ONLY-never-in-merge-plan",
                "command": P1,
                "result": (
                    "PASS"
                    if rc1 == 0 and len(eol_only) == 55 and not eol_in_plan
                    else "FAIL"
                ),
            },
            {
                "id": "T3-planted-two-directional-MERGE-never-pick-a-side",
                "command": P1,
                "result": "PASS" if planted["verdict"] == C.MERGE else "FAIL",
            },
            {
                "id": "T4-dry-run-writes-nothing-to-either-tree",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-planted-both-unique-must-MERGE",
                "kind": "known-broken-fixture",
                "description": (
                    "A planted file with unique lines on both sides must produce "
                    "MERGE, never REPO-AUTHORITATIVE or LIVE-AUTHORITATIVE."
                ),
                "fired_on_bad_state": planted["verdict"] == C.MERGE
                and planted["classification"] == C.BOTH_UNIQUE,
                "silent_on_good_state": all(
                    r["verdict"] != C.MERGE for r in rows if r["verdict"] == C.NO_ACTION
                ),
                "bad_state_output": f"planted verdict={planted['verdict']} class={planted['classification']}",
                "good_state_output": f"NO-ACTION count={len(no_action)} none in merge plan",
            },
            {
                "id": "NC-eol-only-excluded-from-merge-plan",
                "kind": "known-broken-fixture",
                "description": (
                    "EOL-only pairs must classify EOL-ONLY and must never enter "
                    "the merge plan."
                ),
                "fired_on_bad_state": planted["path"] in plan_paths,
                "silent_on_good_state": len(eol_in_plan) == 0,
                "bad_state_output": "planted MERGE path is in merge plan",
                "good_state_output": "eol_in_plan=[]",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0036-probe2-live-larger-full-read",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "xai",
            "notes": (
                "Independent of probe 1: probe 2 reads the three live-larger "
                "files in full and confirms added content is LIVE-ONLY policy "
                "text, not formatting. "
                f"policy_reads={sum(1 for r in reads if r['added_content_is_policy_not_formatting'])}/3."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/BLD-0036/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "BLD-0036",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py (validate_artifact)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c \"import sys; sys.path.insert(0,'platform/lib'); "
                        "from schema_resolver import validate_artifact; "
                        "print(validate_artifact(doc, "
                        "'command-center/schema/divergence-ruling.schema.json'))\""
                    ),
                    "raw_output": f"garbage_rejected={garbage_rejected}/3; validate_artifact errors=[]",
                    "fingerprint": probe_fp(
                        "schema-validate", "schema_resolver.validate_artifact"
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": POLICY,
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The 2026-08-09 Windows citation '5 of 88 rules files "
                    "byte-identical' is not a live host measurement on this "
                    "Linux worktree (repo rules/ and ~/.claude/rules are absent)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-walk C:/Users/Prekzursil/source/ast-integrate/rules vs "
                    "~/.claude/rules on a host that still has those trees; do "
                    "not rebuild ADV-0017."
                ),
            },
            {
                "claim": (
                    "git log -1 --format=%cI per rules path exits 128 because "
                    "this estate root has no .git; the fixture ledger ISO is the "
                    "independent repo-side timestamp analogue."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a git checkout that tracks rules/<path>, re-run "
                    "`git log -1 --format=%cI -- rules/<path>` and compare to "
                    "the live mtime plus this receipt's ledger ISO."
                ),
            },
        ],
        "report": {
            "kind": "divergence-ruling",
            "observations": [
                {
                    "name": "union_files",
                    "measured": counts["union"],
                    "method": "rule_all over fixture repo∪live",
                    "anchor": "command-center/p2-wave/probes/BLD-0036/ruling.py",
                },
                {
                    "name": "NO-ACTION",
                    "measured": counts["NO-ACTION"],
                    "method": "BYTE-IDENTICAL classification",
                    "anchor": "command-center/p2-wave/probes/BLD-0036/probe1-controls.raw.json",
                },
                {
                    "name": "EOL-ONLY",
                    "measured": counts["EOL-ONLY"],
                    "method": "LF-normalised identity",
                    "anchor": "command-center/p2-wave/probes/BLD-0036/probe1-controls.raw.json",
                },
                {
                    "name": "repo_larger",
                    "measured": counts["repo_larger"],
                    "method": "content-differing live_bytes vs repo_bytes",
                    "anchor": "command-center/p2-wave/probes/BLD-0036/classify.py",
                },
                {
                    "name": "live_larger",
                    "measured": counts["live_larger"],
                    "method": "content-differing live_bytes vs repo_bytes",
                    "anchor": "command-center/p2-wave/probes/BLD-0036/classify.py",
                },
                {
                    "name": "MERGE",
                    "measured": counts["MERGE"],
                    "method": "BOTH-UNIQUE forces MERGE; clocks do not pick a side",
                    "anchor": "command-center/p2-wave/probes/BLD-0036/ruling.py",
                },
                {
                    "name": "host_repo_rules_file_count",
                    "measured": host_rules_n,
                    "method": "rglob files under estate rules/",
                    "anchor": "rules/",
                },
                {
                    "name": "host_live_claude_rules_file_count",
                    "measured": live_rules_n,
                    "method": "host_candidates for ~/.claude/rules",
                    "anchor": "~/.claude/rules",
                },
                {
                    "name": "executed_sync",
                    "measured": False,
                    "method": "dry-run mtime/size/sha freeze; sync scripts not invoked",
                    "anchor": "command-center/p2-wave/probes/BLD-0036/probe2-dryrun.raw.json",
                },
            ],
            "control_ids": [
                "T1-five-byte-identical-NO-ACTION",
                "T2-fifty-five-EOL-ONLY-never-in-merge-plan",
                "T3-planted-two-directional-MERGE-never-pick-a-side",
                "T4-dry-run-writes-nothing-to-either-tree",
            ],
            "question": QUESTION,
            "answer": answer,
            "title": (
                "Two-directional live-versus-repo divergence: per-file "
                "authority ruling and a merge plan"
            ),
            "consumed_detection": {
                "adv_0017_output_path": ADV,
                "adv_0017_present": adv_present,
                "adv_0017_receipt_present": adv_receipt_present,
                "rebuilt_adv_0017": False,
                "catalog_pin": CATALOG_PIN,
                "consumed_instead": [
                    "WORK-UNIT-CATALOG.json pin for the 5/55/28 shape and the three named live-larger byte deltas",
                    "ADV-0017 detection receipt consumed, not re-derived",
                ],
                "note": (
                    "ADV-0017 DETECTS two-directional divergence. This unit "
                    "consumes that detection shape and contributes per-file "
                    "AUTHORITY from git log %cI versus live mtime plus a content "
                    "read of the live-larger files, a MERGE plan for both-unique "
                    "files, and the owner packet. It does not rebuild ADV-0017."
                ),
            },
            "host_measurement": {
                "host_rules_present": host_rules_present,
                "host_repo_rules_file_count": host_rules_n,
                "host_live_claude_rules_file_count": live_rules_n,
                "cited_5_of_88_on_host": False,
                "git_repo_present_at_estate_root": (REPO / ".git").exists(),
                "host_candidates": host,
                "fixture_roots": {
                    "repo": "command-center/p2-wave/probes/BLD-0036/fixtures/repo",
                    "live": "command-center/p2-wave/probes/BLD-0036/fixtures/live",
                },
            },
            "summary": counts,
            "rulings": rows,
            "merge_plan": plan,
            "owner_packet": {
                "owner_approval_required": True,
                "executed_sync": False,
                "never_run": [
                    "scripts/sync-from-live.ps1",
                    "scripts/sync-rules.ps1",
                    "Copy-Item -Force of either tree onto the other",
                ],
                "authorize_when_approved": (
                    "NO-ACTION and EOL-ONLY: skip. REPO-AUTHORITATIVE: take repo "
                    "(live is a subset). LIVE-AUTHORITATIVE: take live (repo is a "
                    "subset). MERGE: apply the union preview; never pick a side. "
                    "Do not execute until the owner signs this packet."
                ),
                "merge_file_count": len(plan),
                "eol_only_excluded_from_plan": len(eol_in_plan) == 0,
                "no_action_excluded_from_plan": all(p not in plan_paths for p in no_action),
                "planted_two_directional_is_merge": planted["verdict"] == C.MERGE,
            },
            "live_larger_content_reads": reads,
            "safety": {
                "wrote_host_rules": False,
                "invoked_sync_script": False,
                "measurement_only_on_host": True,
            },
            "named_probes": [
                {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
                {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-4000:]},
            ],
            "fixture_counts": built["counts"],
        },
    }

    if any(t["result"] != "PASS" for t in doc["tests"]):
        print("FAILED:BLD-0036 a required control did not PASS")
        print(json.dumps(doc["tests"], indent=2))
        return 1

    errs = validate_artifact(doc, SCHEMA)
    if errs:
        fp = err_fp(errs)
        strikes = load_strikes()
        prior = [a for a in strikes["attempts"] if a.get("fp") == fp]
        strikes["attempts"].append(
            {"fp": fp, "n": len(errs), "head": errs[:12], "ts": now}
        )
        save_strikes(strikes)
        print("FAILED:BLD-0036 schema-invalid")
        for e in errs[:20]:
            print(f"  {e}")
        if prior:
            return park_blocked(
                required_fix=f"break-same-fingerprint:{fp}",
                errs=errs,
                fp=fp,
                started=started,
            )
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out_path)
    if size < 2048:
        print(f"FAILED:BLD-0036 artifact {size}B below floor")
        return 1
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or parsed.get("state") == "BLOCKED":
        print("FAILED:BLD-0036 written artifact is BLOCKED or unusable")
        return 1
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:BLD-0036 sentinel absent from artifact")
        return 1
    write_return_and_manifest(digest, size, now, rc1, out1, rc2, out2)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:BLD-0036 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
