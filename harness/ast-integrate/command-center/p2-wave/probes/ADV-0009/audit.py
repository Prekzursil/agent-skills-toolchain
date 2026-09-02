#!/usr/bin/env python3
"""Both-states inventory for ADV-0009.

Probe 1 uses in-process library calls. Probe 2 uses production CLIs /
subprocess (mechanically different). A detector is VALID only when it
FIRES on known-broken and is SILENT on known-good.

Meta-control: validate.py V-FIELDS under the bare CI argv
(require_complete default False) is the known-disarmed detector and must
be classified silent-in-both. Classifying it VALID means this audit is
broken.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC = REPO / "tools" / "command-center"
VALIDATE_PY = CC / "validate.py"
SHARD_PY = CC / "shard_reducer.py"
SECRET_PY = REPO / "tools" / "release" / "bundle_secret_scan.py"
PERM_MIN = REPO / "tools" / "marketplace" / "testdata" / "imp0475" / "minimal"
PERM_BAD = REPO / "tools" / "marketplace" / "testdata" / "imp0475" / "malicious"
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
CHECK_RE = re.compile(r'Violation\(\s*"([A-Z][A-Z0-9-]*)"')

sys.path.insert(0, str(CC))
sys.path.insert(0, str(REPO))

import blob  # noqa: E402
import catalog as cat  # noqa: E402
import status_predicate as sp  # noqa: E402
import validate as val  # noqa: E402
from tools.json_ingest import strict_loads  # noqa: E402
from tools.marketplace.permission_scan import scan_package  # noqa: E402
from tools.plugin.strict_json import StrictJSONError, parse_strict  # noqa: E402
from tools.release.bundle_secret_scan import (  # noqa: E402
    CANARY_VARIABLE,
    ensure_clean_bundle,
    plant_canary,
    scan_tree,
)
from tools.test_support.both_states import run_both_states  # noqa: E402
from tools.test_support.selftest import (  # noqa: E402
    always_on_detector,
    discriminating_detector,
    run_selftest,
    silent_detector,
)

JSON_GOOD = '{"ok": true, "n": 1}'
JSON_BAD = '{"ok": true, "n": 1,}'  # trailing comma — JSON5
CANARY_VALUE = "K7mQ2wP9xL4nR8tY1uI3oA5sD6fG0hJz"
MINIMAL_REFUTATION = {
    "unit_id": "ADV-9999",
    "state": "SUCCESS",
    "sentinel": "SUCCESS:ADV-9999-control",
    "title": "Minimal schema-control document",
    "question": (
        "Does jsonschema.Draft7Validator fire on a document missing required "
        "fields and stay silent on a conforming one?"
    ),
    "report_kind": "refutation-record",
    "overall_verdict": "CONFIRMED",
    "targets": [{"target_id": "T-CTRL", "verdict": "CONFIRMED"}],
    "evidence": [
        {"claim": "empty object is invalid", "verdict": "CONFIRMED", "anchor": "schema:1"},
        {"claim": "minimal document is valid", "verdict": "CONFIRMED", "anchor": "schema:2"},
    ],
    "named_probes": [
        {
            "id": "p1",
            "command": "python3 -B control-p1.py",
            "exit_code": 0,
            "raw_output": "control-ok-1",
        },
        {
            "id": "p2",
            "command": "python3 -B control-p2.py",
            "exit_code": 0,
            "raw_output": "control-ok-2",
        },
    ],
    "tests": [{"id": "t1", "result": "PASS"}, {"id": "t2", "result": "PASS"}],
    "negative_controls": [
        {
            "id": "nc1",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
        }
    ],
    "reviewer": {
        "reviewer_id": "schema-control",
        "verdict": "PASS",
        "independent": True,
    },
    "artifacts": [
        {"path": "command-center/schema/refutation-record.schema.json", "role": "schema"}
    ],
}


def claimed_validate_checks() -> list[str]:
    seen: list[str] = []
    for name in CHECK_RE.findall(VALIDATE_PY.read_text(encoding="utf-8")):
        if name not in seen:
            seen.append(name)
    return seen


def mini_item(item_id: str = "R-A01", **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": item_id,
        "title": "ADV-0009 synthetic fixture item",
        "phase": "0",
        "target": "both-states fixture for a single validate.py check",
        "inputs": [],
        "dependencies": [],
        "assignment": {"model": "opus", "vendor": "anthropic", "role": "implementer"},
        "tool_permissions": ["Read"],
        "execution_substrate": "local-serialized",
        "timeout_seconds": 60,
        "output_path": "command-center/receipts/R-A01.json",
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "evidence_requirement": "two independent signals",
        "tests_required": ["both-states"],
        "reviewer_requirement": "cross-vendor",
        "completion_sentinel": "SUCCESS:R-A01",
        "retry_policy": "max 3 attempts",
        "failure_classification": ["detector-failure"],
        "owner_approval_required": False,
        "next_smallest_action": "run the fixture",
        "status": "OPEN",
        "disposition": None,
        "program": "P2",
        "section": "OUTSTANDING",
    }
    item.update(overrides)
    return item


def mini_catalog(items: list[dict[str, Any]] | None = None, **extra: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {"items": list(items if items is not None else [mini_item()])}
    doc.update(extra)
    return doc


def has_check(violations: list[Any], name: str) -> bool:
    return any(str(v.get("check")) == name for v in violations)


def extract_json(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _end = decoder.raw_decode(text[i:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def run_py(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO), str(CC), env.get("PYTHONPATH", "")]
    )
    return subprocess.run(
        [sys.executable, "-B", *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def validate_lib(catalog: dict[str, Any], **kwargs: Any) -> list[Any]:
    violations, _stats = val.validate(catalog, **kwargs)
    return list(violations)


def write_validate_pair(
    tmp: Path, catalog: dict[str, Any]
) -> tuple[Path, Path]:
    cpath = tmp / "cat.json"
    gpath = tmp / "graph.json"
    cat.save(catalog, cpath)
    cat.save(cat.build_graph(catalog), gpath)
    return cpath, gpath


def validate_cli(
    catalog: dict[str, Any],
    *,
    require_complete: bool = False,
    register_path: Path | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="adv0009-val-") as raw:
        tmp = Path(raw)
        cpath = tmp / "cat.json"
        gpath = tmp / "graph.json"
        cat.save(catalog, cpath)
        cat.save(graph if graph is not None else cat.build_graph(catalog), gpath)
        argv = [
            str(VALIDATE_PY),
            "--catalog",
            str(cpath),
            "--graph",
            str(gpath),
            "--json",
        ]
        if require_complete:
            argv.append("--require-complete")
        if register_path is not None:
            argv.extend(["--register", str(register_path)])
        proc = run_py(argv)
        payload = extract_json((proc.stdout or "") + (proc.stderr or ""))
        violations = list((payload or {}).get("violations") or [])
        return {
            "exit_code": proc.returncode,
            "violations": violations,
            "stdout_tail": ((proc.stdout or "") + (proc.stderr or ""))[-1500:],
        }


def register_pair(tmp: Path) -> tuple[Path, str]:
    path = tmp / "REGISTER.md"
    path.write_text("# REGISTER\n\nNo rows.\n", encoding="utf-8", newline="\n")
    digest = blob.sha256_hex(blob.provenance_bytes(path, repo=REPO))
    return path, digest


def with_register(catalog: dict[str, Any], tmp: Path, *, broken: bool) -> tuple[dict[str, Any], Path]:
    path, digest = register_pair(tmp)
    doc = json.loads(json.dumps(catalog))
    doc["provenance"] = {
        "register": path.name,
        "register_sha256": "" if broken else digest,
    }
    return doc, path


def lib_vfields(broken: bool, *, require_complete: bool) -> bool:
    catalog = mini_catalog(
        [mini_item(completion_sentinel="" if broken else "SUCCESS:R-A01")]
    )
    return has_check(
        validate_lib(catalog, require_complete=require_complete), "V-FIELDS"
    )


def cli_vfields(broken: bool, *, require_complete: bool) -> bool:
    catalog = mini_catalog(
        [mini_item(completion_sentinel="" if broken else "SUCCESS:R-A01")]
    )
    result = validate_cli(catalog, require_complete=require_complete)
    return has_check(result["violations"], "V-FIELDS")


def lib_vempty(broken: bool) -> bool:
    catalog = mini_catalog([] if broken else [mini_item()])
    return has_check(validate_lib(catalog), "V-EMPTY")


def cli_vempty(broken: bool) -> bool:
    catalog = mini_catalog([] if broken else [mini_item()])
    return has_check(validate_cli(catalog)["violations"], "V-EMPTY")


def lib_vid(broken: bool) -> bool:
    catalog = mini_catalog([mini_item(item_id="NOT-AN-ID" if broken else "R-A01")])
    return has_check(validate_lib(catalog), "V-ID")


def cli_vid(broken: bool) -> bool:
    catalog = mini_catalog([mini_item(item_id="NOT-AN-ID" if broken else "R-A01")])
    return has_check(validate_cli(catalog)["violations"], "V-ID")


def lib_reach1(broken: bool) -> bool:
    catalog = mini_catalog(
        [
            mini_item(
                "R-A01",
                dependencies=["R-DOES-NOT-EXIST"] if broken else [],
            )
        ]
    )
    return has_check(validate_lib(catalog), "REACH-1")


def cli_reach1(broken: bool) -> bool:
    catalog = mini_catalog(
        [
            mini_item(
                "R-A01",
                dependencies=["R-DOES-NOT-EXIST"] if broken else [],
            )
        ]
    )
    return has_check(validate_cli(catalog)["violations"], "REACH-1")


def lib_reach2(broken: bool) -> bool:
    if broken:
        catalog = mini_catalog(
            [
                mini_item("R-A01", dependencies=["R-A02"]),
                mini_item("R-A02", dependencies=["R-A01"]),
            ]
        )
    else:
        catalog = mini_catalog(
            [
                mini_item("R-A01", dependencies=[]),
                mini_item("R-A02", dependencies=["R-A01"]),
            ]
        )
    return has_check(validate_lib(catalog), "REACH-2")


def cli_reach2(broken: bool) -> bool:
    if broken:
        catalog = mini_catalog(
            [
                mini_item("R-A01", dependencies=["R-A02"]),
                mini_item("R-A02", dependencies=["R-A01"]),
            ]
        )
    else:
        catalog = mini_catalog(
            [
                mini_item("R-A01", dependencies=[]),
                mini_item("R-A02", dependencies=["R-A01"]),
            ]
        )
    return has_check(validate_cli(catalog)["violations"], "REACH-2")


def lib_reach3(broken: bool) -> bool:
    catalog = mini_catalog(
        [
            mini_item(
                "R-A01",
                next_smallest_action="UNKNOWN" if broken else "run the fixture",
                owner_gate=[],
                dependencies=[],
            )
        ]
    )
    return has_check(validate_lib(catalog), "REACH-3")


def cli_reach3(broken: bool) -> bool:
    catalog = mini_catalog(
        [
            mini_item(
                "R-A01",
                next_smallest_action="UNKNOWN" if broken else "run the fixture",
                owner_gate=[],
                dependencies=[],
            )
        ]
    )
    return has_check(validate_cli(catalog)["violations"], "REACH-3")


def lib_reach4(broken: bool) -> bool:
    item = mini_item("R-A01", owner_gate=["OQ-999"] if broken else [], dependencies=[])
    extra = {"owner_questions": []}
    return has_check(validate_lib(mini_catalog([item], **extra)), "REACH-4")


def cli_reach4(broken: bool) -> bool:
    item = mini_item("R-A01", owner_gate=["OQ-999"] if broken else [], dependencies=[])
    extra = {"owner_questions": []}
    return has_check(validate_cli(mini_catalog([item], **extra))["violations"], "REACH-4")


def lib_reach5(broken: bool) -> bool:
    if broken:
        catalog = mini_catalog(
            [
                mini_item(
                    "T-01",
                    disposition="DONE-VERIFIED",
                    disposition_evidence="   ",
                    status="SETTLED",
                )
            ]
        )
    else:
        catalog = mini_catalog([mini_item("T-01")])
    return has_check(validate_lib(catalog), "REACH-5")


def cli_reach5(broken: bool) -> bool:
    if broken:
        catalog = mini_catalog(
            [
                mini_item(
                    "T-01",
                    disposition="DONE-VERIFIED",
                    disposition_evidence="   ",
                    status="SETTLED",
                )
            ]
        )
    else:
        catalog = mini_catalog([mini_item("T-01")])
    return has_check(validate_cli(catalog)["violations"], "REACH-5")


def lib_vgraph(broken: bool) -> bool:
    catalog = mini_catalog([mini_item()])
    graph = {"schema_version": 1, "nodes": [], "edges": []} if broken else cat.build_graph(
        catalog
    )
    return has_check(validate_lib(catalog, graph=graph), "V-GRAPH")


def cli_vgraph(broken: bool) -> bool:
    catalog = mini_catalog([mini_item()])
    graph = {"schema_version": 1, "nodes": [], "edges": []} if broken else None
    return has_check(validate_cli(catalog, graph=graph)["violations"], "V-GRAPH")


def lib_reach6(broken: bool) -> bool:
    with tempfile.TemporaryDirectory(prefix="adv0009-r6-") as raw:
        tmp = Path(raw)
        catalog, path = with_register(mini_catalog([mini_item()]), tmp, broken=broken)
        return has_check(
            validate_lib(catalog, register_path=path), "REACH-6"
        )


def cli_reach6(broken: bool) -> bool:
    with tempfile.TemporaryDirectory(prefix="adv0009-r6c-") as raw:
        tmp = Path(raw)
        catalog, path = with_register(mini_catalog([mini_item()]), tmp, broken=broken)
        return has_check(
            validate_cli(catalog, register_path=path)["violations"], "REACH-6"
        )


def schema_errors(doc: Any) -> int:
    import jsonschema

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    return sum(1 for _ in jsonschema.Draft7Validator(schema).iter_errors(doc))


def lib_schema(broken: bool) -> bool:
    return schema_errors({} if broken else MINIMAL_REFUTATION) > 0


def cli_schema(broken: bool) -> bool:
    with tempfile.TemporaryDirectory(prefix="adv0009-schema-") as raw:
        tmp = Path(raw)
        doc_path = tmp / "doc.json"
        doc_path.write_text(
            json.dumps({} if broken else MINIMAL_REFUTATION), encoding="utf-8"
        )
        script = (
            "import json,sys,jsonschema;"
            "schema=json.loads(open(sys.argv[1],encoding='utf-8').read());"
            "doc=json.loads(open(sys.argv[2],encoding='utf-8').read());"
            "n=sum(1 for _ in jsonschema.Draft7Validator(schema).iter_errors(doc));"
            "print(json.dumps({'n_errors': n}));"
            "raise SystemExit(0)"
        )
        proc = run_py(["-c", script, str(REPO / SCHEMA_REL), str(doc_path)])
        payload = extract_json(proc.stdout or "")
        return int((payload or {}).get("n_errors") or 0) > 0


def lib_strict_json(broken: bool) -> bool:
    text = JSON_BAD if broken else JSON_GOOD
    try:
        parse_strict(text)
        return False
    except StrictJSONError:
        return True


def cli_strict_json(broken: bool) -> bool:
    text = JSON_BAD if broken else JSON_GOOD
    script = (
        "import json, sys\n"
        "from tools.plugin.strict_json import parse_strict, StrictJSONError\n"
        "fired = False\n"
        "try:\n"
        "    parse_strict(sys.argv[1])\n"
        "except StrictJSONError:\n"
        "    fired = True\n"
        "print(json.dumps({'fired': fired}))\n"
    )
    proc = run_py(["-c", script, text])
    payload = extract_json(proc.stdout or "")
    return bool((payload or {}).get("fired"))


def lib_json_ingest(broken: bool) -> bool:
    result = strict_loads(JSON_BAD if broken else JSON_GOOD)
    return not bool(result.accepted)


def cli_json_ingest(broken: bool) -> bool:
    text = JSON_BAD if broken else JSON_GOOD
    script = (
        "import json,sys;"
        "from tools.json_ingest import strict_loads;"
        "r=strict_loads(sys.argv[1]);"
        "print(json.dumps({'fired': (not r.accepted)}))"
    )
    proc = run_py(["-c", script, text])
    payload = extract_json(proc.stdout or "")
    return bool((payload or {}).get("fired"))


def lib_permission(broken: bool) -> bool:
    root = PERM_BAD if broken else PERM_MIN
    return bool(scan_package(root).flagged)


def cli_permission(broken: bool) -> bool:
    root = PERM_BAD if broken else PERM_MIN
    script = (
        "import json,sys;"
        "from tools.marketplace.permission_scan import scan_package;"
        "print(json.dumps({'fired': bool(scan_package(sys.argv[1]).flagged)}))"
    )
    proc = run_py(["-c", script, str(root)])
    payload = extract_json(proc.stdout or "")
    return bool((payload or {}).get("fired"))


def lib_secret(broken: bool) -> bool:
    with tempfile.TemporaryDirectory(prefix="adv0009-sec-") as raw:
        root = Path(raw)
        ensure_clean_bundle(root)
        if broken:
            plant_canary(root, CANARY_VALUE)
        _examined, _skipped, findings = scan_tree(root)
        return len(findings) > 0


def cli_secret(broken: bool) -> bool:
    with tempfile.TemporaryDirectory(prefix="adv0009-secc-") as raw:
        root = Path(raw)
        ensure_clean_bundle(root)
        if broken:
            plant_canary(root, CANARY_VALUE)
        proc = run_py([str(SECRET_PY), "--extracted-root", str(root)])
        payload = extract_json(proc.stdout or "")
        findings = list((payload or {}).get("findings") or [])
        if findings:
            return True
        return proc.returncode == 2


def lib_shard(broken: bool) -> bool:
    from shard_reducer import reduce_shard_set

    with tempfile.TemporaryDirectory(prefix="adv0009-shard-") as raw:
        root = Path(raw)
        set_root = root / "set"
        set_root.mkdir()
        names = ["shard-a.json", "shard-b.json", "shard-c.json", "shard-d.json"]
        for i, name in enumerate(names):
            if broken and i == 2:
                continue
            (set_root / name).write_text("{}\n", encoding="utf-8")
        man = root / "manifest.json"
        man.write_text(
            json.dumps(
                {
                    "set_id": "adv0009",
                    "shards": [
                        {"id": f"SHARD-{chr(65 + i)}", "path": name}
                        for i, name in enumerate(names)
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = reduce_shard_set(set_root, man)
        return result["status"] != "COMPLETE"


def cli_shard(broken: bool) -> bool:
    with tempfile.TemporaryDirectory(prefix="adv0009-shardc-") as raw:
        root = Path(raw)
        set_root = root / "set"
        set_root.mkdir()
        names = ["shard-a.json", "shard-b.json", "shard-c.json", "shard-d.json"]
        for i, name in enumerate(names):
            if broken and i == 2:
                continue
            (set_root / name).write_text("{}\n", encoding="utf-8")
        man = root / "manifest.json"
        man.write_text(
            json.dumps(
                {
                    "set_id": "adv0009",
                    "shards": [
                        {"id": f"SHARD-{chr(65 + i)}", "path": name}
                        for i, name in enumerate(names)
                    ],
                }
            ),
            encoding="utf-8",
        )
        proc = run_py(
            [str(SHARD_PY), "--set-root", str(set_root), "--manifest", str(man)]
        )
        payload = extract_json(proc.stdout or "")
        if payload and payload.get("status"):
            return payload["status"] != "COMPLETE"
        return proc.returncode == 1


def as_state_fn(fn: Callable[[bool], bool]) -> Callable[[Any], bool]:
    def detector(state: Any) -> bool:
        broken = bool(state.get("broken")) if isinstance(state, dict) else bool(state)
        return bool(fn(broken))

    return detector


def pair_for(fn: Callable[[bool], bool], detector_id: str) -> dict[str, Any]:
    return run_both_states(
        as_state_fn(fn),
        {"broken": False, "label": "known-good"},
        {"broken": True, "label": "known-broken"},
        detector_id=detector_id,
    )


def substrate() -> dict[str, Any]:
    reducer = sp.load_reducer()
    rows = [
        {
            "id": "ci-gates",
            "path": ".github/workflows",
            "present": (REPO / ".github" / "workflows").is_dir(),
            "note": "quality.yml / CI workflow tree absent on this worktree",
        },
        {
            "id": "hook-guards-production",
            "path": ".git/hooks",
            "present": (REPO / ".git" / "hooks").is_dir()
            and any((REPO / ".git" / "hooks").glob("*")),
            "note": "production hook-guard tree is not shipped here; probe fixtures only",
        },
        {
            "id": "linters-charter",
            "path": ".quality/charter.yml",
            "present": (REPO / ".quality" / "charter.yml").is_file(),
            "note": ".quality charter / ruff project config absent",
        },
        {
            "id": "monitor-liveness",
            "path": "k8s liveness probes",
            "present": False,
            "note": "no kubernetes liveness detector shipped in this worktree",
        },
        {
            "id": "cc-0003-completion-reducer",
            "path": str(reducer.source or "tools/command-center/completion_predicate.py"),
            "present": bool(reducer.importable and reducer.reducer is not None),
            "note": reducer.reason,
        },
    ]
    return {"rows": rows, "present": [r for r in rows if r["present"]], "absent": [r for r in rows if not r["present"]]}


INVENTORY: list[dict[str, Any]] = [
    {
        "id": "validate.py:V-FIELDS:ci-bare",
        "family": "validate.py",
        "check": "V-FIELDS",
        "arming_flag": "--require-complete",
        "meta_control": True,
        "expect_reason": "silent-in-both",
        "lib": lambda broken: lib_vfields(broken, require_complete=False),
        "cli": lambda broken: cli_vfields(broken, require_complete=False),
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:V-FIELDS:armed",
        "family": "validate.py",
        "check": "V-FIELDS",
        "arming_flag": "--require-complete",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lambda broken: lib_vfields(broken, require_complete=True),
        "cli": lambda broken: cli_vfields(broken, require_complete=True),
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:V-EMPTY",
        "family": "validate.py",
        "check": "V-EMPTY",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_vempty,
        "cli": cli_vempty,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:V-ID",
        "family": "validate.py",
        "check": "V-ID",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_vid,
        "cli": cli_vid,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:REACH-1",
        "family": "validate.py",
        "check": "REACH-1",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_reach1,
        "cli": cli_reach1,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:REACH-2",
        "family": "validate.py",
        "check": "REACH-2",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_reach2,
        "cli": cli_reach2,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:REACH-3",
        "family": "validate.py",
        "check": "REACH-3",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_reach3,
        "cli": cli_reach3,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:REACH-4",
        "family": "validate.py",
        "check": "REACH-4",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_reach4,
        "cli": cli_reach4,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:REACH-5",
        "family": "validate.py",
        "check": "REACH-5",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_reach5,
        "cli": cli_reach5,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:V-GRAPH",
        "family": "validate.py",
        "check": "V-GRAPH",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_vgraph,
        "cli": cli_vgraph,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "validate.py:REACH-6",
        "family": "validate.py",
        "check": "REACH-6",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_reach6,
        "cli": cli_reach6,
        "source": "tools/command-center/validate.py",
    },
    {
        "id": "schema:jsonschema:refutation-record",
        "family": "schema-validator",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_schema,
        "cli": cli_schema,
        "source": SCHEMA_REL,
    },
    {
        "id": "strict_json:parse_strict",
        "family": "schema-validator",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_strict_json,
        "cli": cli_strict_json,
        "source": "tools/plugin/strict_json.py",
    },
    {
        "id": "json_ingest:strict_loads",
        "family": "schema-validator",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_json_ingest,
        "cli": cli_json_ingest,
        "source": "tools/json_ingest.py",
    },
    {
        "id": "permission_scan:declared-vs-exercised",
        "family": "scanner",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_permission,
        "cli": cli_permission,
        "source": "tools/marketplace/permission_scan.py",
    },
    {
        "id": "bundle_secret_scan:extracted-tree",
        "family": "scanner",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_secret,
        "cli": cli_secret,
        "source": "tools/release/bundle_secret_scan.py",
    },
    {
        "id": "shard_reducer:completion",
        "family": "completion-reducer",
        "expect_reason": "silent-on-good-then-fires-on-broken",
        "lib": lib_shard,
        "cli": cli_shard,
        "source": "tools/command-center/shard_reducer.py",
    },
]


def classify_rows(instrument: str) -> list[dict[str, Any]]:
    key = "lib" if instrument == "library" else "cli"
    rows: list[dict[str, Any]] = []
    for spec in INVENTORY:
        fn = spec[key]
        record = pair_for(fn, spec["id"])
        slim = {
            "detector_id": spec["id"],
            "family": spec["family"],
            "instrument": instrument,
            "source": spec["source"],
            "check": spec.get("check"),
            "arming_flag": spec.get("arming_flag"),
            "meta_control": bool(spec.get("meta_control")),
            "expect_reason": spec["expect_reason"],
            "verdict": record["verdict"],
            "reason": record["reason"],
            "valid": record["valid"],
            "fired_on_bad_state": bool(record["known_broken"]["fired"]),
            "silent_on_good_state": record["known_good"]["observation"] == "SILENT",
            "known_good": record["known_good"],
            "known_broken": record["known_broken"],
        }
        rows.append(slim)
    return rows


def fixture_calibration() -> dict[str, Any]:
    selftest = run_selftest()
    silent = run_both_states(
        silent_detector,
        {"broken": False},
        {"broken": True},
        detector_id="audit-calibration-silent",
    )
    always = run_both_states(
        always_on_detector,
        {"broken": False},
        {"broken": True},
        detector_id="audit-calibration-always-on",
    )
    ok = run_both_states(
        discriminating_detector,
        {"broken": False},
        {"broken": True},
        detector_id="audit-calibration-discriminating",
    )
    return {
        "selftest_pass": bool(selftest.get("pass")),
        "silent_rejected": silent.get("reason") == "silent-in-both" and not silent.get("valid"),
        "always_on_rejected": always.get("reason") == "fires-in-both" and not always.get("valid"),
        "discriminating_valid": bool(ok.get("valid")),
        "silent": {
            "verdict": silent.get("verdict"),
            "reason": silent.get("reason"),
            "valid": silent.get("valid"),
        },
        "always_on": {
            "verdict": always.get("verdict"),
            "reason": always.get("reason"),
            "valid": always.get("valid"),
        },
        "discriminating": {
            "verdict": ok.get("verdict"),
            "reason": ok.get("reason"),
            "valid": ok.get("valid"),
        },
    }


def status_for(row: dict[str, Any]) -> str:
    if row.get("reason") == "silent-in-both":
        return "SILENT-IN-BOTH"
    if row.get("reason") == "fires-in-both":
        return "FIRES-IN-BOTH"
    if row.get("valid"):
        return "ARMED" if row.get("arming_flag") and "armed" in row["detector_id"] else "FIRED"
    return str(row.get("reason") or "REJECTED").upper()


def run_instrument(instrument: str) -> dict[str, Any]:
    rows = classify_rows(instrument)
    calib = fixture_calibration() if instrument == "library" else None
    meta = next(r for r in rows if r.get("meta_control"))
    valid_ids = [r["detector_id"] for r in rows if r.get("valid")]
    silent_ids = [r["detector_id"] for r in rows if r.get("reason") == "silent-in-both"]
    firing_broken = [r["detector_id"] for r in rows if r.get("fired_on_bad_state")]
    claimed = claimed_validate_checks()
    executed_checks = sorted(
        {r["check"] for r in rows if r.get("check")}
    )
    errors = []
    if meta["reason"] != "silent-in-both" or meta["valid"]:
        errors.append(
            f"meta-control {meta['detector_id']} classified {meta['reason']} "
            f"valid={meta['valid']}; required silent-in-both"
        )
    if "validate.py:V-EMPTY" not in firing_broken:
        errors.append("V-EMPTY did not fire on the empty catalog")
    if len(valid_ids) < 1:
        errors.append("zero VALID detectors; harness may be dead")
    if instrument == "library" and calib is not None:
        if not calib["silent_rejected"]:
            errors.append("audit calibration did not reject silent-in-both")
        if not calib["always_on_rejected"]:
            errors.append("audit calibration did not reject fires-in-both")
        if not calib["discriminating_valid"]:
            errors.append("audit calibration did not accept a discriminating detector")
        if not calib["selftest_pass"]:
            errors.append("tools.test_support.selftest did not pass")
    ok = not errors
    return {
        "instrument": instrument,
        "pass": ok,
        "errors": errors,
        "rows": rows,
        "calibration": calib,
        "meta_control": meta,
        "n_valid": len(valid_ids),
        "n_silent_in_both": len(silent_ids),
        "n_fired_on_broken": len(firing_broken),
        "valid_ids": valid_ids,
        "silent_in_both_ids": silent_ids,
        "fired_on_broken_ids": firing_broken,
        "claimed_validate_checks": claimed,
        "executed_validate_checks": executed_checks,
        "unexecuted_validate_checks": [c for c in claimed if c not in executed_checks],
        "substrate": substrate(),
        "canary_variable": CANARY_VARIABLE,
    }


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "library"
    report = run_instrument(which)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
