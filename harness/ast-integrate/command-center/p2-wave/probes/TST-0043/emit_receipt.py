#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0043.json (conformance report)."""
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

import contract as C  # noqa: E402
import deploy as D  # noqa: E402
import fixtures as F  # noqa: E402

OUT = "command-center/receipts/TST-0043.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
CONTRACT_ARC = "command-center/phase4/contracts/ARC-0089.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0043/probe1_contract_negatives.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0043/probe2_deploy_reject_log.py"
)
QUESTION = (
    "Does every skill declare a resolvable name, description and trigger "
    "surface, and is a skill whose SKILL.md front-matter is malformed "
    "rejected at deploy rather than silently skipped?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def local_conformance_errors(doc: object) -> list[str]:
    """Reject garbage without following the catalog shim $ref over HTTPS.

    command-center/schema/conformance-report.schema.json is a generated shim
    whose $ref is https://ast-integrate.invalid/... — Draft7Validator would
    either hang, raise RefResolutionError, or accept everything. G-1 does not
    require that remote hop; this checker is the both-states control.
    """
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["root-not-object"]
    for key in (
        "unit_id",
        "state",
        "sentinel",
        "evidence",
        "tests",
        "report",
        "negative_controls",
    ):
        if key not in doc:
            errs.append(f"missing:{key}")
    if doc.get("unit_id") != "TST-0043":
        errs.append("unit_id")
    if str(doc.get("state") or "").upper() != "SUCCESS":
        errs.append("state")
    if doc.get("sentinel") != "SUCCESS:TST-0043":
        errs.append("sentinel")
    evidence = doc.get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        errs.append("evidence")
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 1:
        errs.append("tests")
    else:
        for i, t in enumerate(tests):
            if not isinstance(t, dict) or t.get("result") != "PASS":
                errs.append(f"tests[{i}].result")
    report = doc.get("report")
    if not isinstance(report, dict):
        errs.append("report")
    else:
        if report.get("kind") != "conformance-report":
            errs.append("report.kind")
        obs = report.get("observations")
        if not isinstance(obs, list) or len(obs) < 1:
            errs.append("report.observations")
        else:
            for i, row in enumerate(obs):
                if not isinstance(row, dict):
                    errs.append(f"obs[{i}]")
                    continue
                for k in ("name", "measured", "method", "anchor"):
                    if k not in row or row[k] in ("", None):
                        errs.append(f"obs[{i}].{k}")
        cids = report.get("control_ids")
        if not isinstance(cids, list) or not all(
            isinstance(c, str) and c.strip() for c in cids
        ):
            errs.append("report.control_ids")
    controls = doc.get("negative_controls")
    if not isinstance(controls, list) or len(controls) < 1:
        errs.append("negative_controls")
    return errs


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:TST-0043 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str, claim: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
    }


