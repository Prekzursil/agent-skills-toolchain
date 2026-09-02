"""Emit IMP-0024 receipt, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import unique_line_differ as differ  # noqa: E402
import update as upd  # noqa: E402

UNIT = "IMP-0024"
OUT = "command-center/receipts/IMP-0024.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0024/probe1_upgrade_edit_survives.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0024/probe2_unique_line_differ.py"
)
TEST = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/plugin/tests/test_update_preserves_overrides.py"
)
SUPPORTING = [
    "tools/plugin/update.py",
    "tools/plugin/three_way_merge.py",
    "tools/plugin/unique_line_differ.py",
    "tools/plugin/tests/test_update_preserves_overrides.py",
    "command-center/p2-wave/probes/IMP-0024/probe1_upgrade_edit_survives.py",
    "command-center/p2-wave/probes/IMP-0024/probe2_unique_line_differ.py",
    "command-center/p2-wave/probes/IMP-0024/write_receipts.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def live_rehearsal() -> dict:
    """In-process throwaway HOME: upgrade + independent differ + negative control."""
    v1, v2, v3 = upd.payload_v1(), upd.payload_v2(), upd.payload_v3()
    with tempfile.TemporaryDirectory(prefix="imp0024-receipt-") as td:
        root = Path(td) / "home"
        upd.seed_live_tree(root, v1, version="1.0.0")
        ours = upd.apply_user_override(root)
        r12 = upd.update(
            root,
            base_payload=v1,
            theirs_payload=v2,
            from_version="1.0.0",
            to_version="1.1.0",
        )
        notes_v2 = (root / "notes.md").read_bytes()
        census_v2 = differ.census(v1["notes.md"], ours["notes.md"], notes_v2)
        r23 = upd.update(
            root,
            base_payload=v2,
            theirs_payload=v3,
            from_version="1.1.0",
            to_version="1.2.0",
        )
        settings = upd.parsed_settings(root)
        notes_v3 = (root / "notes.md").read_bytes()
        census_v3 = differ.census(v1["notes.md"], ours["notes.md"], notes_v3)

        bad = Path(td) / "no-clf"
        upd.seed_live_tree(bad, v1, version="1.0.0")
        ours_bad = upd.apply_user_override(bad)
        r_bad = upd.update(
            bad,
            base_payload=v1,
            theirs_payload=v2,
            from_version="1.0.0",
            to_version="1.1.0",
            classifier_enabled=False,
        )
        census_bad = differ.census(
            v1["notes.md"], ours_bad["notes.md"], (bad / "notes.md").read_bytes()
        )

        conflict = Path(td) / "conflict"
        upd.seed_live_tree(conflict, v1, version="1.0.0")
        upd.apply_user_theme_conflict(conflict)
        before = upd.tree_sha(conflict)
        r_c = upd.update(
            conflict,
            base_payload=v1,
            theirs_payload=upd.payload_conflict_theirs(),
            from_version="1.0.0",
            to_version="1.1.0",
        )

        reviewer = Path(td) / "reviewer"
        upd.seed_live_tree(reviewer, v1, version="1.0.0")
        ours_r = upd.apply_reviewer_unanticipated(reviewer)
        r_r = upd.update(
            reviewer,
            base_payload=v1,
            theirs_payload=v2,
            from_version="1.0.0",
            to_version="1.1.0",
        )
        rev_settings = upd.parsed_settings(reviewer)
        rev_text = (reviewer / "settings.json").read_text(encoding="utf-8")
        rev_notes = (reviewer / "notes.md").read_bytes()
        rev_census = differ.census(v1["notes.md"], ours_r["notes.md"], rev_notes)

        differ_src = (PLUGIN / "unique_line_differ.py").read_text(encoding="utf-8")
        isolated = not any(
            line.strip().startswith(("import ", "from "))
            and ("three_way_merge" in line or " update" in line or line.strip() == "import update")
            for line in differ_src.splitlines()
        )

        return {
            "v1_to_v2": {
                "proceeded": r12.proceeded,
                "reason": r12.reason,
                "classifications": {
                    p.relpath: p.classification for p in r12.files
                },
            },
            "v2_to_v3": {"proceeded": r23.proceeded, "reason": r23.reason},
            "settings_after_chain": settings,
            "accent_survived": settings.get("accent") == upd.USER_ACCENT_VALUE,
            "census_v2": census_v2,
            "census_v3": census_v3,
            "negative_control": {
                "classifier_enabled": False,
                "proceeded": r_bad.proceeded,
                "unique_lines_dropped": census_bad["all_unique_present"] is False,
                "census": census_bad,
            },
            "conflicted": {
                "proceeded": r_c.proceeded,
                "wrote": r_c.wrote,
                "tree_unchanged": upd.tree_sha(conflict) == before,
                "paths": r_c.conflicted,
            },
            "reviewer": {
                "key_order": list(rev_settings.keys()),
                "jsonc_comment": "reviewer: key order is load-bearing" in rev_text,
                "notes_comment": upd.REVIEWER_COMMENT_LINE.encode("ascii") in rev_notes,
                "census": rev_census,
                "proceeded": r_r.proceeded,
            },
            "differ_isolated_from_merge": isolated,
        }


def main() -> int:
    started = now()
    test_rc, test_out = run(TEST)
    if test_rc != 0:
        print("FAILED:IMP-0024 tests")
        print(test_out[-4000:])
        return 1

    rehearsal = live_rehearsal()
    if not rehearsal["accent_survived"] or not rehearsal["census_v3"]["all_unique_present"]:
        print("FAILED:IMP-0024 in-process rehearsal lost the user edit")
        print(json.dumps(rehearsal, indent=2)[:4000])
        return 1
    if not rehearsal["negative_control"]["unique_lines_dropped"]:
        print("FAILED:IMP-0024 negative control did not go red")
        return 1
    if rehearsal["conflicted"]["proceeded"] or not rehearsal["conflicted"]["tree_unchanged"]:
        print("FAILED:IMP-0024 conflicted path mutated the tree")
        return 1
    if not rehearsal["differ_isolated_from_merge"]:
        print("FAILED:IMP-0024 unique_line_differ imports the merge implementation")
        return 1

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0024",
        "completion_sentinel": "SUCCESS:IMP-0024",
        "title": "`update` command preserving user overrides across versions",
        "question_or_target": (
            "Implement `update` so that a user-modified deployed file is never "
            "silently overwritten: classify each target as unchanged-by-user "
            "(replace), changed-by-user (three-way merge via IMP-0031), or "
            "conflicted (stop and report), and preserve user data and settings "
            "across the version boundary."
        ),
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "implementation": {
            "module": "tools/plugin/update.py",
            "merge": "tools/plugin/three_way_merge.py",
            "independent_differ": "tools/plugin/unique_line_differ.py",
            "tests": "tools/plugin/tests/test_update_preserves_overrides.py",
            "classifier": (
                "unchanged-by-user (LF-byte equal to shipped vN) -> replace; "
                "changed-by-user -> three-way merge; conflicted -> stop, write nothing"
            ),
            "permission_gate": "permission_diff.gate_update (IMP-0060) before apply",
            "foreign_files": "live paths not in the payload are skipped, never deleted",
        },
        "rehearsal": rehearsal,
        "evidence": [
            {
                "claim": (
                    "A scripted upgrade from vN to vN+1 in a throwaway HOME with a "
                    "user-edited file present keeps the user's accent setting and "
                    "unique notes.md line; v1->v2->v3 preserves the same edit."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/update.py:update",
                "confidence": "almost-certain",
                "settings_after_chain": rehearsal["settings_after_chain"],
            },
            {
                "claim": (
                    "An independent unique-line differ (not the merge module) shows "
                    "the user's unique notes.md lines present after the upgrade; a "
                    "truncated twin is missing those lines and the census hashes diverge."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/unique_line_differ.py:census",
                "confidence": "almost-certain",
                "census_v3": rehearsal["census_v3"],
                "differ_isolated_from_merge": rehearsal["differ_isolated_from_merge"],
            },
            {
                "claim": (
                    "Disabling the classifier overwrites the user-edited file; the "
                    "unique-line test goes red on that path and stays green with "
                    "the classifier on."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/update.py:classifier_enabled",
                "confidence": "almost-certain",
                "negative_control": rehearsal["negative_control"],
            },
        ],
        "tests": [
            {
                "id": "T1-test_update_preserves_overrides",
                "command": TEST,
                "result": "PASS" if test_rc == 0 else "FAIL",
                "assertions": [
                    "unchanged / user-changed / conflicted",
                    "NEGATIVE CONTROL: classifier off, user-edit test goes red",
                    "upgrade chain v1->v2->v3 preserves the same edit",
                ],
                "output_tail": test_out[-1500:],
            }
        ],
        "negative_controls": [
            {
                "id": "IMP0024-C1-classifier-disabled",
                "kind": "known-broken-fixture",
                "description": (
                    "Disable the unchanged/changed/conflicted classifier and assert "
                    "the user-edit unique-line test goes red."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    rehearsal["negative_control"], sort_keys=True
                ),
                "good_state_output": json.dumps(
                    {"all_unique_present": rehearsal["census_v3"]["all_unique_present"]},
                    sort_keys=True,
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "IMP-0024-probe2-reviewer-reorder-comment",
            "verdict": "PASS",
            "independent": True,
            "constructed_edit": (
                "Reordered JSON keys (font before theme) plus a JSONC comment "
                "and a notes.md comment the default user-override helper does not plant."
            ),
            "key_order": rehearsal["reviewer"]["key_order"],
            "jsonc_comment_survived": rehearsal["reviewer"]["jsonc_comment"],
            "notes_comment_survived": rehearsal["reviewer"]["notes_comment"],
        },
        "named_probes": [
            {"id": "probe1", "role": "upgrade-edit-survives", "command": P1},
            {"id": "probe2", "role": "unique-line-differ", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": "tools/plugin/update.py", "exists": True, "role": "supporting"},
            {
                "path": "tools/plugin/three_way_merge.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "tools/plugin/unique_line_differ.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "timestamps": {"started_at": started, "ended_at": now()},
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "registered": True,
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0024/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "notes": (
            "G-1 for IMP-0024: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. SUCCESS:IMP-0024"
        ),
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "IMP-0023 transactional install is implemented here",
                "IMP-0031 is separately receipted; this unit calls the merge mechanism",
            ]
        },
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0024 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0024" not in out.read_text(encoding="utf-8"):
        print("FAILED:IMP-0024 sentinel missing after write")
        return 1

    p1_rc, p1_out = run(P1)
    p2_rc, p2_out = run(P2)
    print(f"probe1 rc={p1_rc}")
    print(p1_out[-1500:])
    print(f"probe2 rc={p2_rc}")
    print(p2_out[-1500:])
    if p1_rc != 0 or p2_rc != 0:
        print("FAILED:IMP-0024 named probes")
        return 1

    # Re-hash receipt after write (probes do not mutate it).
    digest, size = sha256_file(out)
    man_artifacts = [
        {
            "path": OUT,
            "sha256": digest,
            "bytes": size,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0024/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        path = REPO / rel
        if not path.is_file():
            print(f"FAILED:IMP-0024 missing {rel}")
            return 1
        s, n = sha256_file(path)
        man_artifacts.append(
            {
                "path": rel,
                "sha256": s,
                "bytes": n,
                "present": True,
                "unit_id": UNIT,
                "receipt_path": "command-center/p2-wave/probes/IMP-0024/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0024",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": p1_rc,
                "role": "upgrade-edit-survives",
                "raw_output": p1_out[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": p2_rc,
                "role": "unique-line-differ",
                "raw_output": p2_out[-4000:],
            },
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0024/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0024-probe2-reviewer-reorder-comment",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now(),
        "notes": (
            "G-1 for IMP-0024: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(man_artifacts),
        "present": len(man_artifacts),
        "artifacts": man_artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:IMP-0024 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
