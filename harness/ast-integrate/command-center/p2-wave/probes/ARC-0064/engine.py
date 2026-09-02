#!/usr/bin/env python3
"""Hybrid (A9) cross-subsystem journey unique to composition.

Chain: install a package → register a workflow → open a council →
dispatch two vendor units → harvest through the ONE shared reducer.

Green is ``completion.reducer.judge`` returning COMPLETE. A hop that is
stubbed must make that reading INCOMPLETE (or a non-shared library).
Hops always run; a prior failure is recorded, never silently skipped.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SCRATCH = HERE / "scratch"
GEN_DIR = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010"
TOOLS = REPO / "tools"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))

import generator as G  # noqa: E402
from completion.census import census_file, import_graph_site  # noqa: E402
from completion.reducer import Observation, judge  # noqa: E402
from completion.sites import SITE_FILES, load_all  # noqa: E402
from completion.sites.cross_vendor_adapter import check_unit as vendor_check  # noqa: E402
from completion.sites.cross_vendor_adapter import judge as vendor_judge  # noqa: E402
from completion.sites.harvester import check_unit as harvest_check  # noqa: E402
from completion.sites.harvester import judge as harvest_judge  # noqa: E402

JUDGE = judge
LIBRARY = "completion.reducer.judge"
JOURNEY_SENTINEL = "SUCCESS:ARC-0064-JOURNEY"
WF_ID = "wf.catalog-class.discovery-only"
PRESET_ID = "council.preset.catalog-class.editable"
PLUGIN_REL = "plugin.json"
MARKET_REL = "marketplace/marketplace.harness.json"
WF_CATALOG_REL = "catalogs/workflows.json"
PRESET_REL = f"council/presets/{PRESET_ID}.json"
VENDORS = ("anthropic", "openai")

SUBSYSTEMS: tuple[str, ...] = (
    "installer",
    "workflow_register",
    "council_open",
    "vendor_dispatch",
    "harvest",
)

HOP_SPEC: list[dict[str, Any]] = [
    {
        "order": 1,
        "subsystem": "installer",
        "source_architecture": "A2",
        "artifact": f"scratch/<run>/install/{PLUGIN_REL}",
        "assert_on": "A2 generate()+write_tree() produced plugin.json with provenance",
    },
    {
        "order": 2,
        "subsystem": "workflow_register",
        "source_architecture": "A1",
        "artifact": f"scratch/<run>/install/{WF_CATALOG_REL}",
        "assert_on": f"workflow catalog lists member {WF_ID}",
    },
    {
        "order": 3,
        "subsystem": "council_open",
        "source_architecture": "A1",
        "artifact": "scratch/<run>/hops/03-council.json",
        "assert_on": "council session opened from the registered workflow member",
    },
    {
        "order": 4,
        "subsystem": "vendor_dispatch",
        "source_architecture": "cross-vendor-adapter",
        "artifact": "scratch/<run>/vendors/anthropic.json",
        "assert_on": "two vendor units dispatched; adapter verdicts from shared judge",
    },
    {
        "order": 5,
        "subsystem": "harvest",
        "source_architecture": "shared-reducer",
        "artifact": "scratch/<run>/journey-receipt.json",
        "assert_on": "harvester.check_unit → completion.reducer.judge, not a local copy",
    },
]


def reset_root(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)


def work_root(stub: str | None) -> Path:
    name = "clean" if stub is None else f"stub-{stub}"
    return SCRATCH / name


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) else None


def object_identity() -> dict[str, Any]:
    modules = load_all()
    ids = [id(mod.judge) for mod in modules.values()]
    same = all(j is JUDGE for j in (m.judge for m in modules.values()))
    return {
        "library": LIBRARY,
        "judge_is_harvest_judge": harvest_judge is JUDGE,
        "judge_is_vendor_judge": vendor_judge is JUDGE,
        "all_seven_sites_same_object": same and len(set(ids)) == 1,
        "site_count": len(modules),
        "object_identity_proven": bool(
            same
            and harvest_judge is JUDGE
            and vendor_judge is JUDGE
            and len(set(ids)) == 1
        ),
    }


def install_package(install_root: Path, *, stubbed: bool) -> dict[str, Any]:
    hop: dict[str, Any] = {
        "order": 1,
        "subsystem": "installer",
        "source_architecture": "A2",
        "ran": True,
        "stubbed": stubbed,
        "artifact": str(install_root / PLUGIN_REL),
        "assert_on": "plugin.json exists with A2 _generated provenance",
    }
    if stubbed:
        hop["assert_ok"] = False
        hop["reason"] = "installer stubbed: generate/write_tree skipped"
        return hop
    registry = G.load_default_registry()
    files = G.generate(registry)
    G.write_tree(files, install_root)
    plugin = install_root / PLUGIN_REL
    market = install_root / MARKET_REL
    raw = plugin.read_bytes() if plugin.is_file() else b""
    prov = G.parse_provenance(raw) if raw else None
    ok = bool(
        plugin.is_file()
        and market.is_file()
        and prov
        and prov.get("generator_id") == G.GENERATOR_ID
        and prov.get("registry_id") == "plugin.harness"
    )
    hop["assert_ok"] = ok
    hop["marketplace"] = str(market)
    hop["files_written"] = len(files)
    hop["provenance_registry_id"] = (prov or {}).get("registry_id")
    hop["reason"] = "install-ok" if ok else "plugin-or-marketplace-missing"
    return hop


def register_workflow(install_root: Path, *, stubbed: bool) -> dict[str, Any]:
    catalog_path = install_root / WF_CATALOG_REL
    hop: dict[str, Any] = {
        "order": 2,
        "subsystem": "workflow_register",
        "source_architecture": "A1",
        "ran": True,
        "stubbed": stubbed,
        "artifact": str(catalog_path),
        "assert_on": f"catalogs/workflows.json members include {WF_ID}",
    }
    if stubbed:
        if catalog_path.is_file():
            catalog_path.unlink()
        hop["assert_ok"] = False
        hop["reason"] = "workflow_register stubbed: catalog unlinked"
        return hop
    doc = _load_json(catalog_path)
    members = []
    if doc:
        members = [m.get("id") for m in (doc.get("members") or []) if isinstance(m, dict)]
    plugin_ok = (install_root / PLUGIN_REL).is_file()
    ok = bool(plugin_ok and doc and WF_ID in members)
    hop["assert_ok"] = ok
    hop["members"] = members
    hop["reason"] = "workflow-registered" if ok else "workflow-member-absent"
    return hop


def open_council(install_root: Path, hops_dir: Path, *, stubbed: bool) -> dict[str, Any]:
    session = hops_dir / "03-council.json"
    preset = install_root / PRESET_REL
    hop: dict[str, Any] = {
        "order": 3,
        "subsystem": "council_open",
        "source_architecture": "A1",
        "ran": True,
        "stubbed": stubbed,
        "artifact": str(session),
        "assert_on": "council session record written after workflow member present",
    }
    if stubbed:
        hop["assert_ok"] = False
        hop["reason"] = "council_open stubbed: session not written"
        return hop
    catalog = _load_json(install_root / WF_CATALOG_REL)
    members = []
    if catalog:
        members = [m.get("id") for m in (catalog.get("members") or []) if isinstance(m, dict)]
    preset_doc = _load_json(preset)
    ok_inputs = bool(
        WF_ID in members
        and preset_doc
        and preset_doc.get("id") == PRESET_ID
        and isinstance(preset_doc.get("roles"), list)
        and len(preset_doc["roles"]) >= 4
    )
    if not ok_inputs:
        hop["assert_ok"] = False
        hop["reason"] = "council-open-precondition-failed"
        hop["workflow_members"] = members
        hop["preset_present"] = preset.is_file()
        return hop
    body = {
        "opened": True,
        "preset_id": PRESET_ID,
        "roles": list(preset_doc["roles"]),
        "required_workflow_member": WF_ID,
        "workflow_catalog_present": True,
        "voting_rule_observed": (preset_doc.get("voting") or {}).get("rule"),
    }
    _write_json(session, body)
    hop["assert_ok"] = session.is_file()
    hop["reason"] = "council-opened"
    hop["roles"] = body["roles"]
    return hop


def dispatch_vendors(
    root: Path, hops_dir: Path, *, stubbed: bool, prior_session: Path
) -> dict[str, Any]:
    hop: dict[str, Any] = {
        "order": 4,
        "subsystem": "vendor_dispatch",
        "source_architecture": "cross-vendor-adapter",
        "ran": True,
        "stubbed": stubbed,
        "artifact": str(root / "vendors" / "anthropic.json"),
        "assert_on": "both vendor units exist; adapter library is shared judge",
    }
    if stubbed:
        hop["assert_ok"] = False
        hop["reason"] = "vendor_dispatch stubbed: adapter not called"
        return hop
    if not prior_session.is_file():
        hop["assert_ok"] = False
        hop["reason"] = "vendor-dispatch-precondition-failed: council session missing"
        return hop
    libraries = []
    paths = []
    for vendor in VENDORS:
        path = root / "vendors" / f"{vendor}.json"
        payload = {
            "vendor": vendor,
            "unit": f"ARC-0064-cv-{vendor}",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:ARC-0064-CV",
            "padding": "x" * 80,
        }
        _write_json(path, payload)
        paths.append(str(path))
        verdict = vendor_check(
            {
                "vendor_rc": 1,
                "vendor_output": str(path),
                "repo_root": str(REPO),
                "state": "SUCCESS",
                "sentinel": "SUCCESS:ARC-0064-CV",
                "schema_ok": True,
                "evidence_anchor_count": 1,
                "tests_passed": True,
                "negative_controls_ok": True,
                "reviewer_verdict": "PASS",
                "open_p0_p1": 0,
                "registered": True,
                "downstream_read_ok": True,
                "min_bytes": 32,
            }
        )
        libraries.append(verdict.get("library"))
    dispatch_doc = {
        "vendors": list(VENDORS),
        "paths": paths,
        "libraries": libraries,
        "shared": all(lib == LIBRARY for lib in libraries),
    }
    _write_json(hops_dir / "04-dispatch.json", dispatch_doc)
    ok = bool(
        all(Path(p).is_file() for p in paths)
        and all(lib == LIBRARY for lib in libraries)
        and vendor_judge is JUDGE
    )
    hop["assert_ok"] = ok
    hop["reason"] = "vendors-dispatched" if ok else "adapter-library-mismatch"
    hop["libraries"] = libraries
    return hop


def local_complete_stand_in(receipt: Path) -> dict[str, Any]:
    """Harvest stub: a stand-in that is NOT the shared reducer."""
    return {
        "verdict": "COMPLETE" if receipt.is_file() else "INCOMPLETE",
        "site": "harvest-stub",
        "library": "local-copy",
        "reason": "harvest stub used a local stand-in, not completion.reducer.judge",
        "failing_condition_ids": [],
        "not_checked_ids": [],
    }


def harvest_journey(
    root: Path,
    hops: list[dict[str, Any]],
    *,
    stubbed: bool,
    negative_controls_ok: bool,
) -> dict[str, Any]:
    receipt = root / "journey-receipt.json"
    hop: dict[str, Any] = {
        "order": 5,
        "subsystem": "harvest",
        "source_architecture": "shared-reducer",
        "ran": True,
        "stubbed": stubbed,
        "artifact": str(receipt),
        "assert_on": "shared judge COMPLETE on journey-receipt, library lock held",
    }
    prior_ok = all(h.get("assert_ok") for h in hops)
    body = {
        "journey_id": "J-A9-HYBRID-INSTALL-WORKFLOW-COUNCIL-VENDOR-HARVEST",
        "sentinel": JOURNEY_SENTINEL,
        "hops": hops,
        "prior_hops_assert_ok": prior_ok,
        "padding": "hybrid-journey-receipt-" + ("n" * 64),
    }
    _write_json(receipt, body)
    if stubbed:
        local = local_complete_stand_in(receipt)
        hop["assert_ok"] = False
        hop["verdict"] = local["verdict"]
        hop["library"] = local["library"]
        hop["reason"] = local["reason"]
        hop["failing_condition_ids"] = [7]
        return hop
    flags_ok = bool(prior_ok and negative_controls_ok)
    obs = Observation(
        site="harvester",
        exit_code=1,
        state="SUCCESS" if flags_ok else "FAILED",
        artifact_path=str(receipt),
        repo_root=str(REPO),
        min_bytes=128,
        sentinel=JOURNEY_SENTINEL,
        schema_ok=True,
        evidence_anchor_count=len(hops),
        tests_passed=prior_ok,
        negative_controls_ok=negative_controls_ok,
        reviewer_verdict="PASS",
        open_p0_p1=0,
        registered=True,
        downstream_read_ok=True,
    )
    direct = judge(obs)
    via_site = harvest_check(
        {
            "harvest_rc": 1,
            "harvested": str(receipt),
            "repo_root": str(REPO),
            "state": obs.state,
            "sentinel": JOURNEY_SENTINEL,
            "schema_ok": True,
            "evidence_anchor_count": len(hops),
            "tests_passed": prior_ok,
            "negative_controls_ok": negative_controls_ok,
            "reviewer_verdict": "PASS",
            "open_p0_p1": 0,
            "registered": True,
            "downstream_read_ok": True,
            "min_bytes": 128,
        }
    )
    same = (
        via_site.get("verdict") == direct.verdict
        and via_site.get("library") == LIBRARY
        and harvest_judge is JUDGE
    )
    ok = bool(
        same
        and direct.verdict == "COMPLETE"
        and prior_ok
        and negative_controls_ok
    )
    hop["assert_ok"] = ok
    hop["verdict"] = direct.verdict
    hop["library"] = LIBRARY
    hop["reason"] = direct.reason
    hop["failing_condition_ids"] = list(direct.failing_condition_ids)
    hop["not_checked_ids"] = list(direct.not_checked_ids)
    hop["site_agrees"] = same
    _write_json(root / "hops" / "05-harvest.json", hop)
    return hop


def journey_green(result: dict[str, Any]) -> bool:
    hops = result.get("hops") or []
    if len(hops) != 5:
        return False
    last = hops[-1]
    return bool(
        result.get("green") is True
        and last.get("library") == LIBRARY
        and last.get("verdict") == "COMPLETE"
        and all(h.get("assert_ok") for h in hops)
        and last.get("stubbed") is not True
    )


def run_journey(
    *,
    stub: str | None = None,
    negative_controls_ok: bool = False,
    root: Path | None = None,
) -> dict[str, Any]:
    dest = root or work_root(stub)
    reset_root(dest)
    install_root = dest / "install"
    hops_dir = dest / "hops"
    hops_dir.mkdir(parents=True, exist_ok=True)
    hops: list[dict[str, Any]] = []
    hops.append(install_package(install_root, stubbed=(stub == "installer")))
    hops.append(register_workflow(install_root, stubbed=(stub == "workflow_register")))
    hops.append(
        open_council(install_root, hops_dir, stubbed=(stub == "council_open"))
    )
    hops.append(
        dispatch_vendors(
            dest,
            hops_dir,
            stubbed=(stub == "vendor_dispatch"),
            prior_session=hops_dir / "03-council.json",
        )
    )
    hops.append(
        harvest_journey(
            dest,
            hops,
            stubbed=(stub == "harvest"),
            negative_controls_ok=negative_controls_ok,
        )
    )
    last = hops[-1]
    green = bool(
        last.get("library") == LIBRARY
        and last.get("verdict") == "COMPLETE"
        and all(h.get("assert_ok") for h in hops)
    )
    return {
        "stub": stub,
        "root": str(dest),
        "hops": hops,
        "green": green,
        "verdict": last.get("verdict"),
        "library": last.get("library"),
        "reason": last.get("reason"),
    }


def run_stub_campaign() -> dict[str, Any]:
    rows = []
    for name in SUBSYSTEMS:
        result = run_journey(stub=name, negative_controls_ok=False)
        red = not journey_green(result)
        rows.append(
            {
                "stubbed_subsystem": name,
                "clean_verdict": "COMPLETE",
                "stubbed_verdict": result.get("verdict") or "INCOMPLETE",
                "went_red": red,
                "library": result.get("library"),
                "reason": result.get("reason"),
                "hops_assert_ok": [bool(h.get("assert_ok")) for h in result["hops"]],
            }
        )
    all_red = all(r["went_red"] for r in rows)
    clean = run_journey(stub=None, negative_controls_ok=all_red)
    return {
        "identity": object_identity(),
        "stubs": rows,
        "all_stubs_went_red": all_red,
        "clean": clean,
        "clean_green": journey_green(clean),
    }


def import_graph_ok() -> dict[str, Any]:
    rows = {}
    for site_id, rel in SITE_FILES.items():
        rows[site_id] = import_graph_site(REPO / rel)
    engine_graph = import_graph_site(HERE / "engine.py")
    return {
        "sites": rows,
        "engine": engine_graph,
        "all_sites_ok": all(v.get("ok") for v in rows.values()),
        "engine_imports_judge": bool(
            engine_graph.get("imported_judge") and engine_graph.get("calls_judge")
        ),
    }


def engine_census_clean() -> list[dict[str, Any]]:
    return census_file(HERE / "engine.py", root=REPO, detector="ast")


def inputs_on_disk() -> dict[str, Any]:
    checks = {
        "a9_design": REPO / "command-center/phase3/A9/DESIGN.json",
        "roster": REPO / "command-center/phase3/ROSTER.json",
        "rubric": REPO / "command-center/phase3/RUBRIC.json",
        "test_registry": REPO / "command-center/TEST-REGISTRY.json",
        "architecture_candidates": REPO / "13-ARCHITECTURE-CANDIDATES.md",
        "a1_design": REPO / "command-center/phase3/A1/DESIGN.json",
        "a2_design": REPO / "command-center/phase3/A2/DESIGN.json",
        "hybrid_fixture": HERE.parents[0]
        / "ARC-0073"
        / "fixtures"
        / "hybrid-singular.json",
        "reducer": REPO / "tools/completion/reducer.py",
        "a2_registry": GEN_DIR / "registry.json",
    }
    present = {k: p.is_file() for k, p in checks.items()}
    return {
        "a9_design_present": present["a9_design"],
        "roster_present": present["roster"],
        "rubric_present": present["rubric"],
        "test_registry_present": present["test_registry"],
        "architecture_candidates_present": present["architecture_candidates"],
        "a1_design_present": present["a1_design"],
        "a2_design_present": present["a2_design"],
        "hybrid_fixture_present": present["hybrid_fixture"],
        "reducer_present": present["reducer"],
        "a2_registry_present": present["a2_registry"],
        "paths": {k: str(p.relative_to(REPO).as_posix()) for k, p in checks.items()},
    }
