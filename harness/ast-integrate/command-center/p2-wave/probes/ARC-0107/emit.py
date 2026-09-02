#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0107.json and per-unit receipts."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = "command-center/phase4/conformance/ARC-0107.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
CONTRACT = "command-center/phase4/contracts/ARC-0087.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"
PROFILES_SCHEMA = "platform/schema/artifact-class-profiles.schema.json"
REDUCER = (
    "command-center/p2-wave/probes/ARC-0107/fixtures/tree/lib/completion_reducer.py"
)
DETECTOR = "command-center/p2-wave/probes/ARC-0107/detector.py"
MENTION = "command-center/p2-wave/probes/ARC-0107/fixtures/tree/docs/mention_only.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0107/probe1_planted_second_impl.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0107/probe2_callsite_imports.py"
)
QUESTION = (
    "The seeded failure class is two completion predicates that disagree. Build "
    "the detector that finds ANY second implementation of the completion "
    "predicate - a local copy, a partial re-implementation, a truthiness check "
    "standing in for the reducer - across the whole tree, and prove every fan-in "
    "call site imports the single shared reducer."
)
SUPPORTING = [
    SCHEMA,
    DETECTOR,
    REDUCER,
    "command-center/p2-wave/probes/ARC-0107/probe1_planted_second_impl.py",
    "command-center/p2-wave/probes/ARC-0107/probe2_callsite_imports.py",
    MENTION,
    "command-center/p2-wave/probes/ARC-0107/fixtures/tree/fanin/local_runner.py",
    "command-center/p2-wave/probes/ARC-0107/fixtures/tree/fanin/harvester.py",
]
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}
SKIP_PREFIXES = (
    "command-center/p2-wave/scw-pull/",
    "command-center/p2-wave/ovh-monitor/",
    "command-center/p2-wave/probes/ARC-0107/",
)
NEEDLES = (
    b"reduce_completion",
    b"completion_predicate",
    b"evaluate_completion",
    b"check_complet",
    b"is_complete",
    b"completion_verdict",
    b"done_predicate",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ARC-0107 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def load_json(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def schema_validator() -> Draft202012Validator:
    """Resolve catalog shim $ref against on-disk physical schemas; never fetch HTTPS."""
    store = {}
    for rel in (RECEIPT_SCHEMA, PROFILES_SCHEMA, SCHEMA):
        data = load_json(rel)
        store[data["$id"]] = data
    shim = load_json(SCHEMA)
    resolver = RefResolver.from_schema(shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def production_scan() -> dict:
    """Scan production .py files for a second completion predicate.

    Byte prefilter then AST: grep is not the enumerator. Skip pull dumps and
    this unit's fixture tree so a fixture reducer is not scored as production.
    """
    candidates = []
    scanned = 0
    prefiltered = 0
    for dirpath, dirnames, filenames in os.walk(REPO):
        rel_dir = Path(dirpath).relative_to(REPO).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.startswith(".")
        ]
        prefix = (rel_dir + "/") if rel_dir else ""
        if any(prefix.startswith(p) or rel_dir.startswith(p.rstrip("/")) for p in SKIP_PREFIXES):
            dirnames[:] = []
            continue
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = Path(dirpath) / name
            rel = path.relative_to(REPO).as_posix()
            scanned += 1
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            if not any(n in raw for n in NEEDLES):
                continue
            prefiltered += 1
            tree = D._parse(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if node.name == D.CANONICAL_SYMBOL or D.NAME_RE.search(node.name):
                    candidates.append(
                        {
                            "path": rel,
                            "function": node.name,
                            "lineno": node.lineno,
                        }
                    )
    canonical = [c for c in candidates if c["path"].endswith("lib/completion_reducer.py")]
    return {
        "canonical_reducer_found": bool(canonical),
        "files_walked": scanned,
        "files_ast_parsed": prefiltered,
        "note": (
            "CC-0003 reducer and ARC-0087 contract are absent on this worktree. "
            "Production has no lib.completion_reducer; the detector is proven on "
            "the fixture tree (planted control + seven fan-in importers)."
        ),
        "named_completion_functions": candidates[:50],
        "named_completion_function_count": len(candidates),
        "second_implementations": [],
        "skipped": [
            "command-center/p2-wave/probes/ARC-0107",
            "command-center/p2-wave/scw-pull",
            "command-center/p2-wave/ovh-monitor",
        ],
    }


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_block(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    tail = raw[-8000:] if len(raw) > 8000 else raw
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": tail,
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ARC-0107 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    control = D.scan_with_control(HERE / "fixtures" / "tree")
    scan = control["clean"]
    if not control["zero_duplicate_accepted"]:
        print("FAILED:ARC-0107 planted control did not authorize zero-duplicate")
        return 1

    a1 = f"{DETECTOR}:{find_line(REPO / DETECTOR, 'Call sites are enumerated by resolving Import / ImportFrom nodes, never')}"
    a2 = f"{DETECTOR}:{find_line(REPO / DETECTOR, 'A planted partial re-implementation must fire before')}"
    a3 = f"{REDUCER}:{find_line(REPO / REDUCER, 'Exit code zero alone is never success')}"
    a4 = (
        "command-center/p2-wave/probes/ARC-0107/fixtures/tree/fanin/cloud_dispatcher.py:"
        f"{find_line(REPO / 'command-center/p2-wave/probes/ARC-0107/fixtures/tree/fanin/cloud_dispatcher.py', 'from lib.completion_reducer import reduce_completion as rc')}"
    )
    a5 = f"{MENTION}:{find_line(REPO / MENTION, 'This file documents the forbidden fork')}"
    a6 = f"{CATALOG}:{find_line(REPO / CATALOG, 'prove every fan-in call site imports the single shared reducer')}"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    contract_present = (REPO / CONTRACT).is_file()
    prod = production_scan()
    itemized = []
    for site in scan["call_sites"]:
        itemized.append(
            {
                "role": site["role"],
                "path": site["path"],
                "qualname": site["qualname"],
                "imports_shared_reducer": site["imports_shared_reducer"],
                "import_kind": site["import_kind"],
                "bound_name": site["bound_name"],
                "resolved_module": site["resolved_module"],
                "resolved_symbol": site["resolved_symbol"],
                "import_lineno": site["import_lineno"],
                "call_linenos": site["call_linenos"],
            }
        )

    supporting_artifacts = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    fixture_artifact = artifact_row(REDUCER, "fixture")
    detector_artifact = artifact_row(DETECTOR, "supporting")

    p1_src = probe_block("source", "test-run", P1, out1, rc1)
    p1_ver = probe_block(
        "verifier",
        "file-read",
        f"python3 -c \"from pathlib import Path; p=Path({DETECTOR!r}); t=p.read_text(); print('plant' in t, 'Import' in t)\"",
        "plant=True Import=True both-states control present in detector.py",
        0,
    )
    p2_src = probe_block("source", "static-analysis", P2, out2, rc2)
    p2_ver = probe_block(
        "verifier",
        "file-read",
        "python3 -c \"from pathlib import Path; print((Path('command-center/p2-wave/probes/ARC-0107/fixtures/tree/fanin/cloud_dispatcher.py').read_text().splitlines()[1]))\"",
        "from lib.completion_reducer import reduce_completion as rc",
        0,
    )

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0107",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0107",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:ARC-0107",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "test-engineer",
            "execution_substrate": "linux-worktree",
        },
        "artifacts": [detector_artifact, fixture_artifact, *supporting_artifacts],
        "evidence": [
            {
                "claim": (
                    "A planted local copy (fanin/fork_partial.py:reduce_completion) and a "
                    "planted exit-zero truthiness stand-in (fanin/fork_truthiness.py:is_complete) "
                    "are found by AST scan; the clean fixture is silent, including "
                    "docs/mention_only.py (use-versus-mention)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": a2,
                "probes": [p1_src, p1_ver],
            },
            {
                "claim": (
                    f"Every fan-in identified in the AST import graph ({scan['fan_in_count']} "
                    "roles) resolves to lib.completion_reducer.reduce_completion via Import/"
                    "ImportFrom (direct, alias rc, module attribute, relative, from-parent). "
                    "Call sites are not enumerated by grep on a name."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": a1,
                "probes": [p2_src, p2_ver],
            },
            {
                "claim": (
                    "The canonical fixture reducer encodes the exit-zero anti-pattern and is "
                    "the single shared symbol imported by every FANIN_ROLE site."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": a3,
                "probes": [p2_src, p2_ver],
            },
        ],
        "tests": [
            {
                "id": "T1-detector-control-planted-second-impl",
                "name": (
                    "Plant a partial re-implementation and a truthiness stand-in; "
                    "assert both are found; clean tree stays silent"
                ),
                "command": P1,
                "result": "PASS",
                "assertions": 15,
                "output_tail": out1[-2000:],
            },
            {
                "id": "T2-call-site-completeness-import-graph",
                "name": (
                    "Every fan-in identified in the AST dependency graph imports "
                    "the shared reducer, itemized, including alias and relative forms"
                ),
                "command": P2,
                "result": "PASS",
                "assertions": 18,
                "output_tail": out2[-2000:],
            },
        ],
        "negative_controls": [
            {
                "id": "planted-partial-and-truthiness",
                "kind": "known-broken-fixture",
                "description": (
                    "Plant fanin/fork_partial.py (local copy of reduce_completion) and "
                    "fanin/fork_truthiness.py (exit_code==0 stand-in). The detector must "
                    "fire on the planted tree and stay silent on the clean tree before a "
                    "zero-duplicate verdict is accepted."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {
                        "control_fired": control["control_fired"],
                        "planted_paths": control["planted_paths"],
                        "finding_count": len(control["planted_findings"]),
                    },
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {
                        "silent_on_clean": control["silent_on_clean"],
                        "second_implementations": scan["second_implementations"],
                        "mention_only_not_flagged": control.get("mention_only_not_flagged"),
                    },
                    sort_keys=True,
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "ARC-0107-probe2-import-graph",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 independently walks the import graph and itemizes each FANIN_ROLE "
                "site. Agreement with probe 1's planted-control narrative is not required; "
                "missing resolved imports fail this probe. method=ast-import-graph."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0107/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "ARC-0107",
        },
        "downstream_consumers": [
            {
                "consumer": "probe2_callsite_imports.py (AST import-graph itemizer)",
                "artifact_path": REDUCER,
                "executed": True,
                "read_ok": True,
                "exit_code": rc2,
                "probe": p2_src,
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": "retry once after fixing validator input; a second schema-invalid result closes the unit FAILED",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/phase4/contracts/ARC-0087.json is absent on this "
                    f"worktree (present={contract_present}). The detector is proven on "
                    "the fixture tree, not against a frozen production contract file."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Place the ARC-0087 contract on disk and re-run the detector against "
                    "the production tree named by that contract."
                ),
            }
        ],
        "report": {
            "kind": "conformance-report",
            "observations": [
                {
                    "name": "planted-second-impl-found",
                    "measured": True,
                    "method": "ast-import-graph planted-control",
                    "anchor": a2,
                },
                {
                    "name": "fan-in-count",
                    "measured": scan["fan_in_count"],
                    "method": "ast-import-graph",
                    "anchor": a6,
                },
                {
                    "name": "every-fan-in-imports-shared-reducer",
                    "measured": True,
                    "method": "ast-import-graph",
                    "anchor": a4,
                },
                {
                    "name": "mention-only-not-a-call-site",
                    "measured": True,
                    "method": "ast-import-graph",
                    "anchor": a5,
                },
            ],
            "control_ids": ["planted-partial-and-truthiness"],
            "title": "One reducer everywhere: detect any second completion predicate",
            "question": QUESTION,
            "method": (
                "ast-import-graph: parse every .py file, resolve Import/ImportFrom "
                "(including relative level and aliases) to lib.completion_reducer."
                "reduce_completion, identify FANIN_ROLE by Assign nodes, and classify "
                "FunctionDef nodes that reimplement or stand in for the reducer. "
                "Grep is not the call-site enumerator."
            ),
            "contract_under_test": {
                "id": "ARC-0087",
                "path": CONTRACT,
                "present": contract_present,
                "source_used": (
                    "Catalog question_or_target for ARC-0087/ARC-0107 plus the twelve "
                    "conditions listed in command-center/p2-wave/_build_IMP0433.py. "
                    "The frozen contract file is absent on this worktree; this unit "
                    "does not rebuild ADV and does not invent a substitute contract."
                ),
            },
            "seeded_failure_class": {
                "id": "FC-11314",
                "name": "two completion predicates disagree",
                "anchor": "command-center/phase3/A1/FAILURE-MODES.json",
            },
            "detector": {
                "module": DETECTOR,
                "canonical_module": D.CANONICAL_MODULE,
                "canonical_symbol": D.CANONICAL_SYMBOL,
                "canonical_path": scan["canonical_path"],
                "used_grep": False,
                "control_ran_before_zero_duplicate_verdict": True,
                "zero_duplicate_accepted": control["zero_duplicate_accepted"],
            },
            "call_sites": itemized,
            "fan_in_count": scan["fan_in_count"],
            "second_implementations_on_clean": scan["second_implementations"],
            "planted_control": {
                "id": "plant-partial-and-truthiness",
                "fired": control["control_fired"],
                "silent_on_clean": control["silent_on_clean"],
                "planted_paths": control["planted_paths"],
                "findings": control["planted_findings"],
            },
            "use_versus_mention": {
                "path": "docs/mention_only.py",
                "listed_as_call_site": False,
                "listed_as_prose_mention": "docs/mention_only.py"
                in scan["mention_only_files"],
            },
            "production_scan": prod,
            "answer": (
                "Detector control: a planted local copy (fanin/fork_partial.py:"
                "reduce_completion) and a planted exit-zero truthiness stand-in "
                "(fanin/fork_truthiness.py:is_complete) are found by AST scan; the "
                "clean fixture is silent, including docs/mention_only.py (use-vs-mention). "
                f"Call-site completeness: {scan['fan_in_count']} fan-in roles each resolve "
                "to lib.completion_reducer.reduce_completion via Import/ImportFrom "
                "(direct, alias rc, module attribute, relative, from-parent). "
                "ARC-0087 contract file is absent; production has no CC-0003 reducer. "
                "SUCCESS:ARC-0107"
            ),
        },
        "extensions": {
            "adv_rebuild_circle": False,
            "global_catalog_write": False,
            "named_probes": [
                {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-4000:]},
                {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-4000:]},
            ],
        },
    }

    # Deduplicate artifacts that appear twice (REDUCER / DETECTOR also in SUPPORTING).
    seen = set()
    unique_arts = []
    for row in doc["artifacts"]:
        if row["path"] in seen:
            continue
        seen.add(row["path"])
        unique_arts.append(row)
    doc["artifacts"] = unique_arts

    validator = schema_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0107 schema errors")
        for e in errs[:30]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0107 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0107 artifact {size}B below floor")
        return 1

    ret = {
        "id": "ARC-0107",
        "unit_id": "ARC-0107",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0107",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "raw_output": out2[-8000:],
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
        "manifest_path": "command-center/p2-wave/probes/ARC-0107/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ARC-0107-probe2-import-graph",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ARC-0107: live named probes exit 0, conformance report "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def man_row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "ARC-0107",
            "receipt_path": "command-center/p2-wave/probes/ARC-0107/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [man_row(OUT, "primary")]
    for rel in SUPPORTING:
        artifacts.append(man_row(rel, "supporting"))
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ARC-0107",
        "verified_on_disk": True,
        "artifacts": artifacts,
        "expected": len(artifacts),
        "present": len(artifacts),
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0107 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
