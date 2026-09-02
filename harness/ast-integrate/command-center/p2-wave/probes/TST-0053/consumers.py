"""Run the same Name/name document through each consumer. Record resolved values.

Do not assert a single expected value: CPython/Node/jq keep both keys;
a casefold index last-wins; the pipeline reader errors. The table is the proof.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from case_keys import (  # noqa: E402
    NAME_LOWER_VALUE,
    NAME_UPPER_VALUE,
    CaseKeyError,
    extract_pairs,
    pipeline_loads,
    root_name_pair,
)

CNF0035 = REPO / "command-center/p2-wave/probes/CNF-0035"
PLUGIN = REPO / "tools/plugin"
CC = REPO / "command-center"


def _row(
    *,
    consumer_id: str,
    kind: str,
    api: str,
    outcome: str,
    errored: bool,
    error_text: str | None,
    resolved: dict[str, Any] | None,
    keys: list[str] | None,
    note: str,
    available: bool = True,
) -> dict[str, Any]:
    return {
        "consumer_id": consumer_id,
        "kind": kind,
        "api": api,
        "outcome": outcome,
        "errored": errored,
        "error_text": error_text,
        "resolved": resolved,
        "keys": keys,
        "note": note,
        "available": available,
    }


def _from_mapping(obj: Any) -> tuple[dict[str, Any] | None, list[str] | None]:
    if not isinstance(obj, dict):
        return None, None
    return (
        {"Name": obj.get("Name"), "name": obj.get("name")},
        list(obj.keys()),
    )


def _classify_kept(resolved: dict[str, Any]) -> str:
    upper = resolved.get("Name")
    lower = resolved.get("name")
    if upper == NAME_UPPER_VALUE and lower == NAME_LOWER_VALUE:
        return "kept-both"
    if upper == lower == NAME_LOWER_VALUE:
        return "last-wins"
    if upper == lower == NAME_UPPER_VALUE:
        return "first-wins"
    if upper is None or lower is None:
        return "dropped-one"
    if upper == lower:
        return "silent-merge"
    return "diverged"


def consume_cpython_json_loads(text: str) -> dict[str, Any]:
    obj = json.loads(text)
    resolved, keys = _from_mapping(obj)
    return _row(
        consumer_id="cpython-json.loads",
        kind="stdlib",
        api="json.loads",
        outcome=_classify_kept(resolved or {}),
        errored=False,
        error_text=None,
        resolved=resolved,
        keys=keys,
        note="CPython object keys are case-sensitive; Name and name both survive.",
    )


def consume_pairs_hook(text: str) -> dict[str, Any]:
    pairs = extract_pairs(text)
    names = {k: v for k, v in pairs if k.casefold() == "name"}
    keys = [k for k, _ in pairs]
    return _row(
        consumer_id="cpython-object_pairs_hook",
        kind="stdlib-pairs",
        api="json.loads(object_pairs_hook=...)",
        outcome="kept-both" if set(names) == {"Name", "name"} else "dropped-one",
        errored=False,
        error_text=None,
        resolved={"Name": names.get("Name"), "name": names.get("name")},
        keys=keys,
        note="Independent of dict identity: both members are present in the source pairs.",
    )


def consume_ci_downstream(text: str) -> dict[str, Any]:
    """Case-sensitive parse, then a casefold index: the silent data-loss path."""
    obj = json.loads(text)
    index: dict[str, Any] = {}
    kept_orig: dict[str, str] = {}
    for key, value in obj.items():
        fold = key.casefold()
        index[fold] = value
        kept_orig[fold] = key
    merged = {
        "Name": index.get("name"),
        "name": index.get("name"),
    }
    return _row(
        consumer_id="ci-downstream-of-cs-producer",
        kind="casefold-index",
        api="json.loads then dict[key.casefold()]=value (last-wins)",
        outcome=_classify_kept(merged),
        errored=False,
        error_text=None,
        resolved=merged,
        keys=sorted(kept_orig.values()),
        note=(
            "Case-sensitive producer emitted both keys; a case-insensitive "
            "downstream index kept only "
            f"{kept_orig.get('name')!r}={index.get('name')!r}."
        ),
    )


def consume_pipeline_reader(text: str) -> dict[str, Any]:
    try:
        obj = pipeline_loads(text)
    except CaseKeyError as exc:
        return _row(
            consumer_id="tst-0053-pipeline-reader",
            kind="unit-pipeline",
            api="case_keys.pipeline_loads",
            outcome="error",
            errored=True,
            error_text=str(exc),
            resolved=None,
            keys=list(exc.keys),
            note="Pipeline reader errors; it does not silently merge.",
        )
    resolved, keys = _from_mapping(obj)
    return _row(
        consumer_id="tst-0053-pipeline-reader",
        kind="unit-pipeline",
        api="case_keys.pipeline_loads",
        outcome=_classify_kept(resolved or {}),
        errored=False,
        error_text=None,
        resolved=resolved,
        keys=keys,
        note="UNEXPECTED: pipeline reader accepted a colliding document.",
    )


def consume_cnf0035_strict(text: str) -> dict[str, Any]:
    if not (CNF0035 / "strict_reader.py").is_file():
        return _row(
            consumer_id="cnf-0035-strict-reader",
            kind="in-tree",
            api="CNF-0035/strict_reader.read_strict",
            outcome="not-run",
            errored=False,
            error_text=None,
            resolved=None,
            keys=None,
            note="CNF-0035 strict_reader.py absent on this tree.",
            available=False,
        )
    sys.path.insert(0, str(CNF0035))
    import strict_reader as R  # noqa: E402

    try:
        obj = R.read_strict(text, schema=None)
    except R.StrictParseError as exc:
        return _row(
            consumer_id="cnf-0035-strict-reader",
            kind="in-tree",
            api="CNF-0035/strict_reader.read_strict",
            outcome="error",
            errored=True,
            error_text=str(exc),
            resolved=None,
            keys=[exc.key] if exc.key else None,
            note=f"classification={exc.classification}",
        )
    resolved, keys = _from_mapping(obj)
    return _row(
        consumer_id="cnf-0035-strict-reader",
        kind="in-tree",
        api="CNF-0035/strict_reader.read_strict",
        outcome=_classify_kept(resolved or {}),
        errored=False,
        error_text=None,
        resolved=resolved,
        keys=keys,
        note="UNEXPECTED: CNF-0035 strict reader accepted a colliding document.",
    )


def consume_registration_reconciler(path: Path) -> dict[str, Any]:
    loader = PLUGIN / "registration_reconciler.py"
    if not loader.is_file():
        return _row(
            consumer_id="registration_reconciler._load_json",
            kind="in-tree",
            api="tools/plugin/registration_reconciler._load_json",
            outcome="not-run",
            errored=False,
            error_text=None,
            resolved=None,
            keys=None,
            note="registration_reconciler.py absent.",
            available=False,
        )
    sys.path.insert(0, str(PLUGIN))
    import registration_reconciler as rr  # noqa: E402

    obj = rr._load_json(path)
    if obj is None:
        return _row(
            consumer_id="registration_reconciler._load_json",
            kind="in-tree",
            api="tools/plugin/registration_reconciler._load_json",
            outcome="error",
            errored=True,
            error_text="loader returned None",
            resolved=None,
            keys=None,
            note="json.loads failed or file unreadable.",
        )
    resolved, keys = _from_mapping(obj)
    return _row(
        consumer_id="registration_reconciler._load_json",
        kind="in-tree",
        api="tools/plugin/registration_reconciler._load_json",
        outcome=_classify_kept(resolved or {}),
        errored=False,
        error_text=None,
        resolved=resolved,
        keys=keys,
        note="In-tree manifest loader is json.loads (case-sensitive; keeps both).",
    )


def consume_receipt_writer(path: Path) -> dict[str, Any]:
    mod = CC / "receipt_writer.py"
    if not mod.is_file():
        return _row(
            consumer_id="receipt_writer.read_json",
            kind="in-tree",
            api="command-center/receipt_writer.read_json",
            outcome="not-run",
            errored=False,
            error_text=None,
            resolved=None,
            keys=None,
            note="receipt_writer.py absent.",
            available=False,
        )
    sys.path.insert(0, str(CC))
    import receipt_writer as rw  # noqa: E402

    obj, _n = rw.read_json(path)
    resolved, keys = _from_mapping(obj)
    return _row(
        consumer_id="receipt_writer.read_json",
        kind="in-tree",
        api="command-center/receipt_writer.read_json",
        outcome=_classify_kept(resolved or {}),
        errored=False,
        error_text=None,
        resolved=resolved,
        keys=keys,
        note="Receipt reader is json.loads (case-sensitive; keeps both).",
    )


def _run(argv: list[str], timeout: float = 15.0) -> tuple[int, str]:
    try:
        p = subprocess.run(
            argv,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def consume_node(path: Path) -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        return _row(
            consumer_id="node-JSON.parse",
            kind="runtime",
            api="JSON.parse",
            outcome="not-run",
            errored=False,
            error_text=None,
            resolved=None,
            keys=None,
            note="node binary not on PATH.",
            available=False,
        )
    script = (
        "const fs=require('fs');"
        "const o=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));"
        "process.stdout.write(JSON.stringify({keys:Object.keys(o),Name:o.Name,name:o.name}));"
    )
    code, text = _run([node, "-e", script, str(path)])
    if code != 0:
        return _row(
            consumer_id="node-JSON.parse",
            kind="runtime",
            api="JSON.parse",
            outcome="error",
            errored=True,
            error_text=text[-500:],
            resolved=None,
            keys=None,
            note="node JSON.parse exited non-zero.",
        )
    obj = json.loads(text)
    resolved = {"Name": obj.get("Name"), "name": obj.get("name")}
    return _row(
        consumer_id="node-JSON.parse",
        kind="runtime",
        api="JSON.parse",
        outcome=_classify_kept(resolved),
        errored=False,
        error_text=None,
        resolved=resolved,
        keys=list(obj.get("keys") or []),
        note="ECMA-262 object keys are case-sensitive; Name and name both survive.",
    )


def consume_jq(path: Path) -> dict[str, Any]:
    jq = shutil.which("jq")
    if not jq:
        return _row(
            consumer_id="jq",
            kind="runtime",
            api="jq .Name / .name",
            outcome="not-run",
            errored=False,
            error_text=None,
            resolved=None,
            keys=None,
            note="jq binary not on PATH.",
            available=False,
        )
    code, text = _run([jq, "-c", "{keys:keys,Name:.Name,name:.name}", str(path)])
    if code != 0:
        return _row(
            consumer_id="jq",
            kind="runtime",
            api="jq .Name / .name",
            outcome="error",
            errored=True,
            error_text=text[-500:],
            resolved=None,
            keys=None,
            note="jq exited non-zero.",
        )
    obj = json.loads(text)
    resolved = {"Name": obj.get("Name"), "name": obj.get("name")}
    return _row(
        consumer_id="jq",
        kind="runtime",
        api="jq .Name / .name",
        outcome=_classify_kept(resolved),
        errored=False,
        error_text=None,
        resolved=resolved,
        keys=list(obj.get("keys") or []),
        note="jq identifiers are case-sensitive; Name and name both survive.",
    )


CONSUMER_FNS: list[tuple[str, Callable[..., dict[str, Any]], str]] = [
    ("cpython-json.loads", consume_cpython_json_loads, "text"),
    ("cpython-object_pairs_hook", consume_pairs_hook, "text"),
    ("ci-downstream-of-cs-producer", consume_ci_downstream, "text"),
    ("tst-0053-pipeline-reader", consume_pipeline_reader, "text"),
    ("cnf-0035-strict-reader", consume_cnf0035_strict, "text"),
    ("registration_reconciler._load_json", consume_registration_reconciler, "path"),
    ("receipt_writer.read_json", consume_receipt_writer, "path"),
    ("node-JSON.parse", consume_node, "path"),
    ("jq", consume_jq, "path"),
]


def run_matrix(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    plant = root_name_pair(text)
    rows: list[dict[str, Any]] = []
    for _cid, fn, mode in CONSUMER_FNS:
        if mode == "text":
            rows.append(fn(text))
        else:
            rows.append(fn(path))
    outcomes = sorted({r["outcome"] for r in rows if r.get("available") is not False})
    return {
        "fixture": path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else str(path),
        "plant": plant,
        "consumers": rows,
        "distinct_outcomes": outcomes,
        "outcome_count": len(outcomes),
    }


def write_fixture(path: Path | None = None) -> Path:
    from case_keys import FIXTURE_TEXT

    dest = path or (HERE / "fixtures" / "name-and-Name.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(FIXTURE_TEXT, encoding="utf-8")
    return dest
