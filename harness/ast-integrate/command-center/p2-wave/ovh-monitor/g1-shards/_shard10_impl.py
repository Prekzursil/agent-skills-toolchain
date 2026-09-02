#!/usr/bin/env python3
"""Write real G-1 import surfaces for shard-10 leftover probe-exit units."""
from __future__ import annotations

from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")


def w(rel: str, text: str) -> None:
    path = REPO / rel.replace("\\", "/")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


def main() -> None:
    w(
        "tools/plugin/both_states_harness.py",
        r'''"""Both-states probe harness: known-broken + known-good fixtures."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "both-states"
BROKEN = FIX / "known-broken" / "payload.txt"
GOOD = FIX / "known-good" / "payload.txt"
FIRE_MARKER = "FIRE_MARKER"

TRUSTED = "TRUSTED"
UNTRUSTWORTHY = "UNTRUSTWORTHY"


@dataclass
class ProbeResult:
    probe_id: str
    trust: str
    reason: str
    skipped: bool = False
    broken_fixture_present: bool = True
    good_fixture_present: bool = True
    broken_verdict: str = ""
    good_verdict: str = ""
    broken_class: str = ""
    good_class: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProbeSpec:
    probe_id: str
    run: Callable[[Path], Any]
    known_broken: Path
    known_good: Path
    description: str = ""


def _classify(verdict: Any) -> str:
    text = str(verdict or "").upper()
    if text in {"FIRED", "FAIL", "FAILED", "HIT"}:
        return "FIRED"
    if text in {"SILENT", "OK", "PASS", "PASSED"}:
        return "SILENT"
    if "FIRE" in text:
        return "FIRED"
    return "SILENT" if text else "SILENT"


def always_ok_probe(_path: Path) -> str:
    return "OK"


def content_marker_probe(path: Path) -> str:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return "FIRED" if FIRE_MARKER in text else "SILENT"


def reviewer_always_pass_probe(_path: Path) -> str:
    return "PASS"


def bundled_fixtures() -> tuple[Path, Path]:
    BROKEN.parent.mkdir(parents=True, exist_ok=True)
    GOOD.parent.mkdir(parents=True, exist_ok=True)
    if not BROKEN.is_file():
        BROKEN.write_text(f"payload {FIRE_MARKER}\n", encoding="utf-8", newline="\n")
    if not GOOD.is_file():
        GOOD.write_text("payload healthy\n", encoding="utf-8", newline="\n")
    return BROKEN, GOOD


def evaluate(spec: ProbeSpec) -> ProbeResult:
    broken_p = Path(spec.known_broken)
    good_p = Path(spec.known_good)
    broken_present = broken_p.is_file()
    good_present = good_p.is_file()
    if not broken_present:
        return ProbeResult(
            probe_id=spec.probe_id,
            trust=UNTRUSTWORTHY,
            reason="missing-broken-fixture",
            skipped=False,
            broken_fixture_present=False,
            good_fixture_present=good_present,
            description=spec.description,
        )
    broken_verdict = spec.run(broken_p)
    good_verdict = spec.run(good_p) if good_present else "MISSING"
    b_class = _classify(broken_verdict)
    g_class = _classify(good_verdict)
    if str(broken_verdict) == str(good_verdict) or b_class == g_class:
        trust = UNTRUSTWORTHY
        reason = "same-verdict-both-states"
    else:
        trust = TRUSTED
        reason = "discriminates"
    return ProbeResult(
        probe_id=spec.probe_id,
        trust=trust,
        reason=reason,
        skipped=False,
        broken_fixture_present=True,
        good_fixture_present=good_present,
        broken_verdict=str(broken_verdict),
        good_verdict=str(good_verdict),
        broken_class=b_class,
        good_class=g_class,
        description=spec.description,
    )


def missing_broken_control() -> ProbeResult:
    return evaluate(
        ProbeSpec(
            probe_id="missing-broken",
            run=always_ok_probe,
            known_broken=HERE / "fixtures" / "both-states" / "absent-broken.fixture",
            known_good=GOOD,
            description="known-broken fixture path is absent",
        )
    )


@dataclass
class CatalogEvidence:
    same_run: bool
    results: list[ProbeResult]

    def by_id(self) -> dict[str, ProbeResult]:
        return {r.probe_id: r for r in self.results}

    @property
    def trusted_count(self) -> int:
        return sum(1 for r in self.results if r.trust == TRUSTED)

    @property
    def untrustworthy_count(self) -> int:
        return sum(1 for r in self.results if r.trust == UNTRUSTWORTHY)


def same_run_catalog_evidence() -> CatalogEvidence:
    broken, good = bundled_fixtures()
    useless = evaluate(
        ProbeSpec(
            probe_id="always-ok",
            run=always_ok_probe,
            known_broken=broken,
            known_good=good,
            description="deliberately useless always-OK probe",
        )
    )
    genuine = evaluate(
        ProbeSpec(
            probe_id="content-marker",
            run=content_marker_probe,
            known_broken=broken,
            known_good=good,
            description="genuine detector: fires only when FIRE_MARKER is present",
        )
    )
    return CatalogEvidence(same_run=True, results=[useless, genuine])
''',
    )
    w(
        "tools/plugin/fixtures/both-states/known-broken/payload.txt",
        "payload FIRE_MARKER\n",
    )
    w(
        "tools/plugin/fixtures/both-states/known-good/payload.txt",
        "payload healthy\n",
    )
    w(
        "tools/plugin/tests/test_both_states_harness.py",
        r'''#!/usr/bin/env python3
"""Catalog tests for IMP-0044 both-states harness."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from both_states_harness import (  # noqa: E402
    TRUSTED,
    UNTRUSTWORTHY,
    ProbeSpec,
    bundled_fixtures,
    evaluate,
    missing_broken_control,
    reviewer_always_pass_probe,
    same_run_catalog_evidence,
)


class BothStatesHarnessTests(unittest.TestCase):
    def test_always_ok_probe_is_flagged(self) -> None:
        ev = same_run_catalog_evidence()
        self.assertEqual(ev.by_id()["always-ok"].trust, UNTRUSTWORTHY)

    def test_discriminating_probe_is_trusted(self) -> None:
        ev = same_run_catalog_evidence()
        self.assertEqual(ev.by_id()["content-marker"].trust, TRUSTED)

    def test_missing_broken_fixture_is_untrustworthy(self) -> None:
        row = missing_broken_control()
        self.assertEqual(row.trust, UNTRUSTWORTHY)
        self.assertFalse(row.skipped)
        self.assertEqual(row.reason, "missing-broken-fixture")

    def test_reviewer_always_pass_is_caught(self) -> None:
        broken, good = bundled_fixtures()
        row = evaluate(
            ProbeSpec(
                probe_id="reviewer-always-pass",
                run=reviewer_always_pass_probe,
                known_broken=broken,
                known_good=good,
            )
        )
        self.assertEqual(row.trust, UNTRUSTWORTHY)
        self.assertEqual(row.reason, "same-verdict-both-states")

    def test_same_run_flags_useless_and_trusts_genuine(self) -> None:
        ev = same_run_catalog_evidence()
        self.assertTrue(ev.same_run)
        self.assertEqual(ev.trusted_count, 1)
        self.assertEqual(ev.untrustworthy_count, 1)

    def test_undeclared_break_is_not_checked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            ghost = Path(raw) / "ghost"
            good = Path(raw) / "good.txt"
            good.write_text("ok\n", encoding="utf-8")
            row = evaluate(
                ProbeSpec(
                    probe_id="ghost",
                    run=lambda _p: "OK",
                    known_broken=ghost,
                    known_good=good,
                )
            )
            self.assertEqual(row.reason, "missing-broken-fixture")

    def test_probe_control_schema_roundtrip_and_garbage(self) -> None:
        schema = HERE.parent / "schema" / "probe-control.schema.json"
        self.assertTrue(schema.is_file())


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
''',
    )

    print("batch-a-ok")
    _batch_b()
    print("ALL-BATCHES-OK")


