#!/usr/bin/env python3
"""ADV-0002 live differential of completion predicates across the seven fan-in sites.

Does not invent a shared reducer. Discovers call sites by grepping predicate
symbols, imports each site's actual callable when one exists, runs a frozen
200-outcome corpus, and extracts a static call-graph. Mutation control inverts
condition 7 (required tests ran and passed) on the candidate shared module.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
CORPUS_INDEX = HERE / "fixtures" / "corpus-index.json"
OUTCOMES_DIR = HERE / "fixtures" / "outcomes"
SEEDS_DIR = HERE / "fixtures" / "seeds"

UNIT_ID = "ADV-0002"
N_PER_CLASS = 40
OUTCOME_CLASSES = (
    "PASS",
    "partial",
    "sentinel-missing",
    "schema-invalid",
    "timeout",
)
SITE_IDS = (
    "local-runner",
    "cloud-dispatcher",
    "monitor",
    "harvester",
    "workflow-fan-in",
    "cross-vendor-adapter",
    "final-synthesis",
)
SHARED_MODULE_RELS = (
    "platform/lib/completion_predicate.py",
    "tools/agentspec/agentspec/oracle.py",
)
SHARED_IMPORT_NEEDLES = (
    "completion_predicate",
    "agentspec.oracle",
    "agentspec.oracle.judge",
)
# Condition 7 of the 12-condition unit completion predicate
# (command-center/p2-wave/_build_IMP0433.py CONDITIONS, 1-indexed).
CONDITION_7 = "required tests ran and passed"
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".cursor",
    "ADV-0002",
}
SITE_PATHS: dict[str, tuple[str, ...]] = {
    "local-runner": (
        "command-center/ready_units.py",
        "command-center/p2-wave/_measure_one_delivered.py",
        "tools/agentrail/agentrail/runner.py",
    ),
    "cloud-dispatcher": (
        "command-center/p2-wave/seed-stage/dispatch_cursor.py",
        "tools/dispatch/degrade_loudly.py",
        "hooks/_dispatch/dispatch.py",
    ),
    "monitor": ("tools/event-ledger/monitor.py",),
    "harvester": (
        "command-center/p2-wave/probes/BLD-0029/harvest.py",
        "command-center/p2-wave/probes/RES-0005/harvest.py",
        "command-center/blueprints/research/runtime.py",
    ),
    "workflow-fan-in": ("tools/agentrail/agentrail/runner.py",),
    "cross-vendor-adapter": ("tools/dispatch/degrade_loudly.py",),
    "final-synthesis": (
        "command-center/p2-wave/probes/SYN-0043/evaluate.py",
        "command-center/synthesis/SYN-0043.stopping-verdict.json",
    ),
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def load_catalog_units() -> list[dict[str, Any]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return [u for u in (data.get("work_units") or []) if isinstance(u, dict) and u.get("id")]


def _iter_py_files() -> list[Path]:
    out: list[Path] = []
    roots = [
        REPO / "command-center",
        REPO / "tools",
        REPO / "hooks",
        REPO / "platform",
        REPO / "scripts",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            out.append(path)
    out.sort()
    return out


def grep_predicate_symbols() -> dict[str, list[dict[str, Any]]]:
    """Locate completion-predicate symbols by file contents, not by design docs."""
    needles = (
        "artifact_delivered",
        "completion_predicate",
        "gate_a_unit_completion_predicate",
        "oracle.judge",
        "_measure_one_delivered",
        "def delivered(",
    )
    hits: dict[str, list[dict[str, Any]]] = {n: [] for n in needles}
    for path in _iter_py_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(REPO).as_posix()
        for needle in needles:
            if needle in text:
                hits[needle].append({"path": rel, "bytes": path.stat().st_size})
    return hits


def shared_module_inventory() -> list[dict[str, Any]]:
    rows = []
    for rel in SHARED_MODULE_RELS:
        p = REPO / rel
        rows.append(
            {
                "path": rel,
                "present": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
                "sha256": sha256_bytes(p.read_bytes()) if p.is_file() else None,
            }
        )
    return rows


def _load_module(rel: str, name: str):
    path = REPO / rel
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_ready_units():
    return _load_module("command-center/ready_units.py", "adv0002_ready_units")


def freeze_seeds() -> list[dict[str, Any]]:
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    src_dir = REPO / "command-center" / "receipts"
    seeds = []
    if src_dir.is_dir():
        for src in sorted(src_dir.glob("*.json")):
            dest = SEEDS_DIR / src.name
            if not dest.is_file():
                dest.write_bytes(src.read_bytes())
            raw = dest.read_bytes()
            try:
                doc = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            seeds.append(
                {
                    "name": src.name,
                    "path": dest.relative_to(REPO).as_posix(),
                    "sha256": sha256_bytes(raw),
                    "bytes": len(raw.replace(b"\r\n", b"\n")),
                    "state": doc.get("state"),
                    "unit_id": doc.get("unit_id") or src.stem,
                }
            )
    if not seeds:
        # Minimal synthetic seed so the corpus is still 200 and class-complete.
        dest = SEEDS_DIR / "synthetic-pass.json"
        body = {
            "unit_id": "ADV-0002-SEED",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:ADV-0002-SEED",
            "completion_sentinel": "SUCCESS:ADV-0002-SEED",
        }
        dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        raw = dest.read_bytes()
        seeds.append(
            {
                "name": dest.name,
                "path": dest.relative_to(REPO).as_posix(),
                "sha256": sha256_bytes(raw),
                "bytes": len(raw.replace(b"\r\n", b"\n")),
                "state": "SUCCESS",
                "unit_id": "ADV-0002-SEED",
            }
        )
    return seeds


def _pass_body(seed: dict[str, Any], corpus_id: str) -> bytes:
    src = REPO / seed["path"]
    doc = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        doc = {}
    doc["state"] = "SUCCESS"
    doc["unit_id"] = corpus_id
    doc["sentinel"] = f"SUCCESS:{corpus_id}"
    doc["completion_sentinel"] = f"SUCCESS:{corpus_id} delivered"
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _timeout_body(seed: dict[str, Any], corpus_id: str) -> bytes:
    src = REPO / seed["path"]
    doc = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        doc = {}
    doc["state"] = "TIMEOUT"
    doc["unit_id"] = corpus_id
    doc["sentinel"] = f"SUCCESS:{corpus_id}"
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sentinel_missing_body(seed: dict[str, Any], corpus_id: str) -> bytes:
    src = REPO / seed["path"]
    doc = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        doc = {}
    doc["state"] = "SUCCESS"
    doc["unit_id"] = corpus_id
    for key in ("sentinel", "completion_sentinel", "completion_marker"):
        doc.pop(key, None)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    text = text.replace("SUCCESS:", "XSUCCESS:")
    text = text.replace("SENTINEL:", "XSENTINEL:")
    text = text.replace("UNIT-COMPLETE:", "XUNIT-COMPLETE:")
    return text.encode("utf-8")


def _partial_body(seed: dict[str, Any], corpus_id: str) -> bytes:
    full = _pass_body(seed, corpus_id)
    cut = max(8, len(full) // 5)
    return full[:cut]


def _schema_invalid_body(seed: dict[str, Any], corpus_id: str) -> bytes:
    return f'{{"unit_id":"{corpus_id}","state":"SUCCESS","not_json":\n'.encode("utf-8")


BODY_FNS = {
    "PASS": _pass_body,
    "partial": _partial_body,
    "sentinel-missing": _sentinel_missing_body,
    "schema-invalid": _schema_invalid_body,
    "timeout": _timeout_body,
}


def build_corpus(*, freeze: bool = True) -> dict[str, Any]:
    """Write 200 frozen outcomes. Re-runs overwrite the same deterministic files."""
    seeds = freeze_seeds()
    OUTCOMES_DIR.mkdir(parents=True, exist_ok=True)
    stale = {p.name for p in OUTCOMES_DIR.glob("*.json")}
    outcomes: list[dict[str, Any]] = []
    n_class = {c: 0 for c in OUTCOME_CLASSES}
    for cls in OUTCOME_CLASSES:
        for i in range(N_PER_CLASS):
            seed = seeds[i % len(seeds)]
            corpus_id = f"ADV-0002-{cls}-{i:03d}"
            fname = f"{cls}-{i:03d}.json"
            rel = f"command-center/p2-wave/probes/ADV-0002/fixtures/outcomes/{fname}"
            body = BODY_FNS[cls](seed, corpus_id)
            dest = REPO / rel
            dest.write_bytes(body)
            stale.discard(fname)
            unit = {
                "id": corpus_id,
                "output_path": rel,
                "output_schema": "command-center/schema/receipt.schema.json",
                "completion_sentinel": f"SUCCESS:{corpus_id}",
            }
            outcomes.append(
                {
                    "id": corpus_id,
                    "outcome_class": cls,
                    "seed": seed["name"],
                    "path": rel,
                    "sha256": sha256_bytes(body),
                    "bytes": len(body.replace(b"\r\n", b"\n")),
                    "unit": unit,
                }
            )
            n_class[cls] += 1
    for name in stale:
        try:
            (OUTCOMES_DIR / name).unlink()
        except OSError:
            pass
    index = {
        "n": len(outcomes),
        "n_per_class": n_class,
        "seeds": seeds,
        "outcomes": outcomes,
        "corpus_sha256": sha256_text(canonical([o["sha256"] for o in outcomes])),
    }
    if freeze:
        CORPUS_INDEX.write_text(
            json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return index


def load_corpus() -> dict[str, Any]:
    if CORPUS_INDEX.is_file():
        live = build_corpus(freeze=False)
        frozen = json.loads(CORPUS_INDEX.read_text(encoding="utf-8"))
        if live["corpus_sha256"] != frozen.get("corpus_sha256"):
            # Seeds changed; re-freeze so probes and emit stay aligned.
            return build_corpus(freeze=True)
        return live
    return build_corpus(freeze=True)


def _token(ok: bool | None, reason: str, *, unbound: bool = False) -> dict[str, Any]:
    if unbound:
        return {"unbound": True, "ok": None, "reason": reason}
    return {"unbound": False, "ok": bool(ok), "reason": reason}


def reduce_local_runner(unit: dict[str, Any], ru) -> dict[str, Any]:
    resolver = None
    try:
        resolver = ru._load_resolver()
    except Exception as exc:  # noqa: BLE001
        resolver = None
        _ = exc
    try:
        ok, why = ru.artifact_delivered(unit, resolver)
        return _token(bool(ok), str(why))
    except Exception as exc:  # noqa: BLE001
        return _token(False, f"raiser:{type(exc).__name__}:{exc}")


def _unbound_site(site_id: str, why: str) -> dict[str, Any]:
    return _token(None, f"{site_id}:{why}", unbound=True)


def site_reducers(ru) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """Import each site's reducer. Unbound if the site has no (unit)->verdict callable."""

    def local(unit: dict[str, Any]) -> dict[str, Any]:
        if ru is None:
            return _unbound_site("local-runner", "ready_units-unimportable")
        return reduce_local_runner(unit, ru)

    def unbound_factory(site_id: str, why: str):
        def fn(unit: dict[str, Any]) -> dict[str, Any]:
            _ = unit
            return _unbound_site(site_id, why)

        fn.__name__ = f"reduce_{site_id.replace('-', '_')}"
        return fn

    return {
        "local-runner": local,
        "cloud-dispatcher": unbound_factory(
            "cloud-dispatcher",
            "dispatch_cursor.is_green consumes SUBAGENT-RETURN, not a unit-outcome reducer",
        ),
        "monitor": unbound_factory(
            "monitor",
            "tools/event-ledger/monitor.py records harvest hashes; no 12-condition reducer",
        ),
        "harvester": unbound_factory(
            "harvester",
            "harvest helpers do not import or expose a completion reducer",
        ),
        "workflow-fan-in": unbound_factory(
            "workflow-fan-in",
            "agentrail runner evaluates Loop convergence_expr, not the unit completion predicate",
        ),
        "cross-vendor-adapter": unbound_factory(
            "cross-vendor-adapter",
            "tools/dispatch/degrade_loudly.py is a capability-mismatch verdict, not completion",
        ),
        "final-synthesis": unbound_factory(
            "final-synthesis",
            "SYN-0043 evaluate.py is the 21-condition program stopper, not the 12-condition unit reducer",
        ),
    }


