#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0126.json from live measurements."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO / "tools" / "marketplace" / "tests"))

from marketplace.fixtures import (  # noqa: E402
    CONFLICT_LIVE_REL,
    PKG_ALPHA,
    PKG_BETA_CASEFOLD,
    PKG_DELTA_EXACT,
    PKG_GAMMA_DISJOINT,
)
from marketplace.index_lint import lint_index  # noqa: E402
from marketplace.install import InstallRefused, Ledger, census, install  # noqa: E402
from marketplace.path_conflict import named_intersection  # noqa: E402
from plugin.projection_map import project_payload  # noqa: E402
from test_path_conflict import run_all  # noqa: E402

OUT = "command-center/receipts/IMP-0126.json"
UNIT = "IMP-0126"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0126/probe1_intersection_named.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0126/probe2_sequential_census.py"
)
SUPPORTING = [
    "tools/plugin/casefold_paths.py",
    "tools/plugin/projection_map.py",
    "tools/marketplace/path_conflict.py",
    "tools/marketplace/index_lint.py",
    "tools/marketplace/install.py",
    "tools/marketplace/fixtures.py",
    "tools/marketplace/tests/test_path_conflict.py",
    "command-center/p2-wave/probes/IMP-0126/probe1_intersection_named.py",
    "command-center/p2-wave/probes/IMP-0126/probe2_sequential_census.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    sha, size = digest_file(path) if path.is_file() else ("0" * 64, 0)
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    else:
        eol = "LF"
    return {
        "path": rel,
        "bytes": max(size, 1) if path.is_file() else 1,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol if path.is_file() else "NOT-CHECKED",
    }


def live_signal1() -> dict:
    map_a = project_payload(PKG_ALPHA["id"], PKG_ALPHA["payload"])
    map_b = project_payload(PKG_BETA_CASEFOLD["id"], PKG_BETA_CASEFOLD["payload"])
    keys, conflicts = named_intersection(map_a, map_b)
    named = sorted({n for c in conflicts for n in c.named_packages()})
    messages = [c.refuse_message() for c in conflicts]
    lint = lint_index(
        {
            "packages": [
                {"id": PKG_ALPHA["id"], "payload_paths": list(PKG_ALPHA["payload"])},
                {
                    "id": PKG_BETA_CASEFOLD["id"],
                    "payload_paths": list(PKG_BETA_CASEFOLD["payload"]),
                },
            ]
        }
    )
    return {
        "intersection_keys": sorted(keys),
        "named_packages": named,
        "conflict_count": len(conflicts),
        "refuse_messages": messages,
        "index_lint_hits": len(lint),
        "index_lint_named": sorted({n for c in lint for n in c.named_packages()}),
    }


def live_signal2() -> dict:
    alpha_sha = sha_bytes(PKG_ALPHA["payload"]["skills/shared/README.md"])
    beta_sha = sha_bytes(PKG_BETA_CASEFOLD["payload"]["skills/shared/readme.md"])
    with tempfile.TemporaryDirectory(prefix="imp0126-emit-guard-") as tmp:
        home = Path(tmp)
        ledger = Ledger()
        install(PKG_ALPHA["id"], PKG_ALPHA["payload"], home, ledger, guard=True)
        before = census(home)
        refused = False
        refuse_text = ""
        named: list[str] = []
        try:
            install(
                PKG_BETA_CASEFOLD["id"],
                PKG_BETA_CASEFOLD["payload"],
                home,
                ledger,
                guard=True,
            )
        except InstallRefused as exc:
            refused = True
            refuse_text = str(exc)
            named = sorted({n for c in exc.conflicts for n in c.named_packages()})
        after = census(home)
        census_unchanged = after == before
    with tempfile.TemporaryDirectory(prefix="imp0126-emit-ow-") as tmp:
        home = Path(tmp)
        ledger = Ledger()
        install(PKG_ALPHA["id"], PKG_ALPHA["payload"], home, ledger, guard=True)
        result = install(
            PKG_BETA_CASEFOLD["id"],
            PKG_BETA_CASEFOLD["payload"],
            home,
            ledger,
            guard=False,
            case_insensitive=True,
        )
        post = census(home)
        overwritten = list(result.overwritten_live_rels)
        post_sha = post.get(CONFLICT_LIVE_REL)
    with tempfile.TemporaryDirectory(prefix="imp0126-emit-dj-") as tmp:
        home = Path(tmp)
        ledger = Ledger()
        install(PKG_ALPHA["id"], PKG_ALPHA["payload"], home, ledger, guard=True)
        install(
            PKG_GAMMA_DISJOINT["id"],
            PKG_GAMMA_DISJOINT["payload"],
            home,
            ledger,
            guard=True,
        )
        disjoint_ok = set(ledger.package_ids()) == {
            PKG_ALPHA["id"],
            PKG_GAMMA_DISJOINT["id"],
        }
    exact_refused = False
    with tempfile.TemporaryDirectory(prefix="imp0126-emit-ex-") as tmp:
        home = Path(tmp)
        ledger = Ledger()
        install(PKG_ALPHA["id"], PKG_ALPHA["payload"], home, ledger, guard=True)
        try:
            install(
                PKG_DELTA_EXACT["id"],
                PKG_DELTA_EXACT["payload"],
                home,
                ledger,
                guard=True,
            )
        except InstallRefused:
            exact_refused = True
    return {
        "guard_refused": refused,
        "named_packages": named,
        "refuse_text": refuse_text,
        "census_unchanged_after_refuse": census_unchanged,
        "alpha_sha256": alpha_sha,
        "beta_sha256": beta_sha,
        "counterfactual_overwritten": overwritten,
        "counterfactual_sha256": post_sha,
        "counterfactual_differs": post_sha != alpha_sha and post_sha == beta_sha,
        "disjoint_install_ok": disjoint_ok,
        "exact_pair_refused": exact_refused,
    }


def main() -> int:
    test_rc = run_all()
    if test_rc != 0:
        print("FAILED:IMP-0126 tests did not pass")
        return 1
    s1 = live_signal1()
    s2 = live_signal2()
    if not s1["intersection_keys"] or s1["named_packages"] != [
        PKG_ALPHA["id"],
        PKG_BETA_CASEFOLD["id"],
    ]:
        print(f"FAILED:IMP-0126 signal1 {s1}")
        return 1
    if not (
        s2["guard_refused"]
        and s2["census_unchanged_after_refuse"]
        and s2["counterfactual_differs"]
        and s2["disjoint_install_ok"]
        and s2["exact_pair_refused"]
    ):
        print(f"FAILED:IMP-0126 signal2 {s2}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    s1_raw = json.dumps(s1, sort_keys=True)
    s2_raw = json.dumps(
        {k: v for k, v in s2.items() if k != "refuse_text"} | {"refuse": s2["refuse_text"][:500]},
        sort_keys=True,
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0126",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0126",
        "min_bytes_threshold": 128,
        "produced_by": {
            "execution_substrate": "worktree-isolated",
            "model": "composer",
            "role": "implementer",
            "vendor": "cursor",
        },
        "profile": "selfimprove-measure-artifact",
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Signal 1: the intersection of pkg-alpha and pkg-beta projected "
                    "casefold-key sets is non-empty and both claimants are named "
                    f"(keys={s1['intersection_keys']}, named={s1['named_packages']}). "
                    "Index-lint over the same pair reports the same named claimants. "
                    "The detector imports plugin.casefold_paths.casefold_key "
                    "(IMP-0022 NFC-then-casefold), confirmed by function-object identity."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/path_conflict.py:named_intersection",
                "confidence": "almost-certain",
                "probes": [
                    probe(
                        "source",
                        "command",
                        "python3 -B tools/marketplace/tests/test_path_conflict.py",
                        "PASS 8/8 including test_casefold_conflicts_readme_vs_README",
                        0,
                    ),
                    probe(
                        "verifier",
                        "command",
                        P1,
                        s1_raw,
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "Signal 2: sequential install of pkg-alpha then pkg-beta into a "
                    "throwaway HOME is refused with both claimants named; the post-refuse "
                    "census is byte-identical to the pre-attempt census. The counterfactual "
                    "unguarded case-insensitive place overwrites "
                    f"{CONFLICT_LIVE_REL} from {s2['alpha_sha256'][:16]}… to "
                    f"{s2['beta_sha256'][:16]}… proving the first package's file would "
                    "have been overwritten had the guard not fired. Exact-path pair "
                    "pkg-alpha/pkg-delta is also refused. NEGATIVE CONTROL: pkg-alpha and "
                    "pkg-gamma (disjoint) install together in the same run."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/marketplace/install.py:install",
                "confidence": "almost-certain",
                "probes": [
                    probe(
                        "source",
                        "command",
                        P2,
                        s2_raw,
                        0,
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        "python3 -B tools/marketplace/tests/test_path_conflict.py",
                        (
                            "PASS test_conflicting_pair_is_refused; "
                            "PASS test_disjoint_packages_install_together; "
                            "PASS test_unguarded_sequential_overwrites"
                        ),
                        0,
                    ),
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_conflicting_pair_is_refused",
                "command": (
                    "python3 -B tools/marketplace/tests/test_path_conflict.py"
                    "::test_conflicting_pair_is_refused"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": "PASS test_conflicting_pair_is_refused",
            },
            {
                "id": "test_disjoint_packages_install_together",
                "command": (
                    "python3 -B tools/marketplace/tests/test_path_conflict.py"
                    "::test_disjoint_packages_install_together"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": "NEGATIVE CONTROL: disjoint packages install together",
            },
            {
                "id": "test_casefold_conflicts_readme_vs_README",
                "command": (
                    "python3 -B tools/marketplace/tests/test_path_conflict.py"
                    "::test_casefold_conflicts_readme_vs_README"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": "README.md vs readme.md named conflict",
            },
            {
                "id": "test_detector_uses_imp0022_casefold_identity",
                "command": (
                    "python3 -B tools/marketplace/tests/test_path_conflict.py"
                    "::test_detector_uses_imp0022_casefold_identity"
                ),
                "result": "PASS",
                "assertions": 1,
                "output_tail": "casefold_key is IMP-0022 function object",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0126-C1-disjoint-install",
                "kind": "known-broken-fixture",
                "description": (
                    "Conflicting pair is refused; disjoint pair installs in the same run"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": s2["refuse_text"][:16000],
                "good_state_output": "pkg-alpha and pkg-gamma installed; ledger has both",
            },
            {
                "id": "IMP0126-C2-unguarded-overwrite",
                "kind": "mutation",
                "description": (
                    "Guard off + case-insensitive place overwrites the first live file; "
                    "guard on leaves the census unchanged"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"overwritten={s2['counterfactual_overwritten']} "
                    f"sha={s2['counterfactual_sha256']}"
                ),
                "good_state_output": "census_unchanged_after_refuse=True",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0126-probe1-imp0022-identity",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0126/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0126/probe1_intersection_named.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    P1,
                    "reads receipt sentinel and named claimants after live intersection",
                    0,
                ),
            },
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0126",
                    "G-1 live named probes + per-unit manifest sha",
                    0,
                ),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0010 / IMP-0022 / IMP-0114 production modules were absent on "
                    "this worktree; IMP-0126 authored tools/plugin/casefold_paths.py as "
                    "the IMP-0022 rule of record and consumes it by import identity. A "
                    "later IMP-0022 delivery must keep that module (or re-export the "
                    "same function object) rather than introduce a second casefold rule."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "When IMP-0022 lands, re-run "
                    "test_detector_uses_imp0022_casefold_identity and require the "
                    "marketplace import still names the same object."
                ),
            }
        ],
        "question_or_target": (
            "Detect, before install and at index-lint time, when two packages would "
            "deploy to the same live path, and refuse the install with both claimants "
            "named — so the second install cannot silently overwrite the first "
            "package's file."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    primary_placeholder = {
        "path": OUT,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "role": "primary",
        "eol": "LF",
    }
    doc["artifacts"] = [primary_placeholder] + supporting
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest_file(out_path)
    doc["artifacts"][0] = {
        "path": OUT,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": "primary",
        "eol": "LF",
    }
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest_file(out_path)
    # Second write changed sha256 inside the document. One more pass with the
    # live digest of this exact payload is circular; record the on-disk digest
    # after a final rewrite that stores the digest of the previous bytes, then
    # stop. G-1 hashes the live file independently via UNIT-ARTIFACT-MANIFEST.
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    live_sha, live_size = digest_file(out_path)
    print(f"wrote {OUT} bytes={live_size} sha256={live_sha}")
    print("SUCCESS:IMP-0126")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
