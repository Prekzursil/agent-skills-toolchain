"""AUD-0040 shared measurement: generator byte-parity and V-GRAPH both-states.

Scratch copies only. The live WORK-UNIT-CATALOG.json is never rewritten.
A missing live DEPENDENCY-GRAPH.json may be filled by emit.py via catalog.save
(the documented generator path). REGISTER.md is absent on this tree; scratch
binds a synthetic register so REACH-6 does not confound the V-GRAPH proof.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC_TOOLS = REPO / "tools" / "command-center"
VALIDATE_PY = CC_TOOLS / "validate.py"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
GRAPH_REL = "command-center/DEPENDENCY-GRAPH.json"
SCHEMA_REL = "command-center/schema/audit-detector-control.schema.json"
OUT_REL = "command-center/audit/AUD-0040-depgraph-catalog-parity.json"
SLIM_KEYS = (
    "defaults",
    "items",
    "owner_questions",
    "provenance",
    "schema_version",
    "terminal_dispositions",
)
EFFORT_NEEDLE = b'"effort": "S"'
EFFORT_REPL = b'"effort": "T"'


def _ensure_cc() -> None:
    path = str(CC_TOOLS)
    if path not in sys.path:
        sys.path.insert(0, path)


def load_catalog_mod():
    _ensure_cc()
    import catalog as cat  # noqa: WPS433

    return cat


def _unit() -> dict[str, Any]:
    catalog = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == "AUD-0040":
            return unit
    raise RuntimeError("AUD-0040 missing from WORK-UNIT-CATALOG.json")


def catalog_sentinel() -> str:
    return str(_unit().get("completion_sentinel") or "")


def catalog_question() -> str:
    return str(_unit().get("question_or_target") or "")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def dump_json(path: Path, obj: Any) -> bytes:
    text = json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = text.encode("utf-8")
    path.write_bytes(raw)
    return raw


def generate_graph_bytes(catalog: dict[str, Any]) -> bytes:
    cat = load_catalog_mod()
    graph = cat.build_graph(catalog)
    return (json.dumps(graph, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def write_committed_graph() -> dict[str, Any]:
    """Materialise DEPENDENCY-GRAPH.json with the official generator. Catalog untouched."""
    cat = load_catalog_mod()
    live = cat.load()
    graph = cat.build_graph(live)
    path = cat.graph_path()
    cat.save(graph, path)
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": GRAPH_REL,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "node_count": graph["node_count"],
        "edge_count": graph["edge_count"],
        "acyclic": graph["acyclic"],
    }


def slim_catalog(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    cat = load_catalog_mod()
    data = raw if raw is not None else cat.load()
    return {k: copy.deepcopy(data[k]) for k in SLIM_KEYS if k in data}


def synthetic_register(catalog: dict[str, Any]) -> str:
    sections: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in catalog["items"]:
        sections[str(item.get("section") or "OUTSTANDING")].append(item)
    order = (
        ("## 1. OUTSTANDING", "OUTSTANDING"),
        ("## 2. DELIBERATELY-SKIPPED", "DELIBERATELY-SKIPPED"),
        ("## 3. SUPERSEDED", "SUPERSEDED"),
        ("## 4. SETTLED", "SETTLED"),
    )
    lines = ["# Register (isolated AUD-0040 fixture)", ""]
    for heading, key in order:
        lines.extend([heading, "", "| id | title |", "| --- | --- |"])
        for item in sections.get(key, []):
            title = str(item.get("title") or "").replace("|", "/")
            lines.append(f"| {item['id']} | {title} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def bind_register(catalog: dict[str, Any], text: str) -> dict[str, Any]:
    raw = text.encode("utf-8")
    catalog["provenance"] = {
        "overlay": "command-center/sources/overlay.json",
        "register": "command-center/sources/REGISTER.md",
        "register_bytes": len(raw),
        "register_sha256": hashlib.sha256(raw).hexdigest(),
        "seeded_by": "command-center/p2-wave/probes/AUD-0040/common.py",
    }
    return catalog


def run_validate_cli(
    catalog_path: Path, graph_path: Path, register_path: Path
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [
        sys.executable,
        "-B",
        str(VALIDATE_PY),
        "--catalog",
        str(catalog_path),
        "--graph",
        str(graph_path),
        "--register",
        str(register_path),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=90,
        env=env,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "exit_code": int(proc.returncode),
        "output": out,
        "vgraph": "V-GRAPH" in out,
        "success": "SUCCESS:cc-validate" in out,
    }


def one_byte_effort_mutation(catalog_bytes: bytes) -> bytes:
    if EFFORT_NEEDLE not in catalog_bytes:
        raise RuntimeError("no one-byte effort needle in serialized catalog")
    return catalog_bytes.replace(EFFORT_NEEDLE, EFFORT_REPL, 1)


def measure() -> dict[str, Any]:
    """Live generator compare + isolated both-states of the V-GRAPH CLI gate."""
    cat = load_catalog_mod()
    live = cat.load()
    gen1 = generate_graph_bytes(live)
    gen2 = generate_graph_bytes(live)
    committed_path = REPO / GRAPH_REL
    committed = (
        committed_path.read_bytes().replace(b"\r\n", b"\n")
        if committed_path.is_file()
        else b""
    )
    parsed = json.loads(gen1.decode("utf-8"))
    generator = {
        "generated_bytes": len(gen1),
        "generated_sha256": hashlib.sha256(gen1).hexdigest(),
        "second_generation_identical": gen1 == gen2,
        "committed_present": committed_path.is_file() and len(committed) > 0,
        "committed_bytes": len(committed),
        "committed_sha256": hashlib.sha256(committed).hexdigest() if committed else "ABSENT",
        "byte_match": bool(committed) and committed == gen1,
        "node_count": parsed["node_count"],
        "edge_count": parsed["edge_count"],
    }

    with tempfile.TemporaryDirectory(prefix="aud0040-") as raw_tmp:
        tmp = Path(raw_tmp)
        slim = slim_catalog(live)
        reg_text = synthetic_register(slim)
        bind_register(slim, reg_text)
        derived = json.loads(generate_graph_bytes(slim).decode("utf-8"))

        clean_cat = tmp / "clean-catalog.json"
        clean_graph = tmp / "clean-graph.json"
        clean_reg = tmp / "REGISTER.md"
        cat_bytes = dump_json(clean_cat, slim)
        dump_json(clean_graph, derived)
        clean_reg.write_text(reg_text, encoding="utf-8", newline="\n")
        clean = run_validate_cli(clean_cat, clean_graph, clean_reg)

        regen_cat = tmp / "regen-catalog.json"
        regen_graph = tmp / "regen-graph.json"
        dump_json(regen_cat, slim)
        dump_json(regen_graph, json.loads(generate_graph_bytes(slim).decode("utf-8")))
        regen = run_validate_cli(regen_cat, regen_graph, clean_reg)

        mut_cat = tmp / "mut-catalog.json"
        mut_bytes = one_byte_effort_mutation(cat_bytes)
        mut_cat.write_bytes(mut_bytes)
        mutated = run_validate_cli(mut_cat, clean_graph, clean_reg)

        stale_graph = tmp / "stale-graph.json"
        stale = copy.deepcopy(derived)
        stale["edge_count"] = 999
        dump_json(stale_graph, stale)
        stale_run = run_validate_cli(clean_cat, stale_graph, clean_reg)

        mut_graph_bytes = generate_graph_bytes(json.loads(mut_bytes.decode("utf-8")))
        slim_graph_bytes = generate_graph_bytes(slim)
        gen_mismatch_mut = int(mut_graph_bytes != slim_graph_bytes)
        gen_mismatch_stale = int(dump_json(tmp / "stale-cmp.json", stale) != slim_graph_bytes)

    gate = {
        "clean_exit": clean["exit_code"],
        "clean_output_tail": clean["output"][-600:],
        "clean_success": clean["success"],
        "regen_exit": regen["exit_code"],
        "mutated_exit": mutated["exit_code"],
        "mutated_vgraph": mutated["vgraph"],
        "mutated_output_tail": mutated["output"][-600:],
        "stale_exit": stale_run["exit_code"],
        "stale_vgraph": stale_run["vgraph"],
        "stale_output_tail": stale_run["output"][-600:],
        "mutation": {
            "kind": "one-byte catalog JSON",
            "from": EFFORT_NEEDLE.decode("ascii"),
            "to": EFFORT_REPL.decode("ascii"),
            "bytes_changed": 1,
        },
        "register_binding": "synthetic scratch REGISTER.md (live sources/REGISTER.md absent)",
    }
    ok = (
        generator["byte_match"]
        and generator["second_generation_identical"]
        and gate["clean_exit"] == 0
        and gate["regen_exit"] == 0
        and gate["mutated_exit"] != 0
        and gate["mutated_vgraph"]
        and gate["stale_exit"] != 0
        and gate["stale_vgraph"]
        and gen_mismatch_mut == 1
        and gen_mismatch_stale == 1
    )
    return {
        "ok": ok,
        "generator": generator,
        "gate": gate,
        "gen_mismatch_mut": gen_mismatch_mut,
        "gen_mismatch_stale": gen_mismatch_stale,
        "live_register_present": (REPO / "command-center/sources/REGISTER.md").is_file(),
    }
