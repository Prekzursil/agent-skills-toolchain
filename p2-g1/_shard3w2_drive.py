#!/usr/bin/env python3
"""Shard3 wave-2 driver: probes -> manifest -> SUBAGENT-RETURN -> measure.

Per unit: run probe1 (must exit 0) -> write UNIT-ARTIFACT-MANIFEST.json
(LF-normalized sha of the live artifact) -> run probe2 (must exit 0; it
byte-compares nothing itself, but the manifest row is what _measure_one_delivered
byte-compares) -> write SUBAGENT-RETURN.json (status DELIVERED, named probes
with exit codes, failure classification reviewer-absent) -> run
command-center/p2-wave/_measure_one_delivered.py (must print SUCCESS).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
UNITS = {
    "ARC-0056": "command-center/phase3/A8/MIGRATION.json",
    "ARC-0076": "command-center/phase3/VERDICT-STABILITY.json",
    "AUD-0005": "command-center/audit/AUD-0005-tag-release-parity.json",
    "AUD-0008": "command-center/audit/AUD-0008-commit-authorship-integrity.json",
    "AUD-0026": "command-center/audit/AUD-0026-runtime-vs-dev-split.json",
    "AUD-0032": "command-center/audit/AUD-0032-dead-code-census.json",
    "AUD-0042": "command-center/audit/AUD-0042-close-baseline-ci-gap.json",
}
PROBES = {
    "ARC-0056": ("probe1_totality.py", "probe2_alias_roundtrip.py"),
    "ARC-0076": ("probe1_order_effect.py", "probe2_independence_and_weak.py"),
    "AUD-0005": ("probe1_tag_deref.py", "probe2_release_assets.py"),
    "AUD-0008": ("probe1_ancestor.py", "probe2_path_surface.py"),
    "AUD-0026": ("probe1_declared_split.py", "probe2_shipped_import_graph.py"),
    "AUD-0032": ("probe1_ast_refs.py", "probe2_dynamic_reach.py"),
    "AUD-0042": ("probe1_exit_codes.py", "probe2_result_summaries.py"),
}
NOTES = {
    "ARC-0056": (
        "Resume 2026-10-25: prior builder's artifact verified against the live contract, not "
        "rebuilt. probe1 re-derives disposition totality (21 enumerated == 4+9+5+3, disjoint, "
        "zero gaps; alias/deprecation/removal rows agree with dispositions; tamper control "
        "fires). probe2 re-derives alias round-trip (9 aliases forward+reverse, removed "
        "do-not-resolve, unknown-name control fires); on-disk resolution arm recorded "
        "instrument-absent (fixtures/live lost with the prior builder's tree). No owner gate "
        "(owner_approval_required=false)."
    ),
    "ARC-0076": (
        "Resume 2026-10-25: prior builder's artifact verified, not rebuilt. probe1 re-derives "
        "the order-effect control from the replay table (23+12=35; 22/23, 12/12, 34/35; exact-"
        "ordered top-three 23/35; primacy 1.575 == zero-merit WEAK-X front-minus-end placement "
        "delta; WEAK-X never wins 6/6). Method-text observation recorded (slot-means delta "
        "2.765884 vs recorded primacy 1.575; the number reproduces exactly via the weak-entry "
        "delta). probe2 re-derives panel independence (disjoint seats, differing orders, same "
        "entry set, checked-before-results; rubric pre-registered with sha256; identical-config "
        "determinism; synthetic all-zero winner caught). No owner gate."
    ),
    "AUD-0005": (
        "Resume 2026-10-25: prior builder's artifact verified, not rebuilt. probe1 rebuilds the "
        "git fixture control-repo in a temp dir and re-proves `git rev-list -n 1 <tag>` (caret "
        "form forbidden): 2 annotated tags LIVE, registry-only orphan DEAD; artifact rows "
        "consistent with tallies (probe1_dead=0; LIVE rows carry 40-hex commits); planted "
        "control independent (probe1 LIVE / probe2 DEAD). probe2 rebuilds the release-store "
        "fixture: LIVE iff published with non-zero asset bytes; zero-byte asset, unpublished, "
        "and absent-row are DEAD (3/4) matching tallies. Live GitHub arm recorded NOT-CHECKED. "
        "Drift note: artifact records worktree_is_git=true; current tree is not a git repo, so "
        "the rebuilt fixture census is the discriminating instrument. No owner gate."
    ),
    "AUD-0008": (
        "Resume 2026-10-25: prior builder's artifact verified, not rebuilt. probe1 rebuilds the "
        "fixture repo and re-proves merge-base --is-ancestor: GREEN on a legitimate owner "
        "scratch commit, RED after a commit-tree orphan rewrite, equality strawman RED on the "
        "scratch (recorded probe1_control agrees); live catalog recount 2007 == recorded "
        "catalog_unit_id_count. probe2 re-derives the changed-path classifier: owner-forged "
        "commit paths carry AUD-0008 -> UNIT-CORROBORATED; agent-forged paths unit-free -> "
        "NO-UNIT-SURFACE; look-alikes (aud-0008, AUD-00086) do not over-match; identity never "
        "decides. Drift note: artifact cites the prior builder's POSIX worktree path. No owner "
        "gate."
    ),
    "AUD-0026": (
        "Resume 2026-10-25: prior builder's artifact verified, not rebuilt. probe1 re-derives "
        "the manifest census live (tools/plugin has no pyproject/package.json/setup.py -> "
        "manifest_absent, consumer_forced=[]) and re-proves the shippable classifier both-states "
        "in a temp fixture (shipped-dev import fires, test-dev silent, declared-runtime silent, "
        "filter-off fires -> filter load-bearing). LIVE DRIFT recorded with both numbers: the "
        "point-in-time census recorded tools/plugin/census.py -> harness_walker; live census.py "
        "imports stdlib only while tools/harness_walker/ still exists; live AST scan finds 14 "
        "repo-sibling import rows vs recorded 1 (probe2). The reviewer must adjudicate the "
        "drifted arm with both numbers. No owner gate."
    ),
    "AUD-0032": (
        "Resume 2026-10-25: prior builder's artifact verified, not rebuilt. probe1 rebuilds the "
        "aud0032_fx control fixture in a temp dir and re-proves the recorded verdict matrix on "
        "it (entry/live_mod LIVE via test-consumer imports; plugin_only DEAD on AST; "
        "mention_only/truly_dead/__init__ DEAD), plus tallies partition arithmetic "
        "(347+267-2*226=162 disagree; 486+6=492). probe2 re-proves dynamic reachability: "
        "plugin_only LIVE via the string-named plugin registry and DEAD under the string-edge "
        "strawman; a non-README doc mention is NOT a reference source. Original fixture "
        "directory was lost with the prior builder's tree; recorded as instrument-absent, "
        "reproved on an equivalent rebuilt fixture. No owner gate."
    ),
    "AUD-0042": (
        "Resume 2026-10-25: prior builder's artifact verified, not rebuilt. probe1 re-derives "
        "the 32-row gap census (18 tests-ran / 10 target-absent / 3 collected-zero / 1 "
        "isolation-ran; success == exit-0 AND collected>0 AND tests-ran for every row; "
        "collected-zero rows carry pytest exit 5; headline 21 present / 16 counted / 746 "
        "collected recomputes; 10 worktree-never-CI rows same shape). probe2 re-derives summary "
        "arithmetic (passed+failed+errored <= collected on all 28 tests-ran rows incl. "
        "worktree; exit-0 implies no failures) and re-proves the parser live with pytest "
        "8.4.2 (zero-collect rc5 not success; one-test rc0 counts). Drift note: runs/raw logs "
        "were lost with the prior builder's tree; recorded as instrument-absent. declared_"
        "schema_probe honestly recorded ref-resolution failure (offline). No owner gate."
    ),
}


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), timeout=3600)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def main() -> int:
    ids = sys.argv[1:] or list(UNITS)
    bad: list[str] = []
    for uid in ids:
        out_rel = UNITS[uid]
        p1_name, p2_name = PROBES[uid]
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        p1, p2 = pdir / p1_name, pdir / p2_name

        rc1, out1 = run([sys.executable, "-B", p1.relative_to(REPO).as_posix()])
        if rc1 != 0:
            print(f"{uid} probe1 rc={rc1}: {out1[-300:]}")
            bad.append(uid)
            continue

        raw = (REPO / out_rel).read_bytes()
        norm = raw.replace(b"\r\n", b"\n")
        sha = hashlib.sha256(norm).hexdigest()
        rows = [
            {
                "unit_id": uid,
                "path": out_rel,
                "bytes": len(norm),
                "sha256": sha,
                "exists": True,
                "eol": "LF",
                "role": "primary",
                "present": True,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            },
            {
                "unit_id": uid,
                "path": f"command-center/p2-wave/probes/{uid}/{p1_name}",
                "bytes": p1.stat().st_size,
                "sha256": hashlib.sha256(p1.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "exists": True,
                "eol": "LF",
                "role": "supporting",
                "present": True,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            },
            {
                "unit_id": uid,
                "path": f"command-center/p2-wave/probes/{uid}/{p2_name}",
                "bytes": p2.stat().st_size,
                "sha256": hashlib.sha256(p2.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "exists": True,
                "eol": "LF",
                "role": "supporting",
                "present": True,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
            },
        ]
        (pdir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "contract": "completion-predicate-condition-11-unit-artifact-registration",
                    "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
                    "unit_id": uid,
                    "artifacts": rows,
                    "present": len(rows),
                    "expected": len(rows),
                    "verified_on_disk": True,
                },
                indent=1,
            ),
            encoding="utf-8",
            newline="\n",
        )

        rc2, out2 = run([sys.executable, "-B", p2.relative_to(REPO).as_posix()])
        if rc2 != 0:
            print(f"{uid} probe2 rc={rc2}: {out2[-400:]}")
            bad.append(uid)
            continue

        cmds = [
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p1.relative_to(REPO).as_posix()}",
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {p2.relative_to(REPO).as_posix()}",
        ]
        ret = {
            "id": uid,
            "unit_id": uid,
            "status": "DELIVERED",
            "state": "BLOCKED",
            "sentinel": (
                f"FAILED:{uid} builder-side delivery COMPLETE (artifact + live probes + manifest "
                "sha verified); SUCCESS withheld: reviewer-absent, independent closure pending"
            ),
            "output_path": out_rel,
            "named_probes": [
                {"id": "probe1", "command": cmds[0], "exit_code": rc1,
                 "role": "delivery-predicate", "raw_output": out1[:8000]},
                {"id": "probe2", "command": cmds[1], "exit_code": rc2,
                 "role": "independent-recheck", "raw_output": out2[:8000]},
            ],
            "artifacts": [{"path": out_rel, "bytes": len(norm), "sha256": sha,
                           "exists": True, "role": "primary"}],
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
            "failure": {
                "classification": ["reviewer-absent"],
                "reason": (
                    "Independent reviewer closure unavailable in builder shard; artifact + "
                    "named probes + manifest sha all verify live this session."
                ),
            },
            "notes": NOTES[uid],
            "extensions": {
                "builder": "shard3 wave-2 (resume) 2026-10-25",
                "prior_builder": "died mid-flight; artifacts verified against the live "
                                 "contract, not rebuilt",
            },
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        (pdir / "SUBAGENT-RETURN.json").write_text(
            json.dumps(ret, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n"
        )

        mrc, mout = run([sys.executable, "command-center/p2-wave/_measure_one_delivered.py", uid])
        tail = mout.strip().splitlines()[-1] if mout.strip() else ""
        print(f"{uid}: measure rc={mrc} {tail}")
        if mrc != 0:
            bad.append(uid)
    if bad:
        print("NOT-GREEN:", ",".join(bad))
        return 1
    print("ALL-GREEN:", ",".join(ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
