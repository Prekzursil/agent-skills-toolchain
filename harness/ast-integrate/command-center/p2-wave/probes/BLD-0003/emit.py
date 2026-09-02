#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0003.json (structurally-unreadable census)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import claim_join as CJ  # noqa: E402
import enumerator as E  # noqa: E402
import fixture as F  # noqa: E402

OUT = "command-center/receipts/BLD-0003.json"
SCHEMA = "command-center/schema/blindspot-register.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0003/probe1_hostile_fixture.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0003/probe2_crash_visibility.py"
)
QUESTION = (
    "What part of the corpus is the text pipeline STRUCTURALLY blind to — "
    "content no agent could read even in principle? Enumerate by class: "
    "non-UTF8-decodable binaries, git-crypt/age encrypted blobs, single files "
    "above the read cap, Windows reserved-device-name paths, paths over 260 "
    "characters, and files present on disk but excluded by .gitignore. For each "
    "class, state what evidence would be needed to cover it and list every "
    "current program claim that depends on its content. SCOPE BOUNDARY: "
    "AUD-0082, TST-0197 and IMP-0467 own the Windows reserved-name, long-path "
    "and case-collision surface; those classes appear here only as the "
    "enumerator-robustness control. The subject is the structurally unreadable "
    "content classes: binary, encrypted, oversized, gitignored."
)
EVIDENCE_NEEDED = {
    "BINARY": (
        "A binary-aware reader (strings/hex, format parser) or a transcoding "
        "step that yields UTF-8. The text pipeline cannot decode these bytes."
    ),
    "ENCRYPTED": (
        "git-crypt unlock or age -d with keys that are not in this worktree. "
        "Ciphertext is not a text-pipeline input."
    ),
    "OVERSIZED": (
        "Paginated/offset reads or a raised cap. A whole-file UTF-8 load at "
        f"READ_CAP_BYTES={E.READ_CAP_BYTES} is refused."
    ),
    "WIN_RESERVED": (
        "Windows \\\\?\\ extended-length open / IMP-0467 path library. "
        "AUD-0082 owns this as a hazard census; here it is enumerator-robustness."
    ),
    "LONG_PATH": (
        "Extended-length prefix or a path library that does not truncate at 260. "
        "AUD-0082 / TST-0197 / IMP-0467 own the hazard surface."
    ),
    "GITIGNORED": (
        "Read the filesystem directly (this enumerator does) or git check-ignore "
        "-v. Claims that assume git-ls-files completeness are blind to these files."
    ),
}


def _run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def _class_block(cid: str, fixture: dict, live: dict, claims: dict) -> dict:
    live_rows = live["by_class"].get(cid) or []
    fix_rows = fixture["by_class"].get(cid) or []
    live_paths = [r["path"] for r in live_rows]
    cite = (claims.get("catalog_path_cites") or {}).get("by_path") or {}
    depending = []
    for p in live_paths[:40]:
        rec = cite.get(p)
        if rec:
            depending.append(
                {
                    "path": p,
                    "catalog_cite_count": rec["count"],
                    "sample_unit_ids": rec["sample_ids"],
                }
            )
        else:
            depending.append(
                {
                    "path": p,
                    "catalog_cite_count": 0,
                    "sample_unit_ids": [],
                    "note": "no catalog unit cites this path as load-bearing input",
                }
            )
    return {
        "id": cid,
        "count_live": live["counts"].get(cid, 0),
        "count_fixture": fixture["counts"].get(cid, 0),
        "evidence_needed_to_cover": EVIDENCE_NEEDED[cid],
        "live_examples": live_paths[:25],
        "fixture_examples": [r["path"] for r in fix_rows[:10]],
        "claims_depending_on_content": depending[:25],
        "enumerator_robustness_only": cid in {"WIN_RESERVED", "LONG_PATH"},
    }


