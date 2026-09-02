#!/usr/bin/env python3
"""Probe 2: out-of-process client loader reproduces accept/reject.

Catalog signal (2): the real client's own loader, invoked out of process,
reproduces the same accept/reject pair. A fixture parser alone is one signal.

Reviewer check: frozen-key list matches what this client parses, not what
plugin.schema.json lists as properties.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
CLIENT = PLUGIN / "client_loader.py"
FROZEN_DOC = PLUGIN / "schema" / "frozen-keys.json"
SCHEMA = REPO / ".claude-plugin" / "plugin.schema.json"
LIVE = REPO / ".claude-plugin" / "plugin.json"
BARE = "experimentalFlag"
XKEY = "x-experimentalFlag"


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0007-probe2 {msg}")
    return 1


def _invoke(manifest: Path) -> tuple[int, dict]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        [sys.executable, "-B", str(CLIENT), str(manifest)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    try:
        doc = json.loads(proc.stdout or "")
    except json.JSONDecodeError:
        doc = {"ok": False, "errors": [f"unparseable loader output: {text[:500]}"]}
    return proc.returncode, doc


def _client_independence() -> list[str]:
    source = CLIENT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    problems: list[str] = []
    banned_mods = {"strict_parser", "compat_linter"}
    banned_files = {"frozen-keys.json", "frozen_keys.json", "plugin.schema.json"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in banned_mods:
                    problems.append(f"imports {alias.name}")
        if isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root in banned_mods:
                problems.append(f"imports from {node.module}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for name in banned_files:
                if name in node.value:
                    problems.append(f"mentions {name} as a load path")
    return problems


def main() -> int:
    problems = _client_independence()
    if problems:
        return _fail(f"client loader not independent: {problems}")
    print("independence client_loader_does_not_import_fixture_parser=True")

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # NEGATIVE CONTROL first, out of process.
        bad_path = tmp_path / "bare-unknown.json"
        bad = dict(live)
        bad[BARE] = True
        bad_path.write_text(json.dumps(bad, indent=2) + "\n", encoding="utf-8")
        bad_rc, bad_doc = _invoke(bad_path)
        print(
            f"client-negative bare={BARE!r} rc={bad_rc} ok={bad_doc.get('ok')} "
            f"errors={bad_doc.get('errors')}"
        )
        if bad_rc == 0 or bad_doc.get("ok"):
            return _fail("client accepted known-bad; cannot trust later accept")
        if BARE not in " ".join(str(e) for e in bad_doc.get("errors") or []):
            return _fail("client known-bad did not name the field")

        x_path = tmp_path / "x-unknown.json"
        good = dict(live)
        good[XKEY] = {"forward": True}
        x_path.write_text(json.dumps(good, indent=2) + "\n", encoding="utf-8")
        x_rc, x_doc = _invoke(x_path)
        print(
            f"client-x-accept key={XKEY!r} rc={x_rc} ok={x_doc.get('ok')} "
            f"kind={(x_doc.get('classified') or {}).get(XKEY)}"
        )
        if x_rc != 0 or not x_doc.get("ok"):
            return _fail(f"client rejected x- key: {x_doc}")

        live_rc, live_doc = _invoke(LIVE)
        print(f"client-live rc={live_rc} ok={live_doc.get('ok')} keys={live_doc.get('keys')}")
        if live_rc != 0 or not live_doc.get("ok"):
            return _fail(f"client rejected live plugin.json: {live_doc}")

        canary_path = tmp_path / "schema-canary.json"
        canary = dict(live)
        canary["not_a_client_key"] = "schema-only"
        canary_path.write_text(json.dumps(canary, indent=2) + "\n", encoding="utf-8")
        canary_rc, canary_doc = _invoke(canary_path)
        print(
            f"client-schema-canary rc={canary_rc} ok={canary_doc.get('ok')} "
            f"errors={canary_doc.get('errors')}"
        )
        if canary_rc == 0 or canary_doc.get("ok"):
            return _fail("client accepted schema-only canary; frozen would track schema")

    frozen = set(json.loads(FROZEN_DOC.read_text(encoding="utf-8"))["frozen_top_level_keys"])
    client_keys = set(live_doc.get("accepted_keys") or [])
    print(f"frozen={sorted(frozen)}")
    print(f"client_accepted={sorted(client_keys)}")
    if frozen != client_keys:
        return _fail(f"frozen {sorted(frozen)} != client {sorted(client_keys)}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    schema_props = set((schema.get("properties") or {}).keys())
    print(f"schema_properties={sorted(schema_props)}")
    if "not_a_client_key" not in schema_props:
        return _fail("schema missing not_a_client_key canary")
    if frozen == schema_props:
        return _fail("frozen-key list equals schema properties; reviewer cannot confirm client match")
    if "not_a_client_key" in frozen:
        return _fail("schema canary leaked into frozen list")

    print(
        "negative_fired=True x_accepted=True live_ok=True "
        "frozen_matches_client=True frozen_differs_from_schema=True"
    )
    print("SUCCESS:IMP-0007-probe2 out-of-process client loader accept/reject pair")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