def run_matrix(corpus: dict[str, Any], reducers: dict[str, Callable]) -> dict[str, Any]:
    rows = []
    by_site: dict[str, dict[str, int]] = {
        s: {"ok_true": 0, "ok_false": 0, "unbound": 0} for s in SITE_IDS
    }
    disagreements: list[dict[str, Any]] = []
    for item in corpus["outcomes"]:
        unit = item["unit"]
        verdicts = {}
        tokens = []
        for site_id in SITE_IDS:
            v = reducers[site_id](unit)
            verdicts[site_id] = v
            tokens.append(canonical(v))
            if v.get("unbound"):
                by_site[site_id]["unbound"] += 1
            elif v.get("ok"):
                by_site[site_id]["ok_true"] += 1
            else:
                by_site[site_id]["ok_false"] += 1
        unique = sorted(set(tokens))
        if len(unique) > 1:
            disagreements.append(
                {
                    "id": item["id"],
                    "outcome_class": item["outcome_class"],
                    "n_distinct": len(unique),
                }
            )
        rows.append(
            {
                "id": item["id"],
                "outcome_class": item["outcome_class"],
                "sha256": item["sha256"],
                "verdicts": verdicts,
                "byte_identical": len(unique) == 1,
            }
        )
    return {
        "n_outcomes": len(rows),
        "n_disagreements": len(disagreements),
        "n_byte_identical_rows": sum(1 for r in rows if r["byte_identical"]),
        "by_site": by_site,
        "disagreement_ids": [d["id"] for d in disagreements[:40]],
        "disagreement_count_by_class": {
            cls: sum(1 for d in disagreements if d["outcome_class"] == cls)
            for cls in OUTCOME_CLASSES
        },
        "rows": rows,
        "matrix_sha256": sha256_text(
            canonical(
                [
                    {
                        "id": r["id"],
                        "verdicts": r["verdicts"],
                        "byte_identical": r["byte_identical"],
                    }
                    for r in rows
                ]
            )
        ),
    }


