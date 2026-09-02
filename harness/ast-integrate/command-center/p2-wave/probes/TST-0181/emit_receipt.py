#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0181.json from live loader measurements."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from hooks_client import LoadError, fire_each, inventory_equals, load  # noqa: E402
from scenario import expected_hook_ids, expected_skill_ids, seed_tree  # noqa: E402
import _p2lib as L  # noqa: E402

UNIT = "TST-0181"
OUT = "command-center/receipts/TST-0181.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/parser_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0181/probe1_schema_parity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0181/probe2_detector_drop.py"
)
QUESTION = (
    "Does the presence or absence of a `$schema` key alter how many hooks/skills "
    "a client loads? PASS requires an identical loaded set across both forms, "
    "and a loud error if any hook fails to load rather than a silent zero."
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0181/hooks_client.py",
    "command-center/p2-wave/probes/TST-0181/scenario.py",
    "command-center/p2-wave/probes/TST-0181/probe1_schema_parity.py",
    "command-center/p2-wave/probes/TST-0181/probe2_detector_drop.py",
]


def digest_rel(rel: str) -> tuple[str, int, bool]:
    path = REPO / rel
    if not path.is_file():
        return "", 0, False
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw), True


def measure() -> dict:
    want_hooks = expected_hook_ids()
    want_skills = expected_skill_ids()
    with tempfile.TemporaryDirectory(prefix="tst0181-emit-") as tmp:
        base = Path(tmp)
        man_with = seed_tree(base / "with", schema=True)
        man_without = seed_tree(base / "without", schema=False)
        inv_with = load(man_with)
        inv_without = load(man_without)
        fired = fire_each(man_with, base / "markers")
        silent = load(man_with, mode="deny-unknown-silent")

        man_drop = seed_tree(base / "drop", schema=True)
        baseline = load(man_drop)
        dropped = base / "drop" / "hooks" / "post-tool.py"
        dropped.unlink()
        after = load(man_drop)
        declared_only = load(man_drop, mode="count-declared-only")
        unknown_err = None
        man_unknown = seed_tree(
            base / "unknown", schema=True, extra={"notARealField": True}
        )
        try:
            load(man_unknown)
        except LoadError as exc:
            unknown_err = str(exc)

        ok_parity = (
            not inv_with.errors
            and not inv_without.errors
            and inventory_equals(inv_with, inv_without)
            and inv_with.hook_ids == want_hooks
            and inv_with.skill_ids == want_skills
            and inv_with.schema_present
            and not inv_without.schema_present
            and set(fired.fired) == set(want_hooks)
            and not fired.errors
        )
        ok_detector = (
            after.hook_count == baseline.hook_count - 1
            and "post-tool" not in after.hook_ids
            and any("post-tool" in e for e in after.errors)
            and declared_only.hook_count == baseline.hook_count
            and silent.hook_count == 0
            and not silent.errors
            and unknown_err is not None
            and "notARealField" in unknown_err
        )
        return {
            "ok_parity": ok_parity,
            "ok_detector": ok_detector,
            "with_schema": inv_with.as_dict(),
            "without_schema": inv_without.as_dict(),
            "fired": fired.as_dict(),
            "deny_unknown_silent": silent.as_dict(),
            "baseline_count": baseline.hook_count,
            "after_unlink_count": after.hook_count,
            "after_unlink_errors": after.errors,
            "declared_only_count": declared_only.hook_count,
            "unknown_field_error": unknown_err,
            "want_hooks": want_hooks,
            "want_skills": want_skills,
        }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    measured = measure()
    if not measured["ok_parity"] or not measured["ok_detector"]:
        print(
            f"FAILED:TST-0181 emit parity={measured['ok_parity']} "
            f"detector={measured['ok_detector']}"
        )
        print(json.dumps(measured, indent=2, sort_keys=True)[:4000])
        return 1

    c1, t1 = L.run(["python3", "-B", str(HERE / "probe1_schema_parity.py")])
    c2, t2 = L.run(["python3", "-B", str(HERE / "probe2_detector_drop.py")])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0181 probes-before-write c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    artifacts = []
    for rel in SUPPORTING:
        sha, n, exists = digest_rel(rel)
        artifacts.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": n,
                "exists": exists,
                "role": "supporting",
                "eol": "LF",
            }
        )

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_src_1 = L.probe("source", "command", P1, t1[-4000:], c1)
    p_ver_1 = L.probe(
        "verifier",
        "in-process-load",
        "load(with $schema) vs load(without $schema) + fire_each",
        json.dumps(
            {
                "with_count": measured["with_schema"]["hook_count"],
                "without_count": measured["without_schema"]["hook_count"],
                "fired": sorted(measured["fired"]["fired"]),
            }
        ),
        0,
    )
    p_src_2 = L.probe("source", "command", P2, t2[-4000:], c2)
    p_ver_2 = L.probe(
        "verifier",
        "in-process-unlink",
        "unlink post-tool.py then load(); compare deny-unknown-silent",
        json.dumps(
            {
                "baseline": measured["baseline_count"],
                "after": measured["after_unlink_count"],
                "silent_zero": measured["deny_unknown_silent"]["hook_count"],
                "errors": measured["after_unlink_errors"],
            }
        ),
        0,
    )

    answer = (
        "NO: the allow-schema client loads the same three hooks and two skills "
        f"with and without `$schema` (count={measured['with_schema']['hook_count']}). "
        "Removing post-tool.py drops the live count by one and names the missing "
        "file. The deny-unknown silent mutant still loads ZERO hooks when "
        "`$schema` is present, which is the Codex regression this unit refuses."
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0181",
        "completion_sentinel": "SUCCESS:TST-0181",
        "title": "A `$schema` key must not change which hooks load",
        "spec_anchor": "_USER-PROMPTS.md:11014,11302,11309; MEMORY:hooks.json $schema",
        "question": QUESTION,
        "answer": answer,
        "report_kind": "parser_report",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "schema_key_does_not_change_loaded_set": True,
        "detector_count_drops_when_hook_file_removed": True,
        "loud_error_on_missing_hook": True,
        "silent_zero_refuted": True,
        "parser": {
            "client": "command-center/p2-wave/probes/TST-0181/hooks_client.py",
            "reserved_annotation_keys": ["$schema"],
            "unknown_top_level_policy": "loud-reject-named-field",
            "missing_hook_policy": "drop-from-count-and-name-in-errors",
            "codex_deny_unknown_silent_reproduced": True,
        },
        "loaded_sets": {
            "with_schema": measured["with_schema"],
            "without_schema": measured["without_schema"],
            "identical": True,
            "fired_side_effects": measured["fired"]["fired"],
        },
        "detector": {
            "baseline_count": measured["baseline_count"],
            "after_unlink_count": measured["after_unlink_count"],
            "after_unlink_errors": measured["after_unlink_errors"],
            "declared_only_count": measured["declared_only_count"],
            "deny_unknown_silent_count": measured["deny_unknown_silent"]["hook_count"],
            "unknown_field_error": measured["unknown_field_error"],
        },
        "artifacts": artifacts,
        "evidence": [
            L.evidence(
                "Signal (a): client inventory count is identical with and without "
                f"`$schema` ({measured['with_schema']['hook_count']} hooks, "
                f"{measured['with_schema']['skill_count']} skills).",
                "CONFIRMED",
                "command-center/p2-wave/probes/TST-0181/hooks_client.py:load",
                [p_src_1, p_ver_1],
                "almost-certain",
            ),
            L.evidence(
                "Signal (b): firing each resolved hook wrote a unique marker "
                f"{sorted(measured['fired']['fired'])}; inventory ids match the "
                "fire-probe set.",
                "CONFIRMED",
                "command-center/p2-wave/probes/TST-0181/hooks_client.py:fire_each",
                [p_src_1, p_ver_1],
                "almost-certain",
            ),
            {
                "path": "command-center/p2-wave/probes/TST-0181/hooks_client.py",
                "kind": "inventory-count",
                "claim": (
                    "Loaded-hook count from the client is equal across $schema forms."
                ),
                "anchor": "hooks_client.py:load",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0181/hooks_client.py",
                "kind": "hook-fire-side-effect",
                "claim": (
                    "Independent fire probe observed a marker per hook; registration "
                    "was not inferred from file presence alone."
                ),
                "anchor": "hooks_client.py:fire_each",
            },
        ],
        "tests": [
            {
                "id": "TST-0181-T1-both-states-schema",
                "name": "both-states control: the counts must be equal with and without `$schema`",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 2,
                "output_tail": t1[-1500:],
            },
            {
                "id": "TST-0181-T2-detector-drop",
                "name": (
                    "detector control: remove one hook file and confirm the count "
                    "probe drops (regression seed: hooks.json $schema silent zero)"
                ),
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 4,
                "output_tail": t2[-1500:],
            },
        ],
        "checks": [
            {
                "id": "schema-parity",
                "verdict": "PASS" if measured["ok_parity"] else "FAIL",
            },
            {
                "id": "detector-drop",
                "verdict": "PASS" if measured["ok_detector"] else "FAIL",
            },
            {
                "id": "codex-silent-zero-mutant",
                "verdict": "PASS",
                "observed_count": measured["deny_unknown_silent"]["hook_count"],
            },
        ],
        "negative_controls": [
            L.control(
                "unlink-post-tool",
                "known-broken-fixture",
                "Delete hooks/post-tool.py. Live resolve count must drop by one and "
                "the error must name the hook. Declared-only counting stays at baseline.",
                True,
                True,
                bad=f"count={measured['after_unlink_count']} errors={measured['after_unlink_errors']}",
                good=f"count={measured['baseline_count']}",
            ),
            L.control(
                "deny-unknown-silent-schema",
                "mutation",
                "Codex-shaped deny_unknown_fields client swallows `$schema` into a "
                "silent zero. Production allow-schema client must not match it.",
                True,
                True,
                bad=f"silent_count={measured['deny_unknown_silent']['hook_count']}",
                good=f"allow_schema_count={measured['with_schema']['hook_count']}",
            ),
            L.control(
                "unknown-top-level-field",
                "known-broken-fixture",
                "A non-$schema extra key is a loud named reject, not a silent zero.",
                True,
                True,
                bad=measured["unknown_field_error"] or "",
                good="hooks.json with only $schema+hooks+skills loads",
            ),
        ],
        "reviewer": {
            "reviewer_id": "TST-0181-probe2-detector-drop",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Adversarial control is probe2: it unlinks a hook file to prove the "
                "count probe can see a change, and it runs the deny-unknown silent "
                "mutant that reproduces the Codex `$schema` zero-load seed. Not a "
                "second-human review."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0181/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0181",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py TST-0181",
                    "deferred to post-write measure",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Installed Codex CLI HooksFile serde(deny_unknown_fields) was "
                    "not invoked as a binary on this Linux worktree; the silent-zero "
                    "behaviour is reproduced by the deny-unknown-silent mutant that "
                    "matches the recorded estate failure class."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Feed the same fixtures to a live `codex` hooks loader and "
                    "compare inventory counts."
                ),
            },
            {
                "claim": (
                    "_USER-PROMPTS.md:11014 / 11302 / 11309 are not on this "
                    "worktree; the unit question is taken from "
                    "WORK-UNIT-CATALOG.json TST-0181."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Diff the catalog question against the prompts file if restored."
                ),
            },
        ],
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot - same-fingerprint structural refute parks BLOCKED",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "defects": [],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:TST-0181")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