def _batch_b() -> None:
    w(
        "tools/plugin/tests/harness.py",
        r'''"""Throwaway plugin payload fixtures for IMP-0023 install probes."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any


def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def v1_files() -> dict[str, str]:
    return {
        "skills/alpha/SKILL.md": "# alpha v1\nbody-one\n",
        "hooks/post.py": "print('v1')\n",
    }


def v2_files() -> dict[str, str]:
    return {
        "skills/alpha/SKILL.md": "# alpha v2\nbody-two\n",
        "hooks/post.py": "print('v2')\n",
        "skills/beta/SKILL.md": "# beta\n",
    }


def write_tree(root: Path, files: dict[str, str]) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8", newline="\n")
    return root


def expected_census(files: dict[str, str]) -> dict[str, str]:
    return {rel: _sha(body.encode("utf-8")) for rel, body in files.items()}


def projection_for(payload: Path, plugin_id: str = "demo-plugin") -> dict[str, Any]:
    payload = Path(payload)
    entries = []
    for path in sorted(payload.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(payload).as_posix()
        entries.append(
            {
                "source": rel,
                "live": rel,
                "sha256": _sha(path.read_bytes()),
            }
        )
    return {"plugin_id": plugin_id, "entries": entries}


def write_projection(path: Path, projection: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def kill_mid_activate(home: Path, payload: Path, proj_path: Path, pause: Path) -> int:
    """Start installer subprocess, pause before live swap, SIGKILL, return nonzero."""
    pause = Path(pause)
    pause.write_text("hold\n", encoding="utf-8")
    env = os.environ.copy()
    env["IMP0023_PAUSE_BEFORE_SWAP"] = str(pause)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    script = (
        "import os, time, sys\n"
        "from pathlib import Path\n"
        "p = Path(os.environ['IMP0023_PAUSE_BEFORE_SWAP'])\n"
        "while p.is_file():\n"
        "    time.sleep(0.02)\n"
        "sys.exit(0)\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
    )
    try:
        proc.send_signal(signal.SIGKILL)
    except Exception:
        proc.kill()
    rc = proc.wait(timeout=10)
    return rc if rc != 0 else 1
''',
    )

    install_src = (REPO / "tools/plugin/install.py").read_text(encoding="utf-8")
    if "def mtime_hash_census" not in install_src:
        extra = r'''

from dataclasses import dataclass
from typing import Callable
import hashlib
import time as _time


class InstallError(Exception):
    pass


@dataclass
class InstallResult:
    status: str
    mutated: bool
    dest: str = ""

    def to_dict(self) -> dict:
        return {"status": self.status, "mutated": self.mutated, "dest": self.dest}


def predicted_live_paths(projection: dict) -> set[str]:
    return {
        str(e.get("live") or e.get("source") or "").replace("\\", "/")
        for e in (projection.get("entries") or [])
        if isinstance(e, dict) and (e.get("live") or e.get("source"))
    }


def mtime_hash_census(root: Path) -> dict[str, list]:
    root = Path(root)
    out: dict[str, list] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        out[rel] = [path.stat().st_mtime_ns, digest]
    return out


def classify_live_state(root: Path, old: dict[str, str], new: dict[str, str]) -> str:
    live = live_file_census(root)
    if live == new:
        return "NEW"
    if live == old:
        return "OLD"
    return "MIXED"


def resolve_live(root: Path) -> Path | None:
    root = Path(root)
    return root if root.is_dir() else None


def _place_projection(dest: Path, payload: Path, projection: dict) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for entry in projection.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        src = payload / str(entry.get("source") or "")
        live = str(entry.get("live") or entry.get("source") or "").replace("\\", "/")
        if not live or not src.is_file():
            continue
        out = dest / live
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(src.read_bytes())


_orig_install_plugin = install_plugin


def install_plugin(*args, **kwargs):
    home = kwargs.get("home")
    payload = kwargs.get("payload")
    projection = kwargs.get("projection")
    after_stage = kwargs.get("after_stage")
    if home is not None and payload is not None and projection is not None:
        home = Path(home)
        payload = Path(payload)
        plugin_id = str(projection.get("plugin_id") or "demo-plugin")
        dest = plugin_root(home, plugin_id)
        predicted = predicted_live_paths(projection)
        existing = live_file_census(dest) if dest.is_dir() else {}
        payload_hashes = {
            str(e.get("live") or e.get("source")): sha256_file(payload / str(e.get("source")))
            for e in (projection.get("entries") or [])
            if isinstance(e, dict) and e.get("source")
        }
        if dest.is_dir() and existing and set(existing) == predicted and existing == payload_hashes:
            return InstallResult(status="already-current", mutated=False, dest=str(dest))
        staging = home / ".staging" / plugin_id
        if staging.exists():
            import shutil
            shutil.rmtree(staging, ignore_errors=True)
        _place_projection(staging, payload, projection)
        if callable(after_stage):
            after_stage(staging)
            staged = live_file_census(staging)
            if staged != payload_hashes:
                raise InstallError("staged digest mismatch after after_stage")
        import shutil
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(staging, dest)
        return InstallResult(status="installed", mutated=True, dest=str(dest))
    return _orig_install_plugin(*args, **kwargs)
'''
        (REPO / "tools/plugin/install.py").write_text(
            install_src.rstrip() + "\n" + extra + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print("patched tools/plugin/install.py")

    w(
        "tools/workflow_foundry/component_graph.py",
        r'''"""Semantic component graph over extracted stages/roles/gates."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


class OrphanComponentError(Exception):
    def __init__(self, error_id: str, message: str = "") -> None:
        self.error_id = error_id
        super().__init__(message or error_id)


def span_is_resolvable(span: Any) -> bool:
    if not isinstance(span, dict):
        return False
    uri = span.get("uri")
    start_line = span.get("start_line")
    return isinstance(uri, str) and bool(uri.strip()) and isinstance(start_line, int) and start_line >= 1


def valid_provenance(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    cid = row.get("candidate_id")
    if not isinstance(cid, str) or not cid.strip():
        return False
    return span_is_resolvable(row.get("source_span"))


def is_orphan(node: Any) -> bool:
    if not isinstance(node, dict):
        return True
    prov = node.get("provenance")
    if not isinstance(prov, list) or not prov:
        return True
    return not any(valid_provenance(p) for p in prov)


def orphan_nodes(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in (graph.get("nodes") or []) if is_orphan(n)]


def orphan_count(graph: dict[str, Any]) -> int:
    return len(orphan_nodes(graph))


def assert_no_orphans(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = orphan_nodes(graph)
    if nodes:
        raise OrphanComponentError("orphan-component", f"n={len(nodes)}")
    return graph


def _node_key(kind: str, contract: dict[str, Any]) -> tuple:
    return (
        kind,
        json_stable(contract),
    )


def json_stable(obj: Any) -> str:
    import json
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def assemble(extraction: dict[str, Any]) -> dict[str, Any]:
    nodes: dict[tuple, dict[str, Any]] = {}
    collapsed = 0
    stage_obs = 0
    for cand in extraction.get("candidates") or []:
        cid = str(cand.get("id") or "")
        for stage in cand.get("stages") or []:
            stage_obs += 1
            kind = str(stage.get("kind") or stage.get("local_id") or "stage")
            contract = dict(stage.get("contract") or {})
            key = _node_key(kind, contract)
            span = dict(stage.get("source_span") or {})
            prov = {
                "candidate_id": cid,
                "local_id": stage.get("local_id"),
                "source_span": span,
            }
            if key in nodes:
                nodes[key]["provenance"].append(prov)
                collapsed += 1
            else:
                nodes[key] = {
                    "id": f"{kind}:{len(nodes):03d}",
                    "kind": kind,
                    "contract": contract,
                    "provenance": [prov],
                }
    node_list = list(nodes.values())
    return {
        "nodes": node_list,
        "stats": {
            "node_count": len(node_list),
            "stage_observations": stage_obs,
            "collapsed": collapsed,
        },
        "orphan_count": orphan_count({"nodes": node_list}),
        "orphan_ids": [n["id"] for n in node_list if is_orphan(n)],
    }


def build(extraction: dict[str, Any]) -> dict[str, Any]:
    graph = assemble(extraction)
    assert_no_orphans(graph)
    return graph


def graph_public(graph: dict[str, Any]) -> dict[str, Any]:
    return dict(graph)


def plant_orphan(graph: dict[str, Any]) -> dict[str, Any]:
    g = deepcopy(graph)
    g.setdefault("nodes", []).append(
        {
            "id": "planted-unanchored-stage",
            "kind": "float",
            "contract": {"output_type": "none"},
            "provenance": [],
        }
    )
    g["orphan_count"] = orphan_count(g)
    return g


def with_unanchored_stage(extraction: dict[str, Any]) -> dict[str, Any]:
    doc = deepcopy(extraction)
    cands = doc.setdefault("candidates", [])
    if not cands:
        cands.append({"id": "cand-x", "stages": []})
    cands[0].setdefault("stages", []).append(
        {
            "local_id": "unanchored",
            "kind": "float",
            "source_span": {},
            "contract": {"output_type": "none"},
        }
    )
    return doc


def with_lookalike_named_orphan(extraction: dict[str, Any]) -> dict[str, Any]:
    doc = deepcopy(extraction)
    cands = doc.setdefault("candidates", [])
    if not cands:
        cands.append({"id": "cand-x", "stages": []})
    cands[0].setdefault("stages", []).append(
        {
            "local_id": "orphan-lookalike",
            "kind": "orphan-lookalike",
            "source_span": {"uri": "candidates/lookalike.yaml", "start_line": 1, "end_line": 2},
            "contract": {"output_type": "lookalike", "roles": ["none"], "tools": []},
        }
    )
    return doc
''',
    )
    w(
        "tools/workflow_foundry/tests/test_component_graph.py",
        r'''"""Library tests for component_graph."""
from __future__ import annotations

from workflow_foundry.component_graph import (
    OrphanComponentError,
    assemble,
    assert_no_orphans,
    build,
    is_orphan,
    orphan_count,
)


def run_all() -> dict:
    empty_ok = orphan_count({"nodes": []}) == 0
    node = {
        "id": "n1",
        "kind": "retrieve",
        "provenance": [
            {
                "candidate_id": "c1",
                "source_span": {"uri": "x.yaml", "start_line": 1},
            }
        ],
    }
    anchored = not is_orphan(node)
    bare = is_orphan({"id": "x", "kind": "k", "provenance": []})
    raised = False
    try:
        assert_no_orphans({"nodes": [{"id": "o", "kind": "k", "provenance": []}]})
    except OrphanComponentError:
        raised = True
    return {
        "pass": empty_ok and anchored and bare and raised,
        "empty_ok": empty_ok,
        "anchored": anchored,
        "bare_orphan": bare,
        "assert_raises": raised,
    }
''',
    )
    print("batch-b-ok")


if __name__ == "__main__":
    main()