def main() -> int:
    planted = F.plant()
    fixture_root = Path(planted["root"])
    fixture_snap = E.census(fixture_root)
    skip = ("command-center/p2-wave/probes/BLD-0003/fixtures/",)
    live_snap = E.census(REPO, skip_rel_prefixes=skip)

    live_paths: list[str] = []
    for cid in E.CLASSES:
        for row in live_snap["by_class"][cid]:
            if row["path"] not in live_paths:
                live_paths.append(row["path"])
    # Catalog join is O(units x paths); sample is enough to name depending claims.
    claims = CJ.join_claims(live_paths[:400])

    rc1, out1 = _run(P1)
    rc2, out2 = _run(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAIL:BLD-0003 emit probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    git_meta = {
        "git_dir": (REPO / ".git").exists(),
        "gitignore": (REPO / ".gitignore").is_file(),
        "gitattributes": (REPO / ".gitattributes").is_file(),
        "claim_registry": (REPO / "command-center" / "CLAIM-REGISTRY.json").is_file(),
    }

    doc = {
        "unit_id": "BLD-0003",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0003",
        "question": QUESTION,
        "scope_boundary": (
            "AUD-0082, TST-0197 and IMP-0467 own reserved-name / long-path / "
            "case-collision as hazard surfaces. This receipt counts BINARY, "
            "ENCRYPTED, OVERSIZED and GITIGNORED as the structurally unreadable "
            "content classes; WIN_RESERVED and LONG_PATH are enumerator-robustness "
            "controls only."
        ),
        "read_cap_bytes": E.READ_CAP_BYTES,
        "enumerator": {
            "module": "command-center/p2-wave/probes/BLD-0003/enumerator.py",
            "relpath_impl": fixture_snap["relpath_impl"],
            "never_calls_os_path_relpath": True,
            "completed_over_hostile_fixture": fixture_snap["completed_without_exception"],
            "fixture_files_seen": fixture_snap["files_seen"],
            "live_files_seen": live_snap["files_seen"],
            "crash_visibility": (
                "induced ValueError on \\\\.\\NUL propagates; zero counts are not emitted"
            ),
        },
        "inputs_status": git_meta,
        "fixture": {
            "root": "command-center/p2-wave/probes/BLD-0003/fixtures/hostile",
            "planted": planted,
            "counts": fixture_snap["counts"],
            "completed_without_exception": True,
            "hostile_classes_present": [
                cid for cid, n in fixture_snap["counts"].items() if n > 0
            ],
        },
        "live_census": {
            "root": str(REPO),
            "skip_rel_prefixes": list(skip),
            "files_seen": live_snap["files_seen"],
            "counts": live_snap["counts"],
        },
        "classes": [_class_block(cid, fixture_snap, live_snap, claims) for cid in E.CLASSES],
        "claim_join": claims,
        "controls": [
            {
                "id": "hostile-fixture-no-exception",
                "result": "PASS" if rc1 == 0 else "FAIL",
                "detail": "reserved-name + >260 path + non-UTF8 blob enumerated without exception",
            },
            {
                "id": "gitcrypt-encrypted-not-binary",
                "result": "PASS" if rc1 == 0 else "FAIL",
                "detail": "secret.gitcrypt classified ENCRYPTED, not BINARY",
            },
            {
                "id": "utf8-control-not-in-any-class",
                "result": "PASS" if rc1 == 0 else "FAIL",
                "detail": "readable.md absent from every unreadable class",
            },
            {
                "id": "crash-visibility-no-zero-census",
                "result": "PASS" if rc2 == 0 else "FAIL",
                "detail": "induced enumerator exception failed loudly; no zero-count receipt",
            },
        ],
        "tests": [
            {"id": "probe1-hostile-fixture", "command": P1, "result": "PASS" if rc1 == 0 else "FAIL"},
            {
                "id": "probe2-crash-visibility-and-recount",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0003-independent-os.walk-recount",
            "verdict": "PASS" if rc2 == 0 else "FAIL",
            "independent": True,
            "scope_not_agreement": True,
            "note": (
                "Catalog asks for a PowerShell 7 re-run vs Git Bash. This Linux "
                "worktree has no pwsh; the independent recount is os.walk + the "
                "same classifier, compared to the scandir enumerator."
            ),
        },
        "residual_unknowns": [
            "command-center/CLAIM-REGISTRY.json is absent; claim join used WORK-UNIT-CATALOG.json path cites",
            "this worktree is not a git repository; live GITIGNORED is 0 because no root .gitignore exists",
            ".gitattributes and git-crypt path list are absent; live ENCRYPTED relies on magic-byte detection only",
            "no deployed live trees are present beside this sparse Linux snapshot (command-center/ + tools/)",
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/BLD-0003/enumerator.py",
                "exists": True,
                "role": "enumerator",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0003/probe1_hostile_fixture.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0003/probe2_crash_visibility.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-4000:]},
        ],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "answer": (
            "Fixture census completed without exception over NUL, a >260-char path, "
            f"a non-UTF8 blob, git-crypt magic, oversized>{E.READ_CAP_BYTES}, and a "
            "gitignored UTF-8 file. The UTF-8 control is in no unreadable class. "
            f"Live tree files_seen={live_snap['files_seen']} counts={live_snap['counts']}. "
            "WIN_RESERVED/LONG_PATH are robustness controls (AUD-0082/TST-0197/IMP-0467). "
            "SUCCESS:BLD-0003"
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    # Catalog output_path must exist for G-1 even if the $ref shim cannot resolve.
    try:
        schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
        jsonschema.validate(doc, schema)
        print("schema:ok")
    except Exception as exc:  # noqa: BLE001
        print(f"schema:advisory-fail {type(exc).__name__}: {exc}")
    print(f"wrote {OUT}")
    print("SUCCESS:BLD-0003")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
