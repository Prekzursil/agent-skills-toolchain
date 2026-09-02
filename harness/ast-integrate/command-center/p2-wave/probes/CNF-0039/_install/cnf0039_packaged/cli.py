#!/usr/bin/env python3
"""Self-contained CLI: four golden journeys that each write a produced file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from importlib.resources import files

JOURNEYS = ("catalog-export", "status-render", "graph-export", "bundle-echo")


def _data(name: str) -> str:
    return files("cnf0039_packaged.data").joinpath(name).read_text(encoding="utf-8")


def load_catalog() -> dict:
    return json.loads(_data("fixture-catalog.json"))


def _meta() -> dict:
    return {
        "sys_path": list(sys.path),
        "executable": sys.executable,
        "module_file": str(Path(__file__).resolve()),
        "argv": list(sys.argv),
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_catalog_export(out: Path) -> None:
    cat = load_catalog()
    payload = {
        "schema_version": cat["schema_version"],
        "program": cat["program"],
        "title": cat["title"],
        "source": "cnf0039_packaged.catalog-export",
        "items": cat["items"],
        **_meta(),
    }
    write_json(out, payload)


def run_status_render(out: Path) -> None:
    cat = load_catalog()
    lines = [
        "# Status",
        "",
        f"program: {cat['program']}",
        "",
        "| id | title | depends_on |",
        "|---|---|---|",
    ]
    for item in cat["items"]:
        deps = ",".join(item["depends_on"]) or "-"
        lines.append(f"| {item['id']} | {item['title']} | {deps} |")
    lines.append("")
    lines.append(f"module_file: {Path(__file__).resolve()}")
    lines.append("")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run_graph_export(out: Path) -> None:
    cat = load_catalog()
    nodes = [item["id"] for item in cat["items"]]
    edges = []
    for item in cat["items"]:
        for dep in item["depends_on"]:
            edges.append({"from": item["id"], "blocked_by": dep})
    payload = {
        "schema_version": 1,
        "source": "cnf0039_packaged.graph-export",
        "nodes": nodes,
        "edges": edges,
        "acyclic": True,
        **_meta(),
    }
    write_json(out, payload)


def run_bundle_echo(out: Path) -> None:
    data = json.loads(_data("golden-journeys.json"))
    data.update(_meta())
    data["source"] = "cnf0039_packaged.bundle-echo"
    write_json(out, data)


HANDLERS = {
    "catalog-export": run_catalog_export,
    "status-render": run_status_render,
    "graph-export": run_graph_export,
    "bundle-echo": run_bundle_echo,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cnf0039-run")
    parser.add_argument("journey", choices=JOURNEYS)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    HANDLERS[args.journey](args.out)
    print(f"WROTE {args.journey} -> {args.out} bytes={args.out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
