#!/usr/bin/env python3
"""Named probe 2: mechanically different from probe 1.

Signal 1: filesystem — path-traversal materialize must not create the escape
canary outside the sandbox (including an absolute-path variant built at runtime).
Signal 2: exit-code inequality — warn (10) is not reject (20).
Signal 3: both-states mutation of the benign control.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from validator import (  # noqa: E402
    EXIT_PASS,
    EXIT_REJECT,
    EXIT_WARN,
    load_registry,
    validate_package,
)

ART = REPO / "command-center/confirmation/CNF-0113-malicious-plugin-fixtures.json"
CANARY_NAME = "CNF-0113-ESCAPE-CANARY.txt"
CANARY_TOKEN = "CNF0113-TRAVERSAL-CANARY-DO-NOT-WRITE"
ABS_NAME = "CNF-0113-ESCAPE-ABS.txt"


def _copy_benign(dst: Path) -> Path:
    src = S.package_dir({"dir": "benign-control"})
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def _rewrite_manifest(pkg: Path, mutator) -> None:
    man_path = pkg / "plugin.json"
    doc = json.loads(man_path.read_text(encoding="utf-8"))
    mutator(doc)
    man_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0113-probe2 confirmation artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    contract = S.domain_get(doc, "exit_code_contract") or {}
    if contract.get("warn") != EXIT_WARN or contract.get("reject") != EXIT_REJECT:
        print("FAILED:CNF-0113-probe2 artifact exit_code_contract mismatch")
        return 1
    if not contract.get("warning_is_not_rejection"):
        print("FAILED:CNF-0113-probe2 warning collapsed into rejection")
        return 1

    registry = load_registry()
    with tempfile.TemporaryDirectory(prefix="cnf0113-p2-") as tmp:
        parent = Path(tmp)
        sandbox = parent / "sandbox"
        sibling = parent / CANARY_NAME
        abs_target = parent / ABS_NAME

        trav = validate_package(
            S.package_dir({"dir": "path-traversal"}),
            registry=registry,
            sandbox=sandbox,
            materialize_files=True,
        )
        if trav["disposition"] != "reject" or trav["firing_rule"] != "MP-PATH-TRAVERSAL":
            print("FAILED:CNF-0113-probe2 path-traversal not rejected", trav)
            return 1
        if sibling.exists():
            print(f"FAILED:CNF-0113-probe2 escape canary written at {sibling}")
            return 1
        if CANARY_TOKEN in sibling.read_text(encoding="utf-8") if sibling.is_file() else "":
            print("FAILED:CNF-0113-probe2 canary token present outside sandbox")
            return 1
        inside = sandbox / "ok.txt"
        if not inside.is_file():
            print("FAILED:CNF-0113-probe2 in-sandbox file was not materialized")
            return 1
        # Walk parent: canary token must not appear outside sandbox.
        leaked = []
        for p in parent.rglob("*"):
            if not p.is_file():
                continue
            try:
                p.relative_to(sandbox)
                continue
            except ValueError:
                pass
            try:
                body = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if CANARY_TOKEN in body:
                leaked.append(str(p))
        if leaked:
            print("FAILED:CNF-0113-probe2 canary leaked", leaked)
            return 1

        # Absolute-path variant authored in the temp tree, not stored in git.
        abs_pkg = parent / "abs-trav"
        abs_pkg.mkdir()
        abs_manifest = {
            "name": "cnf0113-abs-traversal",
            "version": "1.0.0",
            "publisher": {
                "id": "cnf0113-fixtures",
                "signed": True,
                "signature": "ed25519:fixture-not-a-live-key",
            },
            "permissions": ["fs:package-root"],
            "files": [{"path": str(abs_target), "contents": CANARY_TOKEN}],
        }
        (abs_pkg / "plugin.json").write_text(
            json.dumps(abs_manifest, indent=2) + "\n", encoding="utf-8"
        )
        abs_sandbox = parent / "abs-sandbox"
        abs_res = validate_package(
            abs_pkg,
            registry=registry,
            sandbox=abs_sandbox,
            materialize_files=True,
        )
        if abs_res["disposition"] != "reject" or abs_res["firing_rule"] != "MP-PATH-TRAVERSAL":
            print("FAILED:CNF-0113-probe2 absolute traversal not rejected", abs_res)
            return 1
        if abs_target.exists():
            print(f"FAILED:CNF-0113-probe2 absolute escape written at {abs_target}")
            return 1

        unsigned = validate_package(
            S.package_dir({"dir": "unsigned-publisher"}),
            registry=registry,
            sandbox=parent / "unsigned",
            materialize_files=True,
        )
        excessive = validate_package(
            S.package_dir({"dir": "excessive-permissions"}),
            registry=registry,
            sandbox=parent / "excessive",
            materialize_files=True,
        )
        if unsigned["exit_code"] != EXIT_WARN or unsigned["disposition"] != "warn":
            print("FAILED:CNF-0113-probe2 unsigned is not a warning", unsigned)
            return 1
        if excessive["exit_code"] != EXIT_REJECT or excessive["disposition"] != "reject":
            print("FAILED:CNF-0113-probe2 excessive is not a rejection", excessive)
            return 1
        if unsigned["exit_code"] == excessive["exit_code"]:
            print("FAILED:CNF-0113-probe2 warn exit equals reject exit")
            return 1
        if unsigned["firing_rule"] != "MP-UNSIGNED-PUBLISHER":
            print("FAILED:CNF-0113-probe2 unsigned firing_rule", unsigned)
            return 1

        # Both-states: benign pass; add excessive perm -> reject; strip sig -> warn.
        benign_pkg = _copy_benign(parent / "benign-mut")
        good = validate_package(
            benign_pkg, registry=registry, sandbox=parent / "benign-s", materialize_files=True
        )
        if good["disposition"] != "pass" or good["exit_code"] != EXIT_PASS:
            print("FAILED:CNF-0113-probe2 benign baseline did not pass", good)
            return 1

        _rewrite_manifest(
            benign_pkg, lambda m: m.setdefault("permissions", []).append("network:*")
        )
        mutated = validate_package(
            benign_pkg, registry=registry, sandbox=parent / "benign-m", materialize_files=True
        )
        if mutated["disposition"] != "reject" or mutated["firing_rule"] != "MP-PERM-EXCESSIVE":
            print("FAILED:CNF-0113-probe2 perm mutation did not reject", mutated)
            return 1

        benign2 = _copy_benign(parent / "benign-unsigned")
        def strip_sig(m: dict) -> None:
            m["publisher"] = {"id": "ast-harness", "signed": False}

        _rewrite_manifest(benign2, strip_sig)
        stripped = validate_package(
            benign2, registry=registry, sandbox=parent / "benign-u", materialize_files=True
        )
        if stripped["disposition"] != "warn" or stripped["firing_rule"] != "MP-UNSIGNED-PUBLISHER":
            print("FAILED:CNF-0113-probe2 signature strip did not warn", stripped)
            return 1

    print(
        json.dumps(
            {
                "escape_canary_absent": True,
                "absolute_escape_absent": True,
                "in_sandbox_ok_txt": True,
                "warn_exit": EXIT_WARN,
                "reject_exit": EXIT_REJECT,
                "warning_is_not_rejection": True,
                "benign_pass": True,
                "perm_mutation_rejects": True,
                "unsigned_mutation_warns": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0113-probe2 sandbox write-gate and warning/rejection split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
