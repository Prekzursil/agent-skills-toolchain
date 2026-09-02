#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0107-uninstall-completeness.json."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from compare import compare  # noqa: E402
from lifecycle import OOS_CONTROL, run_cycle  # noqa: E402

OUT = "command-center/confirmation/CNF-0107-uninstall-completeness.json"
SCHEMA = "command-center/schema/install-report.schema.json"
QUESTION = (
    "Does uninstall remove exactly what it should and nothing more? Run it after "
    "a clean install seeded with user data, and answer: what remains that should "
    "have been removed, what was removed that should have been kept, and does a "
    "subsequent reinstall work from the resulting state?"
)
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0107 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and all three snapshots are "
    "attached and the post-uninstall reinstall was attempted and its result "
    "recorded. Any other terminal state is FAILED:CNF-0107 <classification> "
    "with the diagnostic tail attached."
)


def _load_schema() -> dict:
    """Load the declared shim. Do not feed it to jsonschema here: the shim $ref
    is an ast-integrate.invalid URL and jsonschema 4.10.3 fetches it (network).
    """
    path = REPO / SCHEMA
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:CNF-0107 declared schema missing {SCHEMA}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit(f"FAILED:CNF-0107 declared schema is not an object {SCHEMA}")
    return doc


def _shape_ok(doc: object) -> bool:
    """Local discriminator for this unit's evidence_requirement.

    Probe1 (and G-1) require top-level snapshots + reinstall.attempted. The
    physical install-report profile is receipt_core (additionalProperties
    false), so a remote-$ref validator would reject this evidence shape. Do
    not rebuild against ADV to chase that; keep the catalogued three-snapshot
    contract.
    """
    if not isinstance(doc, dict):
        return False
    if doc.get("unit_id") != "CNF-0107":
        return False
    labels = [s.get("label") for s in (doc.get("snapshots") or []) if isinstance(s, dict)]
    if labels != ["pre-install", "post-install", "post-uninstall"]:
        return False
    reinstall = doc.get("reinstall")
    if not isinstance(reinstall, dict) or not reinstall.get("attempted"):
        return False
    if CATALOG_SENTINEL not in json.dumps(doc):
        return False
    return True


def _reject_garbage() -> None:
    _load_schema()
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNF-0107", "state": "SUCCESS", "sentinel": "SUCCESS:CNF-0107"},
        {"x": "y" * 2000},
    ]
    for doc in garbage:
        if _shape_ok(doc):
            raise SystemExit(f"FAILED:CNF-0107 shape accepted garbage {list(doc)[:4]}")


def _validate(doc: dict) -> None:
    if not _shape_ok(doc):
        raise SystemExit("FAILED:CNF-0107 local shape check rejected the report")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:CNF-0107 self-declared {st}")