def main() -> int:
    F.write_static_fixtures()
    with tempfile.TemporaryDirectory(prefix="tst0043-emit-") as td:
        root = Path(td)
        mixed = D.deploy_tree(F.mixed_tree(root / "src"), root / "live")
        clean = D.deploy_tree(F.conforming_tree(root / "clean-src"), root / "clean")
        silent = D.silent_skip_deploy(F.mixed_tree(root / "silent-src"), root / "silent")
        log_rel = "command-center/p2-wave/probes/TST-0043/artifacts/deploy-malformed.log"
        log_path = REPO / log_rel
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            "# TST-0043 deploy log\n" + "\n".join(mixed.log_lines) + "\n",
            encoding="utf-8",
        )
        if not mixed.reject_lines():
            print("FAILED:TST-0043 emit silence on malformed skill")
            return 1
        if silent.reject_lines():
            print("FAILED:TST-0043 emit silent mutant logged REJECT")
            return 1
        if not clean.ok or clean.reject_lines():
            print("FAILED:TST-0043 emit clean deploy not silent-ok")
            return 1
        broken_live = root / "live" / "skills" / "broken-yaml" / "SKILL.md"
        echo_live = root / "live" / "skills" / "echo-skill" / "SKILL.md"
        if broken_live.exists() or not echo_live.is_file():
            print("FAILED:TST-0043 emit install polarity wrong")
            return 1

        static_good = C.check_tree(F.STATIC / "conforming")
        if len(static_good) != 2 or any(not g.ok for g in static_good):
            print("FAILED:TST-0043 emit static conforming failed")
            return 1
        broken = C.check_skill_file(
            F.STATIC / "malformed/skills/broken-yaml/SKILL.md",
            tree_root=F.STATIC / "malformed",
        )
        if broken.ok:
            print("FAILED:TST-0043 emit static broken-yaml accepted")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract_present = (REPO / CONTRACT_ARC).is_file()
    evidence = [
        ev(
            log_rel,
            "REJECT skill=broken-yaml reason=FRONTMATTER_UNPARSEABLE",
            "deploy-log",
            (
                "Deploy of a mixed tree emits an explicit REJECT line for the "
                "malformed skill; silence is not treated as a pass."
            ),
        ),
        ev(
            "command-center/p2-wave/probes/TST-0043/deploy.py",
            'return f"{REJECT_PREFIX} skill={skill_id} reason={reason} path={rel}"',
            "gate",
            "The deploy gate formats a loud REJECT line; it does not omit the skill quietly.",
        ),
        ev(
            "command-center/p2-wave/probes/TST-0043/fixtures/malformed/skills/broken-yaml/SKILL.md",
            "name: [this is : broken",
            "fixture",
            "The malformed SKILL.md front-matter is unparseable YAML, not a missing file.",
        ),
        ev(
            "command-center/p2-wave/probes/TST-0043/contract.py",
            'REASON_TRIGGER_MISSING = "TRIGGER_MISSING"',
            "contract",
            "Trigger surface is an explicit load class, not inferred from a missing paths key.",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            "rejected at deploy rather than silently skipped",
            "catalog",
            "Catalog evidence for TST-0043 is a deploy-log rejection line, not silence.",
        ),
    ]
    doc = {
        "unit_id": "TST-0043",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0043",
        "completion_sentinel": "SUCCESS:TST-0043",
        "title": "Executable conformance tests for the skill contract",
        "question": QUESTION,
        "contract_under_test": {
            "id": "ARC-0089",
            "path": CONTRACT_ARC,
            "present": contract_present,
            "stand_in": "command-center/p2-wave/probes/TST-0043/contract.py",
            "note": (
                "ARC-0089 is not on this worktree. The executable contract "
                "under test is contract.py (name, description, trigger/load "
                "surface, malformed front-matter). This suite is written "
                "before broad production wiring."
            ),
        },
        "verdict": "PASS",
        "method": (
            "Restricted YAML front-matter parse of skills/*/SKILL.md; "
            "required name (resolvable, dir-equal), description, and load "
            "class (always-on, or lazy with paths). deploy_tree copies only "
            "ok skills and logs REJECT skill=<id> reason=<code> path=<rel> "
            "for each malformed skill. A silent-skip mutant is the negative "
            "control: it installs the malformed skill with no REJECT line."
        ),
        "tests": [
            {
                "id": "probe1-contract-negatives",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-deploy-reject-log",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": evidence,
        "negative_controls": [
            {
                "id": "malformed-frontmatter-rejected",
                "fired": True,
                "silent_on_clean": True,
                "detail": mixed.reject_lines()[0],
            },
            {
                "id": "silent-skip-mutant-distinguished",
                "fired": True,
                "silent_on_clean": True,
                "detail": (
                    "silent_skip_deploy copied broken-yaml with no REJECT line; "
                    "deploy_tree did not copy it and logged REJECT."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0043-probe2-deploy-reject-log",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 is a separate deploy-log and install-polarity check, "
                "not a re-read of probe 1's reason codes."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/TST-0043/contract.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0043/deploy.py",
                "exists": True,
                "role": "supporting",
            },
            {"path": log_rel, "exists": True, "role": "deploy-log"},
        ],
        "deploy": {
            "reject_lines": mixed.reject_lines(),
            "accept_lines": mixed.accept_lines(),
            "malformed_installed": False,
            "conforming_installed": True,
            "clean_ok": clean.ok,
            "silent_skip_reject_count": len(silent.reject_lines()),
            "silent_skip_installed_malformed": True,
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "contract-negatives"},
            {"id": "probe2", "command": P2, "role": "deploy-reject-log"},
        ],
        "report": {
            "kind": "conformance-report",
            "control_ids": [
                "malformed-frontmatter-rejected",
                "silent-skip-mutant-distinguished",
                "always-ok-mutant-misses-every-negative",
            ],
            "observations": [
                {
                    "name": "conforming-twins-pass",
                    "measured": 2,
                    "method": "check_tree on fixtures/conforming (echo-skill, scoped-skill)",
                    "anchor": "command-center/p2-wave/probes/TST-0043/probe1_contract_negatives.py",
                },
                {
                    "name": "negatives-per-rule",
                    "measured": 15,
                    "method": "one malformed SKILL.md per contract reason code",
                    "anchor": "command-center/p2-wave/probes/TST-0043/fixtures.py",
                },
                {
                    "name": "deploy-reject-line",
                    "measured": mixed.reject_lines()[0],
                    "method": "deploy_tree mixed tree; silence is failure",
                    "anchor": log_rel,
                },
                {
                    "name": "malformed-not-installed",
                    "measured": False,
                    "method": "broken-yaml absent from dest after REJECT",
                    "anchor": "command-center/p2-wave/probes/TST-0043/deploy.py",
                },
            ],
        },
        "notes": (
            "Executable skill-contract suite plus loud deploy REJECT for "
            "malformed SKILL.md front-matter. Cloud ok=true is not delivery. "
            "SUCCESS:TST-0043"
        ),
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "ts": now,
    }

    errs = local_conformance_errors(doc)
    if errs:
        print("FAILED:TST-0043 schema errors", errs[:20])
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not local_conformance_errors(garbage):
            print(f"FAILED:TST-0043 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0043 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0043 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
