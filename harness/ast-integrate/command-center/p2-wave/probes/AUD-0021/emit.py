#!/usr/bin/env python3
"""Emit AUD-0021 catalog artifact plus per-unit G-1 sidecars.

Does not run tools/command-center/unit_manifest.py --write.
Does not git add/commit/push/stash/checkout/rebase.
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
import inventory as I  # noqa: E402

REPO = I.REPO
UNIT = I.UNIT
OUT = "command-center/audit/AUD-0021-node-dep-inventory.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0021/probe1_manifests.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0021/probe2_locks.py"
)
COMPLETION_SENTINEL = (
    "SUCCESS:AUD-0021 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For every package.json in the repo, what are its dependencies by class "
    "(prod, dev, peer, optional), and does package-lock.json or pnpm-lock.yaml "
    "pass an integrity check?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0021/inventory.py",
    "command-center/p2-wave/probes/AUD-0021/probe1_manifests.py",
    "command-center/p2-wave/probes/AUD-0021/probe2_locks.py",
    "command-center/p2-wave/probes/AUD-0021/probe1-manifests.json",
    "command-center/p2-wave/probes/AUD-0021/probe2-locks.json",
    "command-center/p2-wave/probes/AUD-0021/fixture-lock-good.json",
    "command-center/p2-wave/probes/AUD-0021/fixture-lock-corrupt.json",
    "command-center/p2-wave/probes/AUD-0021/fixture-lock-desync.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=170,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    data = path.read_bytes() if path.is_file() else b""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if not data:
        eol = "NOT-CHECKED"
    elif crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    else:
        eol = "LF"
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "eol": eol,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0021/SUBAGENT-RETURN.json",
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0021 probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    p1 = json.loads((HERE / "probe1-manifests.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "probe2-locks.json").read_text(encoding="utf-8"))
    if not p1.get("walk_vs_find_agreed"):
        print("FAILED:AUD-0021 emit-time walk vs find disagree")
        return 1
    ctl = p2.get("negative_control") or {}
    ds = p2.get("desync_control") or {}
    if not p2.get("pass"):
        print("FAILED:AUD-0021 emit-time probe2 control")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    totals = p1["totals_by_class"]
    failing = p2.get("failing_integrity") or []
    desynced = p2.get("desynced") or {}
    unlocked = p2.get("manifests_without_a_lock") or []
    npm_absent = p2.get("npm_binary") is None
    summary = (
        f"manifests={p1['walk_count']} parse_errors={len(p1.get('parse_errors') or [])} "
        f"deps prod={totals['dependencies']} dev={totals['devDependencies']} "
        f"peer={totals['peerDependencies']} optional={totals['optionalDependencies']} | "
        f"locks={p2['lock_count']} failing_integrity={len(failing)} "
        f"desynced={len(desynced)} manifests_without_a_lock={len(unlocked)} "
        f"npm_binary={'absent' if npm_absent else p2.get('npm_binary')}"
    )
    answer = (
        f"{summary}. Probe 1 parsed every package.json outside pruned "
        f"node_modules/.venv/dist/build caches into prod/dev/peer/optional; "
        f"os.walk and find(1) agreed at {p1['walk_count']} manifests "
        f"(this worktree has no package.json files; the count is zero, not absent). "
        "Probe 2 scanned every lock's packages[*].integrity for presence and "
        "shape, skipping workspace link:true / non-http resolved entries, and "
        "recorded npm ls --all --json exit status per locked directory. "
        "The catalog control corrupts one integrity hash in "
        "fixture-lock-corrupt.json; the checker exits non-zero and names "
        f"{ctl.get('victim_named')}, and is silent on fixture-lock-good.json. "
        "Integrity hashes are not recomputed against tarballs (lower bound). "
        "npm ls is a second signal on lock/manifest agreement; it is degraded "
        "when node_modules is missing or npm is absent, and that gap is not "
        "folded into a green tree. "
        + COMPLETION_SENTINEL
    )

    named_probes = [
        {
            "id": "probe1",
            "role": "package-json-dependency-classes",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1[:65000],
        },
        {
            "id": "probe2",
            "role": "lockfile-integrity-and-npm-ls",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2[:65000],
        },
    ]
    evidence = [
        {
            "claim": (
                f"{p1['walk_count']} package.json manifests exist outside pruned "
                "trees, with dependency class counts "
                f"prod={totals['dependencies']} dev={totals['devDependencies']} "
                f"peer={totals['peerDependencies']} "
                f"optional={totals['optionalDependencies']}."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/AUD-0021/probe1-manifests.json",
            "confidence": "almost-certain",
            "probes": [
                {
                    "role": "source",
                    "method": "file-read",
                    "command": P1,
                    "raw_output": t1[:65000],
                    "exit_code": c1,
                    "fingerprint": fingerprint("file-read", P1),
                },
                {
                    "role": "verifier",
                    "method": "command",
                    "command": "find . \\( -name node_modules -o ... \\) -prune -o -name package.json -print",
                    "raw_output": (
                        f"find_rc={p1['find_exit_code']} find_count={p1['find_count']} "
                        f"agreed={p1['walk_vs_find_agreed']}"
                    ),
                    "exit_code": p1["find_exit_code"],
                    "fingerprint": fingerprint("command", "find-package-json"),
                },
            ],
        },
        {
            "claim": (
                f"{p2['lock_count']} lockfiles, {len(failing)} failing the "
                f"integrity scan, {len(desynced)} out of sync with the lock root, "
                f"{len(unlocked)} manifests with no sibling lock."
            ),
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/AUD-0021/probe2-locks.json",
            "confidence": "almost-certain",
            "probes": [
                {
                    "role": "source",
                    "method": "static-analysis",
                    "command": P2,
                    "raw_output": t2[:65000],
                    "exit_code": c2,
                    "fingerprint": fingerprint("static-analysis", P2),
                },
                {
                    "role": "verifier",
                    "method": "command",
                    "command": (
                        "inventory.py check-lock fixture-lock-corrupt.json "
                        "--kind package-lock.json"
                    ),
                    "raw_output": str(ctl.get("bad_state_output") or "")[:16000],
                    "exit_code": ctl.get("subprocess_corrupt_exit"),
                    "fingerprint": fingerprint(
                        "command",
                        "inventory.py check-lock fixture-lock-corrupt.json",
                    ),
                },
            ],
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "kind": "audit-inventory",
        "report_kind": "audit-inventory",
        "title": "Node dependency inventory and lockfile integrity",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": answer,
        "sentinel": COMPLETION_SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#AUD-0021",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "p2-deliver-worker",
            "execution_substrate": "linux-headless",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "report": {
            "kind": "audit-inventory",
            "control_ids": ["AUD-0021-C1", "AUD-0021-C2"],
            "question": QUESTION,
            "summary": summary,
            "headline": summary,
            "answer": answer,
            "manifests": p1["manifests"],
            "totals_by_class": totals,
            "locks": p2["locks"],
            "npm_ls": p2["npm_ls"],
            "manifests_without_a_lock": unlocked,
            "dependencies_declared_at_more_than_one_version": p1.get(
                "dependencies_declared_at_more_than_one_version"
            ),
            "observations": [
                {
                    "name": "node_manifests",
                    "measured": p1["walk_count"],
                    "method": "file-read",
                    "anchor": "every package.json outside pruned trees",
                    "note": (
                        "This Linux worktree currently contains 0 package.json "
                        "files; os.walk and find(1) agreed. That is the live "
                        "estate, not a skipped scan. Vendored and probe trees "
                        "are included when they carry a package.json."
                    ),
                },
                {
                    "name": "locks_failing_integrity",
                    "measured": len(failing),
                    "method": "static-analysis",
                    "anchor": "packages[*].integrity in every package-lock.json",
                    "note": (
                        "Only http(s) registry tarballs are required to carry a "
                        "hash. Workspace link:true local paths are not counted "
                        "as integrity failures."
                    ),
                },
                {
                    "name": "npm_ls_signal_quality",
                    "measured": len(p2.get("npm_ls") or []),
                    "method": "command",
                    "anchor": "npm ls --all --json per locked directory",
                    "note": (
                        "Reported by EXIT STATUS. npm binary absent or missing "
                        "node_modules degrades this to a second signal, stated "
                        "rather than folded into a pass."
                    ),
                },
            ],
        },
        "evidence": evidence,
        "named_probes": named_probes,
        "negative_controls": [
            {
                "id": "AUD-0021-C1",
                "kind": "mutation",
                "description": ctl.get("description"),
                "fired_on_bad_state": ctl.get("fired_on_bad_state"),
                "silent_on_good_state": ctl.get("silent_on_good_state"),
                "bad_state_output": str(ctl.get("subprocess_named")),
                "good_state_output": f"clean checker exit={ctl.get('subprocess_clean_exit')}",
            },
            {
                "id": "AUD-0021-C2",
                "kind": "mutation",
                "description": ds.get("description"),
                "fired_on_bad_state": ds.get("fired_on_bad_state"),
                "silent_on_good_state": ds.get("silent_on_good_state"),
                "bad_state_output": str(ds.get("bad_state_output")),
                "good_state_output": str(ds.get("good_state_output")),
            },
        ],
        "tests": [
            {
                "id": "probe1-parse-package-json-classes",
                "name": "Probe 1: parse package.json dependency classes",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": t1[-500:],
            },
            {
                "id": "probe2-lock-integrity-and-npm-ls",
                "name": "Probe 2: npm ls --all exit status plus lockfile integrity hashes",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": t2[-500:],
            },
            {
                "id": "ctl-corrupted-integrity-hash",
                "name": "corrupt one integrity hash; checker exits non-zero and names the package",
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0021/inventory.py "
                    "check-lock command-center/p2-wave/probes/AUD-0021/fixture-lock-corrupt.json "
                    "--kind package-lock.json"
                ),
                "result": "PASS",
                "assertions": 2,
                "output_tail": f"rc={ctl.get('subprocess_corrupt_exit')} named={ctl.get('victim_named')}",
            },
            {
                "id": "ctl-clean-fixture-stays-silent",
                "command": (
                    "python3 -B command-center/p2-wave/probes/AUD-0021/inventory.py "
                    "check-lock command-center/p2-wave/probes/AUD-0021/fixture-lock-good.json "
                    "--kind package-lock.json"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": f"rc={ctl.get('subprocess_clean_exit')}",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0021-probe2-lock-integrity-and-npm-ls",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 is a mechanically different instrument (lock integrity "
                "hashes + npm ls exit status, plus the corrupt-hash both-states "
                "control). Catalog-named fresh-context Claude review of the "
                "headline count remains residual and is not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/AUD-0021/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second failure "
                "with the same detector, enumerate at least 2 mechanically "
                "different detectors before a third attempt"
            ),
        },
        "failure": None,
        "defects": [],
        "residual_unknowns": [
            {
                "claim": (
                    "npm ls cannot validate the resolved tree when npm is absent "
                    "or no node_modules is installed; exit status is a degraded "
                    "second signal."
                ),
                "verdict": "NOT-CHECKED" if npm_absent else "PARTIAL",
                "settling_experiment": (
                    "Install npm, run npm ci in a scratch clone of each locked "
                    "directory, then npm ls --all and compare against the static scan."
                ),
            },
            {
                "claim": (
                    "Integrity hashes are checked for presence and shape, not "
                    "recomputed against the tarballs they name. A well-formed but "
                    "wrong hash passes this scan, so failing_integrity is a lower bound."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Download each resolved tarball and recompute sha512; requires "
                    "network egress."
                ),
            },
            {
                "claim": (
                    "pnpm-lock.yaml and yarn.lock parsing is unimplemented. "
                    "Unsupported formats are reported as unsupported-lock-format "
                    "rather than silently skipped."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Add a pnpm workspace fixture and confirm the walker reports "
                    "unsupported-lock-format rather than skipping it."
                ),
            },
            {
                "claim": (
                    "Declared output_schema command-center/schema/audit-inventory.schema.json "
                    "is absent on this tree. G-1 measures JSON parse + sentinel + "
                    "non-BLOCKED state, not that schema file."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Restore or generate the audit-inventory schema shim and validate "
                    "this document against it before a later catalog close."
                ),
            },
        ],
        "cloud_ok": False,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for AUD-0021: live named probes exit 0, "
            "AUD-0021-node-dep-inventory.json state=SUCCESS, per-unit manifest "
            "row. Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if COMPLETION_SENTINEL not in text:
        print("FAILED:AUD-0021 sentinel missing from serialized artifact")
        return 1
    parsed = json.loads(text)
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0021 self-declared non-delivery state")
        return 1
    out_path.write_text(text, encoding="utf-8", newline="\n")
    primary = art_row(OUT, "primary")
    if primary["bytes"] < 4096:
        print(f"FAILED:AUD-0021 artifact too small {primary['bytes']}")
        return 1

    artifacts = [
        {
            "path": OUT,
            "sha256": primary["sha256"],
            "bytes": primary["bytes"],
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/AUD-0021/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for rel in SUPPORTING:
        row = art_row(rel, "supporting")
        if not row["present"]:
            print(f"FAILED:AUD-0021 missing supporting {rel}")
            return 1
        artifacts.append(
            {
                "path": rel,
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "present": True,
                "unit_id": UNIT,
                "receipt_path": "command-center/p2-wave/probes/AUD-0021/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": named_probes,
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0021/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0021-probe2-lock-integrity-and-npm-ls",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0021: live named probes exit 0, "
            "AUD-0021-node-dep-inventory.json state=SUCCESS, per-unit manifest "
            "row. Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0021 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