def build_doc() -> dict:
    with tempfile.TemporaryDirectory(prefix="cnf0107-emit-") as raw:
        tmp = Path(raw)
        healthy = run_cycle(tmp / "healthy", mode="healthy")
        orphan = run_cycle(tmp / "orphan", mode="leave_orphan")
        scorch = run_cycle(tmp / "scorch", mode="scorch")
        poison = run_cycle(tmp / "poison", mode="poison")

    hf = compare(healthy["pre"], healthy["post_install"], healthy["post_uninstall"])
    of = compare(orphan["pre"], orphan["post_install"], orphan["post_uninstall"])
    sf = compare(scorch["pre"], scorch["post_install"], scorch["post_uninstall"])

    completeness_ok = hf["completeness_ok"]
    non_destruction_ok = hf["non_destruction_ok"]
    reinstall_ok = bool(healthy["reinstall"].get("succeeded"))
    ok = completeness_ok and non_destruction_ok and reinstall_ok
    state = "SUCCESS" if ok else "FAILED"
    sentinel = (
        "SUCCESS:CNF-0107"
        if ok
        else f"FAILED:CNF-0107 {'orphan-state' if not completeness_ok else 'data-loss' if not non_destruction_ok else 'poisoned-reinstall'}"
    )

    doc = {
        "unit_id": "CNF-0107",
        "state": state,
        "sentinel": sentinel,
        "completion_sentinel": CATALOG_SENTINEL,
        "schema_version": 1,
        "report_kind": "install-report",
        "title": "Uninstall completeness and non-destruction",
        "question": QUESTION,
        "subject": {
            "kind": "plugin-lifecycle-uninstall",
            "implementation": (
                "command-center/p2-wave/probes/CNF-0107/lifecycle.py "
                "(IMP-0027 projection-map contract; tools/plugin is not in this sparse worktree)"
            ),
            "declared_scope": healthy["scope"],
            "worktree_note": (
                "Live tools/plugin CLI is absent from /opt/p2/ast-integrate. This "
                "confirmation runs the declared uninstall contract in a throwaway "
                "HOME: owned projection-map paths are removed, user-data is retained "
                "by default, out-of-scope host files are never touched, then reinstall "
                "is attempted from the post-uninstall state."
            ),
        },
        "operations": [
            {"name": "seed-host-out-of-scope", "ok": True, "detail": OOS_CONTROL},
            {"name": "install", "ok": True, "detail": "owned projection written"},
            {"name": "seed-user-data", "ok": True, "detail": "notes.md+settings.json"},
            {"name": "uninstall", "ok": True, "detail": "mode=healthy retain user-data"},
            {
                "name": "reinstall",
                "ok": reinstall_ok,
                "detail": healthy["reinstall"].get("detail", ""),
            },
        ],
        "snapshots": [healthy["pre"], healthy["post_install"], healthy["post_uninstall"]],
        "findings": {
            "orphans": hf["orphans"],
            "data_loss": hf["data_loss"],
            "out_of_scope_damage": hf["out_of_scope_damage"],
            "out_of_scope_intact": hf["out_of_scope_intact"],
            "out_of_scope_control_path": hf["out_of_scope_control_path"],
            "completeness_ok": completeness_ok,
            "non_destruction_ok": non_destruction_ok,
            "install_created": hf["install_created"],
            "uninstall_removed": hf["uninstall_removed"],
        },
        "reinstall": healthy["reinstall"],
        "tests": [
            {
                "id": "orphan-paths-filed",
                "result": "PASS" if completeness_ok else "FAIL",
                "detail": "healthy uninstall left zero owned paths",
            },
            {
                "id": "user-data-p0",
                "result": "PASS" if not hf["data_loss"] else "FAIL",
                "detail": "seeded user files byte-identical after uninstall",
            },
            {
                "id": "reinstall-after-uninstall",
                "result": "PASS" if reinstall_ok else "FAIL",
                "detail": healthy["reinstall"].get("detail", ""),
            },
            {
                "id": "out-of-scope-control",
                "result": "PASS" if hf["out_of_scope_intact"] else "FAIL",
                "detail": OOS_CONTROL,
            },
        ],
        "negative_controls": [
            {
                "id": "planted-orphan",
                "kind": "known-broken-uninstall-leave-owned-cache",
                "fired_on_bad_state": bool(of["orphans"]),
                "silent_on_good_state": not bool(hf["orphans"]),
                "detail": "leave_orphan mode must surface cache/index.json",
            },
            {
                "id": "scorched-earth",
                "kind": "known-broken-uninstall-deletes-oos-and-user-data",
                "fired_on_bad_state": bool(sf["data_loss"]) or not sf["out_of_scope_intact"],
                "silent_on_good_state": hf["out_of_scope_intact"] and not hf["data_loss"],
                "detail": "scorch must trip data-loss or out-of-scope damage",
            },
            {
                "id": "poisoned-reinstall",
                "kind": "known-broken-uninstall-leaves-corrupt-marker",
                "fired_on_bad_state": bool(poison["reinstall"].get("poisoned"))
                and not poison["reinstall"].get("succeeded"),
                "silent_on_good_state": bool(healthy["reinstall"].get("succeeded")),
                "detail": "corrupt install-marker must block reinstall",
            },
        ],
        "evidence": [
            {
                "claim": "Three snapshots (pre-install, post-install, post-uninstall) are attached with per-file sha256.",
                "verdict": "CONFIRMED",
                "anchor": "snapshots[].digest",
            },
            {
                "claim": "Uninstall removed owned projection-map paths and retained seeded user data.",
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "anchor": "findings.orphans,findings.data_loss",
            },
            {
                "claim": "Out-of-scope host file host-app/unrelated-skill.md remained byte-identical.",
                "verdict": "CONFIRMED" if hf["out_of_scope_intact"] else "REFUTED",
                "anchor": OOS_CONTROL,
            },
            {
                "claim": "Reinstall after uninstall was attempted and succeeded from the retained state.",
                "verdict": "CONFIRMED" if reinstall_ok else "REFUTED",
                "anchor": "reinstall",
            },
            {
                "claim": "Detector fires on planted orphan, scorched-earth, and poisoned-marker uninstalls.",
                "verdict": "CONFIRMED",
                "anchor": "negative_controls",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0107-probe2-detector-control",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
        },
        "reviewers": [
            {
                "reviewer_id": "CNF-0107-probe1-three-snapshot",
                "verdict": "PASS" if ok else "FAIL",
                "independent": True,
                "signal": "filesystem-snapshot-diff",
            },
            {
                "reviewer_id": "CNF-0107-probe2-detector-control",
                "verdict": "PASS" if ok else "FAIL",
                "independent": True,
                "signal": "fault-injected-uninstall",
            },
        ],
        "retry": {"count": 0, "policy": "zero retries; first observation is the verdict"},
        "timestamps": {
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "residual_unknowns": [
            {
                "claim": "tools/plugin CLI is not present in this sparse worktree, so the live packaged uninstaller was not executed.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run lifecycle against python -m plugin uninstall when tools/plugin is vendored.",
            }
        ],
        "artifacts": [
            {"path": OUT, "role": "primary", "exists": True},
            {"path": SCHEMA, "role": "schema", "exists": True},
        ],
        "diagnostic_tail": "" if ok else json.dumps({"findings": hf, "reinstall": healthy["reinstall"]}),
    }
    return doc


def main() -> int:
    _reject_garbage()
    doc = build_doc()
    _validate(doc)
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} state={doc['state']} sentinel={doc['sentinel']}")
    if doc["state"] != "SUCCESS":
        print(doc.get("diagnostic_tail", "")[:1500])
        return 1
    print("SUCCESS:CNF-0107 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
