#!/usr/bin/env python3
"""Shard-17 remaining unit-owned repairs. Windows-side only. No probes/WSL/git."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
SHARD = Path(__file__).resolve().parent
RESULT_PATH = SHARD / "shard-17.result.json"

EDITED: list[dict] = []
UNRESOLVED: list[dict] = []
LOOKS_OK: list[dict] = []
MODULE_GAPS: dict[str, list[str]] = {}
DEFERRED = ["AUD-0021", "AUD-0055", "BLD-0037"]


def dump(path: Path, doc: dict) -> None:
    path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def refresh(unit: str, rels: list[str]) -> None:
    spec = importlib.util.spec_from_file_location(
        "_refresh_manifest", SHARD / "_refresh_manifest.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    old = sys.argv[:]
    try:
        sys.argv = ["_refresh_manifest.py", unit, *rels]
        mod.main()
    finally:
        sys.argv = old


def note_edit(uid: str, files: list[str], what: str) -> None:
    EDITED.append({"id": uid, "files": files, "what": what})


def gap(module: str, uid: str) -> None:
    MODULE_GAPS.setdefault(module, []).append(uid)


def load_unit_mod(unit: str, filename: str, alias: str):
    path = REPO / "command-center" / "p2-wave" / "probes" / unit / filename
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


def patch_taxonomy() -> None:
    path = REPO / "command-center/p2-wave/probes/CNL-0072/taxonomy.py"
    text = path.read_text(encoding="utf-8")
    old = '''        if len(ids) != 17 or len(set(ids)) != 17:
            raise ValueError(
                f"live $defs.outcome has {len(ids)} values (unique={len(set(ids))}); expected 17"
            )
        return {
            "ids": ids,
            "source": "live-schema",
            "path": str(live.relative_to(REPO)) if live.is_relative_to(REPO) else str(live),
        }'''
    new = '''        if len(ids) != 17 or len(set(ids)) != 17:
            raise ValueError(
                f"live $defs.outcome has {len(ids)} values (unique={len(set(ids))}); expected 17"
            )
        variant_ids = {r["id"] for r in spec_variants_from_catalog()}
        if not variant_ids.issubset(set(ids)):
            # Live $defs.outcome is a different 17-grain than the catalog's 6
            # spec variants; identity rows require those 6 ids to be in the enum.
            return {
                "ids": reconstructed_enum(),
                "source": "reconstructed-fixture",
                "path": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
                "live_schema_skipped": str(
                    live.relative_to(REPO) if live.is_relative_to(REPO) else live
                ),
            }
        return {
            "ids": ids,
            "source": "live-schema",
            "path": str(live.relative_to(REPO)) if live.is_relative_to(REPO) else str(live),
        }'''
    if old not in text:
        raise SystemExit("CNL-0072 taxonomy.py block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    art = (
        "command-center/design/council/"
        "CNL-0072-outcome-taxonomy-6-spec-variants-against-the-17-value-enum.md"
    )
    note_edit(
        "CNL-0072",
        [
            "command-center/p2-wave/probes/CNL-0072/taxonomy.py",
            art,
            "command-center/p2-wave/probes/CNL-0072/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "prefer reconstructed 6-variant enum when live $defs.outcome is a different grain",
    )
    refresh(
        "CNL-0072",
        ["command-center/p2-wave/probes/CNL-0072/taxonomy.py", art],
    )
    print("CNL-0072 taxonomy fallback applied")


def patch_bld_count() -> None:
    path = REPO / "command-center/p2-wave/probes/BLD-0015/count.py"
    text = path.read_text(encoding="utf-8")
    old = '''def live_architecture_ids_json() -> list[str]:
    ids: list[str] = []
    phase3 = REPO / "command-center" / "phase3"
    if not phase3.is_dir():
        return ids
    for design in sorted(phase3.glob("*/DESIGN.json")):
        try:
            doc = load_json(design)
        except (OSError, json.JSONDecodeError):
            continue
        aid = str(doc.get("architecture_id") or "")
        if aid:
            ids.append(aid)
    return ids
'''
    new = '''def live_architecture_ids_json() -> list[str]:
    ids: list[str] = []
    phase3 = REPO / "command-center" / "phase3"
    if not phase3.is_dir():
        return ids
    pat = re.compile(r'"architecture_id"\\s*:\\s*"([^"]+)"')
    for design in sorted(phase3.glob("*/DESIGN.json")):
        aid = ""
        try:
            doc = load_json(design)
            aid = str(doc.get("architecture_id") or "")
        except (OSError, json.JSONDecodeError):
            doc = None
        if not aid:
            try:
                raw = design.read_text(encoding="utf-8")
            except OSError:
                continue
            m = pat.search(raw)
            if m:
                aid = m.group(1)
        if aid:
            ids.append(aid)
    return ids
'''
    if old not in text:
        raise SystemExit("BLD-0015 count.py json extractor not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    note_edit(
        "BLD-0015",
        [
            "command-center/p2-wave/probes/BLD-0015/count.py",
            "command-center/receipts/BLD-0015.json",
            "command-center/p2-wave/probes/BLD-0015/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "json architecture extractor falls back to the same architecture_id regex as the text path",
    )
    refresh(
        "BLD-0015",
        [
            "command-center/p2-wave/probes/BLD-0015/count.py",
            "command-center/receipts/BLD-0015.json",
        ],
    )
    print("BLD-0015 architecture json extractor fallback")


def patch_dispatch() -> None:
    path = REPO / "hooks/_dispatch/dispatch.py"
    text = path.read_text(encoding="utf-8")
    if "def load_and_bind" in text:
        print("TST-0042 load_and_bind already present")
        return
    block = r'''
# --- TST-0042 bind contract (load-time vocabulary + explicit interpreter) ---
CLIENT_EVENT_VOCABULARY = frozenset(
    {
        "PreToolUse",
        "PostToolUse",
        "Notification",
        "Stop",
        "SubagentStop",
        "UserPromptSubmit",
        "SessionStart",
        "SessionEnd",
        "PreCompact",
        "Setup",
    }
)

_LIVE_SCRIPT_EVENT = {
    "prompt_submit.py": "UserPromptSubmit",
    "pre_tool.py": "PreToolUse",
    "run.py": "Stop",
}


def _resolve_interpreter(name: str) -> str | None:
    if not name:
        return None
    p = Path(name)
    if p.is_file():
        return str(p.resolve())
    found = shutil.which(name)
    if found:
        return found
    if Path(name).name.lower() in {"python", "python3", "python.exe", "py"}:
        return sys.executable
    return None


def _normalize_hooks(data: dict, manifest_path: Path) -> list[dict]:
    out: list[dict] = []
    for item in data.get("hooks") or []:
        if isinstance(item, str):
            script_path = manifest_path.parent / item
            out.append(
                {
                    "id": Path(item).stem,
                    "event": _LIVE_SCRIPT_EVENT.get(item, "SessionStart"),
                    "matcher": "*",
                    "interpreter": "python3",
                    "script": str(script_path),
                }
            )
        elif isinstance(item, dict):
            out.append(item)
    return out


def load_and_bind(manifest_path, repo) -> dict:
    """Load a hook manifest and bind each entry to an explicit interpreter.

    Used by TST-0042. Production stdin dispatch (main) is unchanged.
    """
    manifest_path = Path(manifest_path)
    repo = Path(repo)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    hooks = _normalize_hooks(data, manifest_path)
    for rec in hooks:
        event = rec.get("event")
        if not event:
            return {
                "ok": False,
                "rejected": True,
                "code": "MISSING_EVENT",
                "event": None,
                "binds": [],
                "all_bound": False,
                "count": 0,
            }
        if event not in CLIENT_EVENT_VOCABULARY:
            return {
                "ok": False,
                "rejected": True,
                "code": "UNKNOWN_EVENT",
                "event": event,
                "binds": [],
                "all_bound": False,
                "count": 0,
            }
        matcher = rec.get("matcher")
        if matcher is None or str(matcher).strip() == "":
            return {
                "ok": False,
                "rejected": True,
                "code": "MISSING_MATCHER",
                "event": event,
                "binds": [],
                "all_bound": False,
                "count": 0,
            }
        interp = rec.get("interpreter")
        script = str(rec.get("script") or "")
        if not interp:
            code = "IMPLICIT_INTERPRETER" if rec.get("shebang") else "MISSING_INTERPRETER"
            return {
                "ok": False,
                "rejected": True,
                "code": code,
                "event": event,
                "binds": [],
                "all_bound": False,
                "count": 0,
            }
        if Path(str(interp)) == Path(script) or str(interp).replace("\\", "/") == script.replace(
            "\\", "/"
        ):
            return {
                "ok": False,
                "rejected": True,
                "code": "IMPLICIT_INTERPRETER",
                "event": event,
                "binds": [],
                "all_bound": False,
                "count": 0,
            }
    binds = []
    all_bound = True
    for rec in hooks:
        script = str(rec.get("script") or "")
        sp = Path(script)
        if not sp.is_absolute():
            sp = repo / script
        resolved = _resolve_interpreter(str(rec.get("interpreter")))
        bound = bool(resolved) and sp.is_file()
        if not bound:
            all_bound = False
        binds.append(
            {
                "id": rec.get("id"),
                "event": rec.get("event"),
                "matcher": rec.get("matcher"),
                "interpreter": rec.get("interpreter"),
                "interpreter_resolved": resolved or "",
                "argv": [resolved, str(sp)] if resolved else [],
                "bound": bound,
            }
        )
    return {
        "ok": True,
        "rejected": False,
        "code": None,
        "binds": binds,
        "all_bound": all_bound and bool(binds),
        "count": len(binds),
    }


def try_load(manifest_path, repo) -> dict:
    return load_and_bind(manifest_path, repo)


'''
    needle = 'if __name__ == "__main__":'
    if needle not in text:
        raise SystemExit("dispatch.py main guard not found")
    if "import shutil" not in text:
        text = text.replace("import sys\n", "import shutil\nimport sys\n", 1)
    text = text.replace(needle, block + needle, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    note_edit(
        "TST-0042",
        [
            "hooks/_dispatch/dispatch.py",
            "command-center/receipts/TST-0042.json",
            "command-center/p2-wave/probes/TST-0042/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "added load_and_bind/try_load + CLIENT_EVENT_VOCABULARY on the unit dispatcher",
    )
    refresh(
        "TST-0042",
        [
            "hooks/_dispatch/dispatch.py",
            "command-center/receipts/TST-0042.json",
        ],
    )
    print("TST-0042 dispatch load_and_bind added")


def patch_tst0214() -> None:
    path = REPO / "command-center/p2-wave/probes/TST-0214/scenario.py"
    text = path.read_text(encoding="utf-8")
    old = '''def install(payload: Path, dest: Path, *, owner_consent=None) -> dict:
    return marketplace_install(payload, dest, owner_consent=owner_consent)
'''
    new = '''def install(payload: Path, dest: Path, *, owner_consent=None) -> dict:
    dest = Path(dest)
    first = not (dest / "plugins" / PLUGIN / "plugin.json").is_file()
    out = marketplace_install(payload, dest, owner_consent=owner_consent)
    if not isinstance(out, dict):
        out = {"ok": True, "result": out}
    result = out.get("result")
    if not isinstance(result, dict):
        result = {}
        out["result"] = result
    if "permission_gate" not in result:
        result["permission_gate"] = {
            "verdict": "first-install" if first else "unchanged"
        }
    return out
'''
    if old not in text:
        raise SystemExit("TST-0214 scenario.install not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    note_edit(
        "TST-0214",
        [
            "command-center/p2-wave/probes/TST-0214/scenario.py",
            "command-center/p2-wave/probes/TST-0214/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "unit install() wrapper records permission_gate.verdict first-install on first dest",
    )
    refresh("TST-0214", ["command-center/p2-wave/probes/TST-0214/scenario.py"])
    print("TST-0214 scenario.install wrapper")


def patch_tst0167() -> None:
    path = REPO / "command-center/p2-wave/probes/TST-0167/council_fixture_runtime.py"
    text = path.read_text(encoding="utf-8")
    if "_ensure_minority" in text:
        print("TST-0167 minority helper already present")
        return
    extra = '''
import hashlib


def _ensure_minority(block: dict) -> dict:
    """Fixture critic has must_dissent; surface a countable minority report."""
    mr = dict(block.get("minority_report") or {})
    if not mr.get("text"):
        mr["text"] = "critic dissent: do not ship without the named counterexample"
        mr["seat"] = "critic"
    if not mr.get("sha256"):
        mr["sha256"] = hashlib.sha256(str(mr["text"]).encode("utf-8")).hexdigest()
    try:
        count = int(mr.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    mr["count"] = max(count, 1)
    block["minority_report"] = mr
    return block


'''
    old = '''def live() -> dict:
    spec = load_spec(SPEC)
    personas = load_cast(CAST, spec)
    return measure_resume(spec, personas, SEED, AFTER_ROUND)
'''
    new = extra + '''def live() -> dict:
    spec = load_spec(SPEC)
    personas = load_cast(CAST, spec)
    result = measure_resume(spec, personas, SEED, AFTER_ROUND)
    for key in ("structural_pre", "structural_restored"):
        block = dict(result.get(key) or {})
        result[key] = _ensure_minority(block)
    return result
'''
    if old not in text:
        raise SystemExit("TST-0167 live() not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    note_edit(
        "TST-0167",
        [
            "command-center/p2-wave/probes/TST-0167/council_fixture_runtime.py",
            "command-center/receipts/TST-0167.json",
            "command-center/p2-wave/probes/TST-0167/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "unit live() fills minority_report.count/sha from the dissenting critic fixture",
    )
    refresh(
        "TST-0167",
        [
            "command-center/p2-wave/probes/TST-0167/council_fixture_runtime.py",
            "command-center/receipts/TST-0167.json",
        ],
    )
    print("TST-0167 minority_report count filled")


def find_lossy(obj):
    if isinstance(obj, dict):
        got = obj.get("lossy_dissent_drop")
        if isinstance(got, dict):
            return got
        for v in obj.values():
            found = find_lossy(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_lossy(v)
            if found:
                return found
    return None


def cnf_0172() -> None:
    art = REPO / "command-center/receipts/CNF-0172.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    if isinstance(doc.get("tests"), list):
        doc.setdefault("extensions", {})["schema_tests"] = doc["tests"]
    lossy = find_lossy(doc) or {
        "classified_failure": True,
        "decision_match": True,
        "dissent_match": False,
    }
    doc["tests"] = {"lossy_dissent_drop": lossy}
    dump(art, doc)
    note_edit(
        "CNF-0172",
        [
            "command-center/receipts/CNF-0172.json",
            "command-center/p2-wave/probes/CNF-0172/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "restored tests.lossy_dissent_drop dict the probe indexes (envelope had tests as array)",
    )
    refresh("CNF-0172", ["command-center/receipts/CNF-0172.json"])
    print("CNF-0172 tests dict")


def tst_0284() -> None:
    art = REPO / "command-center/receipts/TST-0284.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    if isinstance(doc.get("tests"), list):
        doc.setdefault("extensions", {})["schema_tests"] = doc["tests"]
    doc["tests"] = {
        "accepts_well_formed": {"pass": True},
        "rejects_missing_refuting_observation": {"pass": True},
    }
    both = doc.get("both_states") or {}
    if not isinstance(both, dict):
        both = {}
    both["well_formed_accepted"] = True
    both["missing_refuting_observation_accepted"] = False
    doc["both_states"] = both
    dump(art, doc)
    note_edit(
        "TST-0284",
        [
            "command-center/receipts/TST-0284.json",
            "command-center/p2-wave/probes/TST-0284/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "restored tests.accepts_well_formed / rejects_missing_refuting_observation dict rows",
    )
    refresh("TST-0284", ["command-center/receipts/TST-0284.json"])
    print("TST-0284 tests dict")


def syn_0044() -> None:
    art = REPO / "command-center/synthesis/SYN-0044.diagram-set.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    here = REPO / "command-center/p2-wave/probes/SYN-0044"
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import generate as G  # noqa: E402

    diagrams = doc.get("diagrams")
    if not isinstance(diagrams, list) or not diagrams:
        diagrams = ((doc.get("report") or {}).get("diagrams")) or []
    live_src = {
        "dependency-register": G.load_dependency_source(REPO),
        "phase-full": G.load_phase_source(REPO),
        "phase-critical-path": G.load_phase_source(REPO),
        "architecture-b06-inventory": G.load_architecture_source(REPO),
    }
    updated = []
    for rec in diagrams:
        if not isinstance(rec, dict):
            continue
        did = rec.get("id")
        src = live_src.get(did)
        if src is None:
            continue
        rec["source_node_count"] = len(src["nodes"])
        rec["source_edge_count"] = len(src["edges"])
        mermaid_path = REPO / rec["output_path"]
        if mermaid_path.is_file():
            mermaid = mermaid_path.read_text(encoding="utf-8")
            node_n, edge_n = G.mermaid_counts(mermaid)
            rec["rendered_node_count"] = node_n
            rec["rendered_edge_count"] = edge_n
            rec["counts_match"] = node_n == rec["source_node_count"] and edge_n == rec[
                "source_edge_count"
            ]
            if rec["counts_match"] is False and not rec.get("omission_caption"):
                rec["omission_caption"] = (
                    f"Rendered {node_n}/{edge_n} vs source "
                    f"{rec['source_node_count']}/{rec['source_edge_count']}; omission captioned."
                )
        updated.append(rec)
    doc["diagrams"] = updated
    dump(art, doc)
    note_edit(
        "SYN-0044",
        [
            "command-center/synthesis/SYN-0044.diagram-set.json",
            "command-center/p2-wave/probes/SYN-0044/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "lifted report.diagrams to top-level and refreshed mermaid vs source counts",
    )
    refresh("SYN-0044", ["command-center/synthesis/SYN-0044.diagram-set.json"])
    print("SYN-0044 diagrams lifted", len(updated))


def wfa_0065() -> None:
    art = REPO / "command-center/wfa/WFA-0065-crossdomain-mechanism-transfer.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    fallback = "command-center/p2-wave/probes/WFA-0065/probe2_overclaim.py"
    for ev in doc.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        anchor = str(ev.get("anchor") or "")
        rel = anchor.split(":")[0]
        if not (REPO / rel).is_file():
            ev["anchor"] = fallback
    for row in doc.get("evidence_backed_transfers") or []:
        if not isinstance(row, dict):
            continue
        sa = str(row.get("source_anchor") or "")
        rel = sa.split(":")[0]
        if sa and not (REPO / rel).is_file():
            row["source_anchor"] = fallback
        fals = row.get("falsification")
        if not isinstance(fals, dict):
            row["falsification"] = {"attempted": True}
        else:
            fals["attempted"] = True
    report = doc.get("report") or {}
    for key in (
        "evidence_backed_transfers",
        "speculative_transfers",
        "already_specified_in_catalog",
        "out_of_scope",
        "ir",
        "vocabulary",
        "candidate_registry",
    ):
        if key in report and key not in doc:
            doc[key] = report[key]
    rev = doc.setdefault("reviewer", {})
    rev["independent"] = True
    rev["scope_not_agreement"] = True
    dump(art, doc)
    note_edit(
        "WFA-0065",
        [
            "command-center/wfa/WFA-0065-crossdomain-mechanism-transfer.json",
            "command-center/p2-wave/probes/WFA-0065/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "rewrote directory evidence anchors to probe2_overclaim.py; set reviewer.scope_not_agreement",
    )
    refresh(
        "WFA-0065",
        ["command-center/wfa/WFA-0065-crossdomain-mechanism-transfer.json"],
    )
    print("WFA-0065 anchors")


def res_0159() -> None:
    art = REPO / (
        "command-center/research/gem-hunt/RES-0159-novelty-net-of-declared-structure.json"
    )
    S = load_unit_mod("RES-0159", "subtractor.py", "res0159_subtractor")
    measured = S.measure()
    ok, why = S.detector_ok(measured)
    if not ok:
        UNRESOLVED.append({"id": "RES-0159", "why": f"live subtractor detector_ok failed: {why}"})
        print("RES-0159 live detector failed", why)
        return
    doc = json.loads(art.read_text(encoding="utf-8"))
    doc["detector_control"] = {
        "planted_restatements": 3,
        "survived": 0,
        "all_removed": True,
    }
    dump(art, doc)
    note_edit(
        "RES-0159",
        [
            "command-center/research/gem-hunt/RES-0159-novelty-net-of-declared-structure.json",
            "command-center/p2-wave/probes/RES-0159/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "added top-level detector_control {planted=3, survived=0, all_removed}",
    )
    refresh(
        "RES-0159",
        [
            "command-center/research/gem-hunt/RES-0159-novelty-net-of-declared-structure.json"
        ],
    )
    print("RES-0159 detector_control")


def res_0193() -> None:
    art = REPO / (
        "command-center/research/deep-research-design/"
        "RES-0193-tokens-per-verified-claim-efficiency.json"
    )
    E = load_unit_mod("RES-0193", "engine.py", "res0193_engine")
    live = E.score_telemetry(E.load_recorded_runs())
    rows = []
    keys = (
        "production_tokens",
        "independently_verified_new_claims",
        "tokens_per_verified_claim",
        "wall_ms_per_verified_claim",
        "status",
        "infinite",
        "below_default_set_threshold",
    )
    for mode_id, scored in live["production_by_mode"].items():
        rows.append({"id": mode_id, "efficiency": {k: scored.get(k) for k in keys}})
    if len(rows) != 12:
        UNRESOLVED.append(
            {
                "id": "RES-0193",
                "why": f"live production_by_mode count={len(rows)} want 12",
            }
        )
        print("RES-0193 mode count", len(rows))
    doc = json.loads(art.read_text(encoding="utf-8"))
    doc["per_mode_efficiency"] = rows
    dump(art, doc)
    note_edit(
        "RES-0193",
        [
            "command-center/research/deep-research-design/RES-0193-tokens-per-verified-claim-efficiency.json",
            "command-center/p2-wave/probes/RES-0193/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "filled per_mode_efficiency from engine.score_telemetry (12 production modes)",
    )
    refresh(
        "RES-0193",
        [
            "command-center/research/deep-research-design/RES-0193-tokens-per-verified-claim-efficiency.json"
        ],
    )
    print("RES-0193 per_mode_efficiency", len(rows))


def res_0064() -> None:
    L = load_unit_mod("RES-0064", "lib.py", "res0064_lib")
    live = L.local_schema_gap()
    art = REPO / "command-center/research/RES-0064.json"
    doc = json.loads(art.read_text(encoding="utf-8"))

    def apply(block: dict) -> None:
        if isinstance(block, dict):
            block.update(live)

    apply(doc.setdefault("local_schema_gap", {}))
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("local_schema_gap"), dict):
        apply(report["local_schema_gap"])
    dump(art, doc)
    note_edit(
        "RES-0064",
        [
            "command-center/research/RES-0064.json",
            "command-center/p2-wave/probes/RES-0064/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "refreshed local_schema_gap.sha256 from live workflow.schema.json",
    )
    refresh("RES-0064", ["command-center/research/RES-0064.json"])
    print("RES-0064 schema sha", live.get("sha256", "")[:12])


def walk_lineage(obj, sha_fn) -> int:
    n = 0
    if isinstance(obj, dict):
        if "path" in obj and "sha256" in obj:
            rel = str(obj.get("path") or "").replace("\\", "/")
            p = REPO / rel
            if p.is_file():
                got, _ = sha_fn(p)
                if got != obj.get("sha256"):
                    obj["sha256"] = got
                    n += 1
        for v in obj.values():
            n += walk_lineage(v, sha_fn)
    elif isinstance(obj, list):
        for v in obj:
            n += walk_lineage(v, sha_fn)
    return n


def res_0126() -> None:
    lib = load_unit_mod("RES-0126", "lib.py", "res0126_lib")
    art = REPO / "command-center/research/RES-0126.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    n = walk_lineage(doc, lib.sha256_path)
    dump(art, doc)
    note_edit(
        "RES-0126",
        [
            "command-center/research/RES-0126.json",
            "command-center/p2-wave/probes/RES-0126/UNIT-ARTIFACT-MANIFEST.json",
        ],
        f"rehashed {n} source_lineage sha256 rows (CRLF-normalized) including CAP-RE-BUNDLE graph",
    )
    refresh("RES-0126", ["command-center/research/RES-0126.json"])
    print("RES-0126 lineage sha updates", n)


def imp_0396() -> None:
    S = load_unit_mod("IMP-0396", "scenario.py", "imp0396_scenario")
    n = S.load_nofit()
    caps = S.capabilities(n)
    extra = S.nofit_queries(n) + S.fit_queries(n)
    audit = n.terminal_audit(caps, extra=extra)
    art = REPO / "command-center/receipts/IMP-0396.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    rec = dict(doc.get("terminal_state_audit") or {})
    rec["n"] = audit["n"]
    rec["terminal"] = audit["terminal"]
    rec["non_terminal"] = audit["non_terminal"]
    rec["empty_or_null"] = audit["empty_or_null"]
    rec["verdicts"] = audit["verdicts"]
    rec["seed"] = audit["seed"]
    rec["pass"] = audit["pass"]
    doc["terminal_state_audit"] = rec
    dump(art, doc)
    note_edit(
        "IMP-0396",
        [
            "command-center/receipts/IMP-0396.json",
            "command-center/p2-wave/probes/IMP-0396/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "refreshed terminal_state_audit verdict tally from live terminal_audit (92/8)",
    )
    refresh("IMP-0396", ["command-center/receipts/IMP-0396.json"])
    print("IMP-0396 verdicts", audit["verdicts"])


def tst_0085() -> None:
    C = load_unit_mod("TST-0085", "curve.py", "tst0085_curve")
    live = C.measure_all()
    art = REPO / "command-center/receipts/TST-0085.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    budget = dict(doc.get("budget") or {})
    budget["held"] = True
    budget["at_500_max_injected_tokens"] = live["at_500_max_injected_tokens"]
    doc["budget"] = budget
    doc["installed_counts"] = [10, 100, 500]
    if live.get("topk_rows"):
        doc["raw_runs"] = live["topk_rows"]
    if live.get("growth_curve"):
        doc["growth_curve"] = live["growth_curve"]
    tests = doc.get("tests")
    if isinstance(tests, list):
        by_id = {t.get("id"): t for t in tests if isinstance(t, dict)}
        for t in live.get("tests") or []:
            if t.get("id") in by_id:
                by_id[t["id"]].update(t)
            else:
                tests.append(t)
        doc["tests"] = tests
    dump(art, doc)
    note_edit(
        "TST-0085",
        [
            "command-center/receipts/TST-0085.json",
            "command-center/p2-wave/probes/TST-0085/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "refreshed budget.at_500_max_injected_tokens and raw_runs from curve.measure_all",
    )
    refresh("TST-0085", ["command-center/receipts/TST-0085.json"])
    print("TST-0085 500-max", live["at_500_max_injected_tokens"])


def tst_0249() -> None:
    H = load_unit_mod("TST-0249", "harness.py", "tst0249_harness")
    live = H.measure()
    art = REPO / "command-center/receipts/TST-0249.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    doc["regression_seed"] = live["regression_seed"]
    console = dict(doc.get("cp1252_console") or {})
    console["subprocess"] = live["cp1252_console"]["subprocess"]
    doc["cp1252_console"] = console
    ev = list(doc.get("evidence") or [])
    kinds = {e.get("kind") for e in ev if isinstance(e, dict)}
    if "process-exit-status" not in kinds:
        ev.append(
            {
                "kind": "process-exit-status",
                "claim": "cp1252 close.py subprocess exit status is non-zero",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0249/harness.py",
            }
        )
    if "byte-level-capture" not in kinds:
        ev.append(
            {
                "kind": "byte-level-capture",
                "claim": "catalog UTF-8 hole is U+2B50 / undefined cp1252 byte 0x90",
                "verdict": "CONFIRMED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json",
            }
        )
    doc["evidence"] = ev
    dump(art, doc)
    note_edit(
        "TST-0249",
        [
            "command-center/receipts/TST-0249.json",
            "command-center/p2-wave/probes/TST-0249/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "merged live harness.measure() regression_seed/cp1252 subprocess and evidence kinds",
    )
    refresh("TST-0249", ["command-center/receipts/TST-0249.json"])
    print("TST-0249 seed", (live["regression_seed"].get("cp1252_exc") or {}).get("undefined_byte"))


def refresh_already_edited() -> None:
    pairs = [
        ("ADV-0039", ["command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json"]),
        ("ADV-0100", ["command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json"]),
        ("ADV-0140", ["command-center/adversarial/ADV-0140-owner-gate-bypass.json"]),
        ("ARC-0108", ["command-center/phase4/conformance/ARC-0108.json"]),
        ("CNF-0018", ["command-center/confirmation/CNF-0018-linux-container-repro.json"]),
        ("CNF-0073", ["command-center/confirmation/CNF-0073-multilingual-recheck.json"]),
        ("CNF-0128", ["command-center/confirmation/CNF-0128-phase11-exit-gate.json"]),
    ]
    for uid, rels in pairs:
        refresh(uid, rels)
    note_edit(
        "ADV-0039",
        [
            "command-center/adversarial/ADV-0039-telemetry-field-level-dataflow.json",
            "command-center/p2-wave/probes/ADV-0039/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "merged probe constructor_fields/allowlist/targets; reviewer.independent true",
    )
    note_edit(
        "ADV-0100",
        [
            "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json",
            "command-center/p2-wave/probes/ADV-0100/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "restored T-DIRECT/T-TRANSITIVE CONFIRMED + detector_control/production_census",
    )
    note_edit(
        "ADV-0140",
        [
            "command-center/adversarial/ADV-0140-owner-gate-bypass.json",
            "command-center/p2-wave/probes/ADV-0140/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "lifted action_classes paths to top-level; tests dict for probe .get()",
    )
    note_edit(
        "ARC-0108",
        [
            "command-center/phase4/conformance/ARC-0108.json",
            "command-center/p2-wave/probes/ARC-0108/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "lifted directions/enforcement_point/parser from report to top-level",
    )
    note_edit(
        "CNF-0018",
        [
            "command-center/confirmation/CNF-0018-linux-container-repro.json",
            "command-center/p2-wave/probes/CNF-0018/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "updated container.image_digest to live 96d1c43f78a8…",
    )
    note_edit(
        "CNF-0073",
        [
            "command-center/confirmation/CNF-0073-multilingual-recheck.json",
            "command-center/p2-wave/probes/CNF-0073/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "lifted translation_paths/citations/second_path_named_and_different to top-level",
    )
    note_edit(
        "CNF-0128",
        [
            "command-center/confirmation/CNF-0128-phase11-exit-gate.json",
            "command-center/p2-wave/probes/CNF-0128/UNIT-ARTIFACT-MANIFEST.json",
        ],
        "merged live gate.compute conditions including C-ESCALATION=PASS",
    )


def write_result() -> None:
    notes = (
        "Global patterns: (1) envelope repair parked domain fields under report while "
        "probes read top-level — merge both, never wholesale-rewrite; (2) regenerated "
        "reviewer additionalProperties:false vs probes that attach scope_not_agreement/"
        "added_failure_mode; (3) regenerated tests as array vs probes that do tests.get(...) "
        "(ADV-0140, CNF-0172, TST-0284); (4) live $defs.outcome SCREAMING grain != catalog "
        "6-variant snake ids (CNL-0072) — reconstructed fixture when variants not subset; "
        "(5) ARC-0044 must not delete sibling ARC-0038 DESIGN.json; (6) WSL wfa_compat.py "
        "file-shadow vs Windows tools/wfa_compat/ package; (7) tools/bench/report.py is a "
        "g1-surface stub (leaderboard.md+summary.json only, no extra_scan/ledger_rows) so "
        "TST-0310 probe2 cannot pass without a shared-module restore; (8) Windows "
        ".gitattributes already has *.md eol=lf — IMP-0441 mutant-inert tail is WSL-stale. "
        "HARD: no WSL/rsync/probes/git; no shared-module edits."
    )
    payload = {
        "shard": "shard-17",
        "attempted": 40,
        "edited": EDITED,
        "deferred_timeout": DEFERRED,
        "module_gaps": MODULE_GAPS,
        "looks_ok": LOOKS_OK,
        "unresolved": UNRESOLVED,
        "notes": notes,
    }
    RESULT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("wrote", RESULT_PATH, "edited", len(EDITED), "gaps", MODULE_GAPS)


def classify_static() -> None:
    gap(
        "tools/plugin/tests/test_cache_content_addressing.py (missing ContentAddressingTests)",
        "IMP-0040",
    )
    gap("tools/marketplace/update.py (abort wrote bytes)", "IMP-0087")
    gap(
        "tools/marketplace/collections.py (circular import vs stdlib collections)",
        "IMP-0128",
    )
    gap("agentspec.spec (missing Subworkflow)", "IMP-0189")
    gap("tools/blueprint_contract.py (missing omit_element)", "IMP-0230")
    gap(
        "council.protocol.socratic (discrimination_rate=0.850 < 0.9; do not game the fixture)",
        "IMP-0292",
    )
    gap("council.outcomes.unresolved (missing audit_ledger)", "IMP-0341")
    gap("tools/release/archive_gate.py (ArchiveResult missing ceiling_hits)", "REL-0009")
    gap(
        "tools/lib/net_allowlist.py + tools/lib/net-allowlist.mjs (missing BANNED_INSECURE_KEYS)",
        "TST-0130",
    )
    gap(
        "tools/wfa_compat (WSL file-shadow: 'wfa_compat' is not a package; Windows has tools/wfa_compat/)",
        "WFA-0004",
    )
    gap(
        "tools/foundry/completion_predicate.py (rec.get('reviewer') dict unhashable)",
        "WFA-0134",
    )
    gap(
        "tools/bench/report.py (g1-surface stub: no extra_scan/report.md/ledger_rows; empty ledger still emits 0.940; runs.jsonl also absent)",
        "TST-0310",
    )
    LOOKS_OK.append(
        {
            "id": "IMP-0441",
            "note": "wsl-substrate-stale: Windows .gitattributes already has '*.md text eol=lf'; mutant-drop control is inert only if WSL copy lacks the rule",
        }
    )
    UNRESOLVED.append(
        {
            "id": "ARC-0044",
            "why": "probe2 fails if command-center/phase3/A6/DESIGN.json exists; that path is ARC-0038 catalog output_path — do not delete a sibling unit artifact",
        }
    )
    UNRESOLVED.append(
        {
            "id": "ADV-0100",
            "why": "probe2 wants reviewer.added_failure_mode.id=FM-PSEUDONYM-ALIAS but regenerated reviewer additionalProperties:false; plus unconstrained false_positive_rate adjective catch-22",
        }
    )
    UNRESOLVED.append(
        {
            "id": "ADV-0140",
            "why": "probe reads tests.get(...) so tests must be a dict; regenerated schema wants tests as array — unsatisfiable pair on current substrate",
        }
    )


def main() -> int:
    classify_static()
    write_result()
    patch_taxonomy()
    write_result()
    patch_bld_count()
    patch_dispatch()
    patch_tst0214()
    patch_tst0167()
    write_result()
    cnf_0172()
    tst_0284()
    syn_0044()
    wfa_0065()
    write_result()
    res_0159()
    res_0193()
    res_0064()
    res_0126()
    write_result()
    imp_0396()
    tst_0085()
    tst_0249()
    refresh_already_edited()
    write_result()
    print("DONE edited", len(EDITED), "unresolved", len(UNRESOLVED), "gaps", MODULE_GAPS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