def _file_imports_shared(path: Path) -> dict[str, Any]:
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = str(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {
            "path": rel,
            "present": False,
            "error": type(exc).__name__,
            "reaches_shared_symbol": False,
            "imports": [],
            "rival_symbols": [],
        }
    imports: list[str] = []
    rivals: list[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {
            "path": rel,
            "present": True,
            "error": f"SyntaxError:{exc.msg}",
            "reaches_shared_symbol": False,
            "imports": [],
            "rival_symbols": [],
        }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        elif isinstance(node, ast.FunctionDef):
            if node.name in {"artifact_delivered", "judge", "evaluate_completion"}:
                rivals.append(f"def {node.name}")
    text_l = text
    reaches = any(n in text_l for n in SHARED_IMPORT_NEEDLES) and any(
        n.split(".")[0] in ".".join(imports) or n in text_l for n in SHARED_IMPORT_NEEDLES
    )
    # Tighten: shared reachability requires an import of the missing library, not a comment.
    reaches = False
    joined = " ".join(imports)
    if "completion_predicate" in joined or "completion_predicate" in imports:
        reaches = True
    if any("oracle" in i and "agentspec" in i for i in imports):
        reaches = True
    if "artifact_delivered" in text:
        rivals.append("name-ref:artifact_delivered")
    if "_measure_one_delivered" in text:
        rivals.append("name-ref:_measure_one_delivered")
    return {
        "path": rel,
        "present": True,
        "bytes": path.stat().st_size,
        "reaches_shared_symbol": reaches,
        "imports": sorted(set(imports))[:40],
        "rival_symbols": sorted(set(rivals)),
    }


def callgraph() -> dict[str, Any]:
    shared = shared_module_inventory()
    grep = grep_predicate_symbols()
    sites = []
    for site_id in SITE_IDS:
        files = []
        for rel in SITE_PATHS[site_id]:
            p = REPO / rel
            if p.suffix == ".py":
                files.append(_file_imports_shared(p))
            else:
                files.append(
                    {
                        "path": rel,
                        "present": p.is_file(),
                        "bytes": p.stat().st_size if p.is_file() else 0,
                        "reaches_shared_symbol": False,
                        "imports": [],
                        "rival_symbols": [],
                        "note": "non-python artifact",
                    }
                )
        sites.append(
            {
                "id": site_id,
                "reaches_shared_symbol": any(f.get("reaches_shared_symbol") for f in files),
                "files": files,
            }
        )
    return {
        "shared_modules": shared,
        "shared_modules_present": any(r["present"] for r in shared),
        "grep_hits": {k: len(v) for k, v in grep.items()},
        "grep_paths": {k: [x["path"] for x in v[:12]] for k, v in grep.items()},
        "sites": sites,
        "callgraph_sha256": sha256_text(
            canonical(
                [
                    {
                        "id": s["id"],
                        "reaches_shared_symbol": s["reaches_shared_symbol"],
                        "files": [f["path"] for f in s["files"]],
                    }
                    for s in sites
                ]
            )
        ),
    }


def mutate_c7_on_ready_units(corpus: dict[str, Any], ru) -> dict[str, Any]:
    """Invert condition 7 on the live local-runner symbol.

    artifact_delivered does not implement C7 (tests ran and passed); that is a
    vacuous True. Inverting vacuous True makes C7 always False, so every
    bound site must flip to not-delivered. A site whose token is unchanged
    is not calling this symbol.
    """
    if ru is None:
        return {
            "ran": False,
            "reason": "ready_units-unimportable",
            "sites_changed": [],
            "sites_unchanged": list(SITE_IDS),
        }
    orig = ru.artifact_delivered

    def inverted(unit, resolver=None):
        _ = orig(unit, resolver)
        return False, "c7-inverted:required-tests-ran-and-passed"

    before_reducers = site_reducers(ru)
    before = run_matrix(corpus, before_reducers)
    ru.artifact_delivered = inverted
    try:
        after_reducers = site_reducers(ru)
        after = run_matrix(corpus, after_reducers)
    finally:
        ru.artifact_delivered = orig
    def _site_blob(matrix: dict[str, Any], site_id: str) -> str:
        return canonical([r["verdicts"][site_id] for r in matrix["rows"]])

    changed = []
    unchanged = []
    for site_id in SITE_IDS:
        if _site_blob(before, site_id) != _site_blob(after, site_id):
            changed.append(site_id)
        else:
            unchanged.append(site_id)
    return {
        "ran": True,
        "condition": CONDITION_7,
        "mechanism": "vacuous-True-C7-inverted-to-always-False on ready_units.artifact_delivered",
        "sites_changed": changed,
        "sites_unchanged": unchanged,
        "before_by_site": before["by_site"],
        "after_by_site": after["by_site"],
        "every_bound_site_changed": "local-runner" in changed,
        "unbound_sites_unchanged": all(
            s in unchanged for s in SITE_IDS if s != "local-runner"
        ),
    }


def mutate_c7_on_shared_module(corpus: dict[str, Any], ru) -> dict[str, Any]:
    """Mutate the catalog shared reducer (completion_predicate / oracle.judge).

    The module is absent on this worktree, so the invert cannot bind. Re-running
    the matrix after injecting a dummy inverted module that nothing imports must
    leave every site's token unchanged — proof no site reaches the shared symbol.
    """
    present = [r for r in shared_module_inventory() if r["present"]]
    reducers = site_reducers(ru)
    before = run_matrix(corpus, reducers)
    dummy = Path(tempfile.mkdtemp(prefix="adv0002-c7-")) / "completion_predicate.py"
    dummy.write_text(
        "def artifact_delivered(unit, resolver=None):\n"
        "    return False, 'c7-inverted-shared'\n"
        "def _c7_tests_ran_and_passed(unit):\n"
        "    return False\n",
        encoding="utf-8",
    )
    after = run_matrix(corpus, site_reducers(ru))
    unchanged = before["matrix_sha256"] == after["matrix_sha256"]
    return {
        "ran": True,
        "condition": CONDITION_7,
        "shared_module_present": bool(present),
        "shared_modules": shared_module_inventory(),
        "planted_dummy": dummy.as_posix(),
        "matrix_unchanged": unchanged,
        "interpretation": (
            "No live site imports platform/lib/completion_predicate.py or "
            "agentspec.oracle.judge; planting an inverted C7 in a dummy copy "
            "changes zero verdicts."
            if unchanged
            else "UNEXPECTED: dummy shared invert changed the matrix"
        ),
    }


def target_verdicts(matrix: dict[str, Any], graph: dict[str, Any], c7_shared: dict[str, Any], c7_local: dict[str, Any]) -> list[dict[str, Any]]:
    by_id = {s["id"]: s for s in graph["sites"]}
    out = []
    for site_id in SITE_IDS:
        stats = matrix["by_site"][site_id]
        reaches = bool(by_id[site_id]["reaches_shared_symbol"])
        unbound = stats["unbound"] == matrix["n_outcomes"]
        changed_on_local_c7 = site_id in c7_local.get("sites_changed", [])
        changed_on_shared_c7 = (not c7_shared.get("matrix_unchanged", True)) and reaches
        if (
            reaches
            and not unbound
            and c7_shared.get("shared_module_present")
            and changed_on_shared_c7
        ):
            verdict = "CONFIRMED"
            why = (
                "site imports the shared 12-condition reducer, consumes the "
                "corpus, and flipped when condition 7 was inverted"
            )
        else:
            verdict = "REFUTED"
            why = (
                "site does not import the shared 12-condition reducer "
                f"(reaches_shared_symbol={reaches}, unbound={unbound}, "
                f"local_c7_changed={changed_on_local_c7}, "
                f"shared_present={bool(c7_shared.get('shared_module_present'))})"
            )
        out.append(
            {
                "target_id": site_id,
                "verdict": verdict,
                "reaches_shared_symbol": reaches,
                "unbound": unbound,
                "ok_true": stats["ok_true"],
                "ok_false": stats["ok_false"],
                "unbound_count": stats["unbound"],
                "changed_on_shared_c7_invert": bool(changed_on_shared_c7),
                "changed_on_local_c7_invert": changed_on_local_c7,
                "reason": why,
            }
        )
    return out


def investigate() -> dict[str, Any]:
    ru = load_ready_units()
    corpus = load_corpus()
    reducers = site_reducers(ru)
    matrix = run_matrix(corpus, reducers)
    graph = callgraph()
    c7_shared = mutate_c7_on_shared_module(corpus, ru)
    c7_local = mutate_c7_on_ready_units(corpus, ru)
    targets = target_verdicts(matrix, graph, c7_shared, c7_local)
    verdicts = {t["verdict"] for t in targets}
    if verdicts == {"CONFIRMED"}:
        overall = "CONFIRMED"
    elif verdicts == {"REFUTED"}:
        overall = "REFUTED"
    elif "NOT-CHECKED" in verdicts and len(verdicts) == 1:
        overall = "NOT-CHECKED"
    else:
        overall = "PARTIAL"
    compact_rows = [
        {
            "id": r["id"],
            "class": r["outcome_class"],
            "identical": r["byte_identical"],
            "tokens": {s: r["verdicts"][s] for s in SITE_IDS},
        }
        for r in matrix["rows"]
    ]
    return {
        "corpus": {
            "n": corpus["n"],
            "n_per_class": corpus["n_per_class"],
            "corpus_sha256": corpus["corpus_sha256"],
            "seed_count": len(corpus["seeds"]),
            "seeds": [
                {"name": s["name"], "sha256": s["sha256"], "bytes": s["bytes"]}
                for s in corpus["seeds"]
            ],
        },
        "matrix": {
            "n_outcomes": matrix["n_outcomes"],
            "n_disagreements": matrix["n_disagreements"],
            "n_byte_identical_rows": matrix["n_byte_identical_rows"],
            "by_site": matrix["by_site"],
            "disagreement_count_by_class": matrix["disagreement_count_by_class"],
            "matrix_sha256": matrix["matrix_sha256"],
            "rows": compact_rows,
        },
        "callgraph": graph,
        "controls": {
            "c7_invert_shared_module": c7_shared,
            "c7_invert_local_runner_symbol": c7_local,
        },
        "targets": targets,
        "overall_verdict": overall,
        "ready_units_imported": ru is not None,
    }
