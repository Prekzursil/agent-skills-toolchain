"""Schrodinger-side helper — runs INSIDE the Schrodinger interpreter
(`$SCHRODINGER/run python3 _sch_helper.py <cmd> <json-args>`), where both the
`schrodinger` package and a bundled `rdkit` are importable. Emits one JSON line.

The MCP server (server.py, in its own venv) invokes this via subprocess so it
never has to import `schrodinger` directly (which only works under `run`).
"""

import ast
import sys
import os
import json


def _info(_a):
    out = {"schrodinger_path": os.environ.get("SCHRODINGER", "")}
    try:
        import schrodinger

        out["schrodinger_build"] = getattr(schrodinger, "__version__", "n/a")
    except Exception as e:
        out["schrodinger_build"] = "ERR " + repr(e)
    try:
        import rdkit

        out["rdkit"] = rdkit.__version__
    except Exception as e:
        out["rdkit"] = "ERR " + repr(e)
    return out


def _smiles_to_3d(a):
    """SMILES -> 3D structure file (.sdf or .mae). 3D via RDKit ETKDGv3 + MMFF."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    smiles, out_path, title = a["smiles"], a["out_path"], a.get("title", "")
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return {"error": "invalid SMILES: " + smiles}
    m = Chem.AddHs(m)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    if AllChem.EmbedMolecule(m, params) != 0:
        return {"error": "3D embedding failed for " + smiles}
    try:
        AllChem.MMFFOptimizeMolecule(m)
    except Exception:
        pass
    if title:
        m.SetProp("_Name", title)
    ext = os.path.splitext(out_path)[1].lower()
    if ext in (".sdf", ".sd"):
        w = Chem.SDWriter(out_path)
        w.write(m)
        w.close()
    else:  # .mae / .maegz via schrodinger structure (keeps 3D coords from rdkit)
        from schrodinger.adapter import to_structure

        st = to_structure(m)
        if title:
            st.title = title
        st.write(out_path)
    return {
        "ok": True,
        "out_path": out_path,
        "atoms": m.GetNumAtoms(),
        "size_bytes": os.path.getsize(out_path),
    }


def _properties(a):
    """Drug-likeness descriptor panel for a SMILES (RDKit)."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Crippen, Lipinski, rdMolDescriptors

    m = Chem.MolFromSmiles(a["smiles"])
    if m is None:
        return {"error": "invalid SMILES: " + a["smiles"]}
    mw, logp = Descriptors.MolWt(m), Crippen.MolLogP(m)
    hbd, hba = Lipinski.NumHDonors(m), Lipinski.NumHAcceptors(m)
    return {
        "formula": rdMolDescriptors.CalcMolFormula(m),
        "mw": round(mw, 2),
        "logp": round(logp, 2),
        "hbd": hbd,
        "hba": hba,
        "tpsa": round(Descriptors.TPSA(m), 2),
        "rotatable_bonds": Descriptors.NumRotatableBonds(m),
        "rings": rdMolDescriptors.CalcNumRings(m),
        "qed": round(Descriptors.qed(m), 3),
        "lipinski_pass": bool(mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10),
    }


def _convert(a):
    """Convert any structure file to another format via schrodinger.structure."""
    from schrodinger import structure

    src, dst = a["src"], a["dst"]
    n = 0
    with structure.StructureWriter(dst) as w:
        for st in structure.StructureReader(src):
            w.append(st)
            n += 1
    return {"ok": True, "dst": dst, "structures": n, "size_bytes": os.path.getsize(dst)}


def _job_common(j, complete):
    """Shared completed-job fields. `succeeded()` RAISES unless complete, so gate it."""
    out = {
        "jobid": j.JobId,
        "status": j.Status,
        "is_complete": complete,
        "program": j.Program,
        "name": j.Name,
    }
    try:
        out["progress"] = j.getProgressAsString()
    except Exception:
        out["progress"] = None
    if complete:
        out["succeeded"] = j.succeeded()
        out["exit_status"] = j.ExitStatus
        out["dir"] = j.Dir
        try:
            out["struct_output"] = j.StructureOutputFile
        except Exception:
            out["struct_output"] = None
        try:
            out["output_files"] = list(j.OutputFiles or [])
        except Exception:
            out["output_files"] = []
    return out


def _job_status(a):
    """Read a Job Control job's live status by id (works cross-process via the job server)."""
    from schrodinger.job import jobcontrol as jc

    j = jc.Job(a["jobid"])
    j.readAgain()
    return _job_common(j, j.isComplete())


def _job_wait(a):
    """Poll a Job Control job until it completes or `timeout` (s) elapses."""
    import time
    from schrodinger.job import jobcontrol as jc

    timeout = float(a.get("timeout", 600))
    poll = max(1.0, float(a.get("poll", 5)))
    deadline = time.time() + timeout
    j = jc.Job(a["jobid"])
    j.readAgain()
    while not j.isComplete() and time.time() < deadline:
        time.sleep(poll)
        j = jc.Job(a["jobid"])
        j.readAgain()
    complete = j.isComplete()
    res = _job_common(j, complete)
    res["timed_out"] = not complete
    return res


def _launch(a):
    """Submit an arbitrary argv under Job Control (async) and return its jobid.
    For manager scripts (e.g. thermal_mmgbsa.py) that are not themselves
    jobcontrol launchers; jobcontrol-aware drivers self-submit without -WAIT."""
    from schrodinger.job import jobcontrol as jc

    job = jc.launch_job(a["argv"], launch_dir=a.get("launch_dir") or None)
    return {"jobid": job.JobId, "name": job.Name, "program": job.Program}


def _trj_analyze(a):
    """Compact numeric trajectory analysis from a Desmond -out.cms (auto-finds its _trj).
    Uses schrodinger.application.desmond.packages {analysis, traj_util, topo}. Computes
    protein-CA RMSD (fit on CA), protein-CA RMSF, radius of gyration, and (if lig_asl)
    ligand RMSD after protein fit. Returns per-frame series + summary stats."""
    import numpy as np
    from schrodinger.application.desmond.packages import analysis, traj_util

    cms_file = a["cms_file"]
    fit_asl = a.get("fit_asl", 'protein and atom.ptype " CA "')
    lig_asl = a.get("lig_asl") or ""
    stride = int(a.get("stride", 1))
    msys, cms, tr = traj_util.read_cms_and_traj(cms_file)
    if stride > 1:
        tr = tr[::stride]
    fit_aids = cms.select_atom(fit_asl)
    if not fit_aids:
        return {"error": f"fit_asl matched 0 atoms: {fit_asl!r}"}
    fit_ref = cms.extract(fit_aids).getXYZ()
    analyzers, keys = [], []
    analyzers.append(
        analysis.RMSD(
            msys, cms, fit_aids, fit_ref, fit_aids=fit_aids, fit_ref_pos=fit_ref
        )
    )
    keys.append("protein_ca_rmsd")
    analyzers.append(analysis.RMSF(msys, cms, fit_aids, fit_aids, fit_ref))
    keys.append("protein_ca_rmsf")
    analyzers.append(analysis.Gyradius(msys, cms, asl=fit_asl))
    keys.append("radius_of_gyration")
    if lig_asl:
        lig_aids = cms.select_atom(f"({lig_asl}) and not atom.ele H")
        if lig_aids:
            lig_ref = cms.extract(lig_aids).getXYZ()
            analyzers.append(
                analysis.RMSD(
                    msys, cms, lig_aids, lig_ref, fit_aids=fit_aids, fit_ref_pos=fit_ref
                )
            )
            keys.append("ligand_rmsd")
    results = analysis.analyze(tr, *analyzers)
    if len(analyzers) == 1:
        results = [results]
    out = {
        "cms_file": cms_file,
        "n_frames": len(tr),
        "sim_time_ns": round(tr[-1].time / 1000.0, 4) if tr else None,
        "series": {},
        "summary": {},
    }
    for key, series in zip(keys, results):
        arr = np.asarray(series, dtype=float)
        if arr.ndim == 1 and key != "protein_ca_rmsf":  # per-frame series
            out["series"][key] = [round(float(x), 4) for x in arr.tolist()]
            out["summary"][key] = {
                "mean": round(float(arr.mean()), 4),
                "min": round(float(arr.min()), 4),
                "max": round(float(arr.max()), 4),
                "last": round(float(arr[-1]), 4),
            }
        else:  # RMSF = per-atom (mean over frames already)
            flat = arr.ravel()
            out["series"][key] = [round(float(x), 4) for x in flat.tolist()][:2000]
            out["summary"][key] = {
                "mean": round(float(flat.mean()), 4),
                "min": round(float(flat.min()), 4),
                "max": round(float(flat.max()), 4),
                "n": int(flat.size),
            }
    return out


# ============================================================================
# ==== APPENDED HELPER GROUP: g01_feploop ====
# ============================================================================

# CMDS: "fep_map_qc": _fep_map_qc, "fep_parse_results": _fep_parse_results
#
# GROUP g01_feploop helper fns (run INSIDE $SCHRODINGER/run python3 — `schrodinger` importable).
# scisol FEP Graph API — attribute names introspected against the live 2026-2 / scisol-v6.2 install.
# Resolve the Graph class version-robustly via _scisol_fep_graph_cls() (the proven fep_sar.parse_fep
# path): the real package is schrodinger.application.scisol.packages.fep (WITH .packages) and the
# Graph class lives in the `submaps` submodule on 2026-2 (scisol-v6.2) — `graph` on older installs —
# so a hard `from ...scisol.packages.fep import graph` raises ImportError on 2026-2.
#   GraphClass.deserialize(path) [staticmethod] -> Graph(networkx.Graph)
#   g.write(path) ; g.nodes_iter() -> Node ; g.edges_iter() -> Edge ; g.add_edge(node0, node1)
#   Node: .id .short_id .struc .pred_dg .exp_dg   (pred_dg/exp_dg -> desmond.measurement.Measurement)
#   Edge: .id .short_id .nodes(from,to) .bennett_ddg .ccc_ddg .complex_dg .solvent_dg .exp_ddg
#   Measurement: instance attrs .val and .unc (both may be NaN)  -> _val_unc guards NaN.
# Confirmed absent (defensively probed, degrade to None): Node.title (fall back to struc.title),
# Edge.ddg (use bennett_ddg), per-edge overlap / forward-reverse convergence (best-effort only —
# the ACTIVE reliability signals are bennett_ddg.unc and the node-dG cycle-closure residual).


# ---------- small scisol-graph probes (tolerate value/version drift) ----------


def _val_unc(x):
    """Best-effort (value, uncertainty) from a scisol Measurement (.val/.unc) / (val,unc) / float.
    NaN is treated as missing (Measurement.val/.unc can be NaN) so it never leaks into JSON or a
    threshold comparison (NaN compares False and would silently disable a reliability flag)."""
    import math

    if x is None:
        return None, None
    if hasattr(x, "val"):
        v = getattr(x, "val")
    elif hasattr(x, "value"):
        v = getattr(x, "value")
    elif isinstance(x, (tuple, list)) and x:
        v = x[0]
    else:
        v = x
    u = None
    for uk in ("unc", "std", "error", "err", "uncertainty", "std_err"):
        if hasattr(x, uk):
            u = getattr(x, uk)
            break
    if u is None and isinstance(x, (tuple, list)) and len(x) > 1:
        u = x[1]
    try:
        v = float(v)
        if math.isnan(v) or math.isinf(v):
            return None, None
    except (TypeError, ValueError):
        return None, None
    try:
        u = float(u) if u is not None else None
        if u is not None and (math.isnan(u) or math.isinf(u)):
            u = None
    except (TypeError, ValueError):
        u = None
    return v, u


def _first_attr(obj, names):
    """Return the first present, non-None attribute among `names` (each may be a property or a
    callable -> call it). Every access is guarded (a scisol property may raise on an incomplete job)."""
    for n in names:
        if hasattr(obj, n):
            try:
                v = getattr(obj, n)
                v = v() if callable(v) else v
            except Exception:
                continue
            if v is not None:
                return v
    return None


def _num(x):
    """Scalar float from an attribute that may itself be a Measurement/tuple/float (NaN -> None)."""
    return _val_unc(x)[0]


def _node_id(n):
    """Stable string id for a fep graph Node (confirmed: Node.id, Node.short_id)."""
    for a in ("id", "short_id", "name"):
        v = getattr(n, a, None)
        if v is not None:
            return str(v)
    return "node_" + str(id(n))


def _short_id(e):
    """Human edge id ('from->to') for a fep graph Edge (confirmed: Edge.short_id, Edge.id)."""
    sid = getattr(e, "short_id", None)
    if sid is None:
        sid = getattr(e, "id", None)
    if isinstance(sid, (tuple, list)):
        return "->".join(str(s) for s in sid)
    return str(sid) if sid is not None else None


def _edge_endpoints(e):
    """(from_id, to_id) for a scisol fep graph Edge. Confirmed API: Edge.nodes -> (from_node,
    to_node) tuple of Node; short_id/id (a node-id pair) is the defensive fallback."""
    nodes = getattr(e, "nodes", None)
    if isinstance(nodes, (tuple, list)) and len(nodes) == 2:
        return _node_id(nodes[0]), _node_id(nodes[1])
    sid = getattr(e, "short_id", None)
    if sid is None:
        sid = getattr(e, "id", None)
    if isinstance(sid, (tuple, list)) and len(sid) == 2:
        return str(sid[0]), str(sid[1])
    return None


def _add_fep_edge(g, na, nb):
    """Add a manual edge between two Node objects via the confirmed Graph.add_edge(node0, node1)
    API (it validates membership and raises ValueError if a node is not in the graph, and no-ops
    if the two are the same node). Returns (ok: bool, detail: str). NOTE: the added edge carries
    NO precomputed atom-mapping, so it is a topological placeholder — verify/complete it in Maestro
    before submitting to fep_plus."""
    try:
        g.add_edge(na, nb)  # confirmed signature: takes the two Node objects
        return True, "Graph.add_edge(node,node)"
    except Exception as ex:
        return False, "add_edge failed: %r" % (ex,)


def _scisol_fep_graph_cls():
    """Resolve the scisol FEP Graph class version-robustly (the proven fep_sar.parse_fep path).
    The real package is schrodinger.application.scisol.packages.fep (WITH .packages); the Graph
    class's MODULE varies by scisol version — `submaps` on 2026-2 (scisol-v6.2), `graph` on older
    installs — so a hard `from ...scisol.packages.fep import graph` raises ImportError on 2026-2.
    Import the fep package and scan its submodules (submaps, then graph, then the rest) for a class
    exposing .deserialize. Returns that Graph class; raises ImportError if none is found."""
    import importlib
    import pkgutil
    import schrodinger.application.scisol.packages.fep as fep

    names = ["submaps", "graph"]
    pkg_dir = os.path.dirname(fep.__file__)
    names += [n for _, n, _ in pkgutil.iter_modules([pkg_dir]) if n not in names]
    for name in names:
        try:
            m = importlib.import_module(
                "schrodinger.application.scisol.packages.fep." + name
            )
        except Exception:
            continue
        cls = getattr(m, "Graph", None)
        if cls is not None and hasattr(cls, "deserialize"):
            return cls
    raise ImportError(
        "no scisol FEP Graph class with deserialize() found in "
        "schrodinger.application.scisol.packages.fep"
    )


def _cycle_closure(edge_list, thresh):
    """Fundamental-cycle hysteresis from signed edge ddG. A spanning tree is grown; each non-tree
    edge closes one independent cycle whose closure residual (edge ddG minus the tree-path ddG sum)
    should be ~0 for a well-converged map. edge_list = [(from_id, to_id, ddg), ...]."""
    from collections import deque

    nodes = set()
    for f, t, _d in edge_list:
        nodes.add(f)
        nodes.add(t)
    parent = {n: n for n in nodes}

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r

    tree_adj = {n: [] for n in nodes}
    non_tree = []
    for f, t, d in edge_list:
        if d is None:
            continue
        if find(f) != find(t):
            parent[find(f)] = find(t)
            tree_adj[f].append((t, d))
            tree_adj[t].append((f, -d))
        else:
            non_tree.append((f, t, d))

    def tree_path_sum(f, t):
        seen = {f: 0.0}
        dq = deque([f])
        while dq:
            u = dq.popleft()
            if u == t:
                return seen[u]
            for v, d in tree_adj[u]:
                if v not in seen:
                    seen[v] = seen[u] + d
                    dq.append(v)
        return None

    cycles, worst = [], None
    for f, t, d in non_tree:
        ps = tree_path_sum(f, t)
        if ps is None:
            continue
        h = round(d - ps, 4)  # closure residual around this fundamental cycle (ideal 0)
        cycles.append({"closes": f"{f}->{t}", "hysteresis": h, "flag": abs(h) > thresh})
        worst = abs(h) if worst is None else max(worst, abs(h))
    return {
        "n_independent_cycles": len(non_tree),
        "cycles": cycles[:200],
        "max_abs_hysteresis": round(worst, 4) if worst is not None else None,
    }


# ---------- fep_map_build backend: inject manual edges + QC the authored graph ----------


def _fep_map_qc(a):
    """Load an authored .fmp, inject manual extra_edges, QC connectivity + independent cycles,
    flag orphan/disconnected nodes, warn on GPU budget, write out_fmp. Returns
    {fmp, n_nodes, n_edges, disconnected_nodes[], edges_added, ...}."""
    graph_cls = _scisol_fep_graph_cls()
    in_fmp = a["in_fmp"]
    out_fmp = a.get("out_fmp") or in_fmp
    extra = a.get("extra_edges") or []
    budget = int(a.get("gpu_edge_budget", 0) or 0)
    g = graph_cls.deserialize(in_fmp)

    id2node = {_node_id(n): n for n in g.nodes_iter()}
    existing = set()
    for e in g.edges_iter():
        ep = _edge_endpoints(e)
        if ep:
            existing.add(frozenset(ep))

    warnings, edges_added = [], []
    for pair in extra:
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            warnings.append("skip malformed extra_edge: " + repr(pair))
            continue
        a_id, b_id = str(pair[0]), str(pair[1])
        na, nb = id2node.get(a_id), id2node.get(b_id)
        if na is None or nb is None:
            warnings.append("skip extra_edge (unknown node id): %s->%s" % (a_id, b_id))
            continue
        if frozenset((a_id, b_id)) in existing:
            warnings.append("extra_edge already present: %s->%s" % (a_id, b_id))
            continue
        ok, detail = _add_fep_edge(g, na, nb)
        if ok:
            edges_added.append([a_id, b_id])
            existing.add(frozenset((a_id, b_id)))
        else:
            warnings.append(
                "could not add extra_edge %s->%s (%s)" % (a_id, b_id, detail)
            )
    if edges_added:
        warnings.append(
            "%d manual edge(s) added carry no precomputed atom-mapping — verify them "
            "in Maestro's FEP Mapper before submitting to fep_plus" % len(edges_added)
        )

    # QC over the (possibly mutated) graph — pure Python union-find, no scisol internals needed.
    ids = [_node_id(n) for n in g.nodes_iter()]
    parent = {i: i for i in ids}

    def find(x):
        parent.setdefault(x, x)
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r

    deg = {i: 0 for i in ids}
    n_edges = 0
    for e in g.edges_iter():
        ep = _edge_endpoints(e)
        if ep is None:
            continue
        f, t = ep
        parent.setdefault(f, f)
        parent.setdefault(t, t)
        deg[f] = deg.get(f, 0) + 1
        deg[t] = deg.get(t, 0) + 1
        if find(f) != find(t):
            parent[find(f)] = find(t)
        n_edges += 1
    n_nodes = len(ids)

    comps = {}
    for i in ids:
        comps.setdefault(find(i), []).append(i)
    n_comp = len(comps) if comps else 0
    disconnected = []
    if comps:
        mainset = set(max(comps.values(), key=len))
        disconnected = sorted(i for i in ids if i not in mainset or deg.get(i, 0) == 0)
    independent_cycles = max(0, n_edges - n_nodes + n_comp)  # cyclomatic number

    if budget and n_edges > budget:
        warnings.append(
            "edge count %d exceeds local GPU budget %d (each edge is ~GPU-hours of "
            "FEP; split the map or drop weak perturbations)" % (n_edges, budget)
        )
    if disconnected:
        warnings.append(
            "%d disconnected/orphan node(s) — FEP+ needs one connected graph: %s"
            % (len(disconnected), disconnected[:20])
        )
    if n_nodes and n_comp > 1:
        warnings.append(
            "graph has %d components; only the largest will give consistent dG" % n_comp
        )

    try:
        g.write(out_fmp)
    except Exception as e:
        return {
            "error": "graph.write(out_fmp) failed: " + repr(e),
            "n_nodes": n_nodes,
            "n_edges": n_edges,
            "edges_added": edges_added,
            "disconnected_nodes": disconnected,
            "warnings": warnings,
        }
    return {
        "fmp": out_fmp if os.path.exists(out_fmp) else None,
        "n_nodes": n_nodes,
        "n_edges": n_edges,
        "n_components": n_comp,
        "independent_cycles": independent_cycles,
        "disconnected_nodes": disconnected,
        "edges_added": edges_added,
        "node_degree": deg,
        "warnings": warnings,
    }


# ---------- fep_parse_results backend: read the -out.fmp into structured results ----------


def _fep_parse_results(a):
    """Deserialize a completed FEP map and extract per-edge ddG / per-node dG / cycle-closure /
    reliability. Result reads use the CONFIRMED scisol attribute names with defensive fallbacks;
    a node-dG-based cycle-closure residual is always computed as an independent reliability signal."""
    graph_cls = _scisol_fep_graph_cls()
    out_fmp = a["out_fmp"]
    hyst = float(a.get("hysteresis_kcal", 1.0))
    overlap_min = float(a.get("overlap_min", 0.10))
    unc_thresh = float(a.get("ddg_unc_kcal", 1.0))
    g = graph_cls.deserialize(out_fmp)

    node_dg, nodes_out = {}, []
    for n in g.nodes_iter():
        nid = _node_id(n)
        pv, pu = _val_unc(_first_attr(n, ("pred_dg", "predicted_dg", "ccc_dg")))
        ev, eu = _val_unc(_first_attr(n, ("exp_dg", "experimental_dg")))
        title = _first_attr(n, ("title",))
        if (
            title is None
        ):  # Node has no .title; the ligand name lives on its structure (ct)
            st = _first_attr(n, ("struc", "structure", "ct"))
            title = getattr(st, "title", None) if st is not None else None
        node_dg[nid] = pv
        nodes_out.append(
            {
                "id": nid,
                "title": title,
                "pred_dg": pv,
                "pred_dg_unc": pu,
                "exp_dg": ev,
                "exp_dg_unc": eu,
            }
        )

    edges_out, edge_list, recommend = [], [], []
    for e in g.edges_iter():
        ep = _edge_endpoints(e)
        f, t = ep if ep else (None, None)
        # Confirmed per-edge ddG: bennett_ddg (raw Bennett), fall back to ccc_ddg (cycle-closure-corrected).
        ddg, ddg_u = _val_unc(_first_attr(e, ("bennett_ddg", "ccc_ddg")))
        cccddg, cccddg_u = _val_unc(_first_attr(e, ("ccc_ddg",)))
        cpx, cpx_u = _val_unc(_first_attr(e, ("complex_dg", "cpx_dg")))
        sol, sol_u = _val_unc(_first_attr(e, ("solvent_dg", "sol_dg")))
        if ddg is None and cpx is not None and sol is not None:
            ddg = round(cpx - sol, 4)  # ddG_bind = dG_complex - dG_solvent
            if cpx_u is not None and sol_u is not None:
                ddg_u = round((cpx_u**2 + sol_u**2) ** 0.5, 4)
        # overlap / fwd-rev convergence are NOT graph Edge attrs in 2026-2 -> best-effort, usually None.
        overlap = _num(_first_attr(e, ("overlap", "phase_space_overlap")))
        fwd = _num(_first_attr(e, ("forward_ddg", "ddg_forward")))
        rev = _num(_first_attr(e, ("reverse_ddg", "ddg_reverse")))
        conv = (
            round(abs(fwd - rev), 4) if (fwd is not None and rev is not None) else None
        )
        resid = None
        if (
            f in node_dg
            and t in node_dg
            and node_dg.get(f) is not None
            and node_dg.get(t) is not None
            and ddg is not None
        ):
            resid = round((node_dg[t] - node_dg[f]) - ddg, 4)

        reasons = []
        if ddg_u is not None and ddg_u > unc_thresh:
            reasons.append("ddg_unc %.2f > %.2f" % (ddg_u, unc_thresh))
        if overlap is not None and overlap < overlap_min:
            reasons.append("overlap %.2f < %.2f" % (overlap, overlap_min))
        if conv is not None and conv > hyst:
            reasons.append("fwd/rev hysteresis %.2f > %.2f" % (conv, hyst))
        if resid is not None and abs(resid) > hyst:
            reasons.append("cycle-closure residual %.2f > %.2f" % (resid, hyst))

        row = {
            "from": f,
            "to": t,
            "short_id": _short_id(e),
            "ddg": ddg,
            "ddg_unc": ddg_u,
            "ccc_ddg": cccddg,
            "ccc_ddg_unc": cccddg_u,
            "complex_dg": cpx,
            "solvent_dg": sol,
            "overlap": overlap,
            "fwd_rev_hysteresis": conv,
            "cycle_closure_residual": resid,
            "reliable": not reasons,
        }
        edges_out.append(row)
        if f and t and ddg is not None:
            edge_list.append((f, t, ddg))
        if reasons:
            recommend.append(
                {"from": f, "to": t, "short_id": row["short_id"], "reasons": reasons}
            )

    cc = _cycle_closure(edge_list, hyst)
    return {
        "fmp": out_fmp,
        "n_nodes": len(nodes_out),
        "n_edges": len(edges_out),
        "nodes": nodes_out[:500],
        "edges": edges_out[:1000],
        "cycle_closure": cc,
        "recommend_extend": recommend,
        "thresholds": {
            "hysteresis_kcal": hyst,
            "overlap_min": overlap_min,
            "ddg_unc_kcal": unc_thresh,
        },
    }


# ============================================================================
# ==== APPENDED HELPER GROUP: g02_qmprep ====
# ============================================================================

# CMDS: register these five in the _sch_helper.py CMDS dict (see g02_qmprep.mods.md §2):
#   "qm_cluster_extract": _qm_cluster_extract, "jaguar_in": _jaguar_in,
#   "jaguar_energy": _jaguar_energy, "jaguar_pka_in": _jaguar_pka_in,
#   "epik_pka_parse": _epik_pka_parse
#
# GROUP g02_qmprep — _sch_helper.py functions (append + register in CMDS).
# All run INSIDE the Schrodinger interpreter (need schrodinger.structure /
# schrodinger.application.jaguar / schrodinger.infra.mm). Each returns one JSON-able dict;
# an unhandled exception is caught by _sch_helper.py's __main__ and returned as {"error": ...}.
# (os + json are already imported at the top of _sch_helper.py.)


# standard terminal X-H cap bond lengths (Angstrom), by the heavy atom being capped
_QM_XH = {"C": 1.09, "N": 1.01, "O": 0.96, "S": 1.34, "P": 1.42, "B": 1.19}
# nominal (neutral) valence used by the cluster valence self-check
_QM_VALENCE = {
    "H": 1,
    "C": 4,
    "N": 3,
    "O": 2,
    "S": 2,
    "P": 3,
    "F": 1,
    "Cl": 1,
    "Br": 1,
    "I": 1,
    "B": 3,
}


def _qm_cluster_extract(a):
    """Carve a capped QM cluster (ligand + whole pocket residues within radius) from a complex.
    Severs each boundary bond, H-caps it along the original bond vector, partitions into
    ligand/pocket/complex, writes three .xyz files and a JSON manifest with per-fragment charge,
    multiplicity, atom ranges, and a valence/formal-charge self-check."""
    from schrodinger import structure
    from schrodinger.structutils import analyze

    # Merge all CTs so a single-CT complex OR a receptor+ligand pose-viewer (2 CTs, the
    # pose_viewer_split "complex" feed) both resolve the ligand ASL against one structure.
    # Structure.extend(other) appends other's atoms in place (verified _structure.py:3598).
    sts = list(structure.StructureReader(a["complex_mae"]))
    if not sts:
        return {"error": "no structures in complex_mae"}
    st = sts[0].copy()
    for extra in sts[1:]:
        st.extend(extra)
    lig_asl = a["ligand_asl"]
    radius = float(a["radius"])
    out_dir = a["out_dir"]

    lig = analyze.evaluate_asl(st, lig_asl)
    if not lig:
        return {"error": f"ligand_asl matched 0 atoms: {lig_asl!r}"}
    pocket_asl = f"(fillres (within {radius} ({lig_asl}))) and not ({lig_asl})"
    pocket = analyze.evaluate_asl(st, pocket_asl)
    lig_set, pocket_set = set(lig), set(pocket)
    included = lig_set | pocket_set

    def _xyz_tuple(i):
        at = st.atom[i]
        return (at.element, round(at.x, 6), round(at.y, 6), round(at.z, 6))

    def _cap_pos(a_in, a_out):
        pi, po = (a_in.x, a_in.y, a_in.z), (a_out.x, a_out.y, a_out.z)
        d = sum((po[k] - pi[k]) ** 2 for k in range(3)) ** 0.5 or 1.0
        f = _QM_XH.get(a_in.element, 1.09) / d
        return tuple(round(pi[k] + (po[k] - pi[k]) * f, 6) for k in range(3))

    # single pass over bonds: build in-cluster bond-order map, detect boundary cuts, place caps
    border, cap_count = {}, {}
    lig_caps, pocket_caps, cut_bonds = [], [], 0
    for bond in st.bond:
        i1, i2 = bond.atom1.index, bond.atom2.index
        in1, in2 = i1 in included, i2 in included
        if in1 and in2:
            border[frozenset((i1, i2))] = int(bond.order)
            continue
        if not in1 and not in2:
            continue
        cut_bonds += 1
        a_in, a_out = (st.atom[i1], st.atom[i2]) if in1 else (st.atom[i2], st.atom[i1])
        cap = ("H",) + _cap_pos(a_in, a_out)
        (lig_caps if a_in.index in lig_set else pocket_caps).append(cap)
        cap_count[a_in.index] = cap_count.get(a_in.index, 0) + 1

    lig_atoms = [_xyz_tuple(i) for i in sorted(lig_set)] + lig_caps
    pocket_atoms = [_xyz_tuple(i) for i in sorted(pocket_set)] + pocket_caps
    complex_atoms = lig_atoms + pocket_atoms

    # formal charges (caps are neutral H) and electron-parity multiplicity guess
    def _charge(idxs):
        return int(sum(st.atom[i].formal_charge for i in idxs))

    def _mult(idxs, q, ncaps):
        electrons = (
            sum(st.atom[i].atomic_number for i in idxs) + ncaps
        )  # each cap H adds 1 e
        return 1 if (electrons - q) % 2 == 0 else 2

    lig_q, pocket_q = _charge(lig_set), _charge(pocket_set)
    complex_q = lig_q + pocket_q
    lig_mult = _mult(lig_set, lig_q, len(lig_caps))
    pocket_mult = _mult(pocket_set, pocket_q, len(pocket_caps))
    complex_mult = _mult(included, complex_q, len(lig_caps) + len(pocket_caps))

    # valence self-check: in-cluster bond-order sum (+ caps as single bonds) vs nominal valence
    anomalies = []
    for i in included:
        at = st.atom[i]
        nominal = _QM_VALENCE.get(at.element)
        if nominal is None:
            continue
        order_sum = cap_count.get(i, 0)
        for nb in at.bonded_atoms:
            if nb.index in included:
                order_sum += border.get(frozenset((i, nb.index)), 1)
        fc = int(at.formal_charge)
        if order_sum not in (
            nominal,
            nominal + fc,
        ):  # tolerate charged lone-pair states (N+, O-)
            anomalies.append(
                {
                    "atom": i,
                    "element": at.element,
                    "order_sum": order_sum,
                    "nominal": nominal,
                    "formal_charge": fc,
                }
            )
    valence_ok = (len(lig_caps) + len(pocket_caps) == cut_bonds) and not anomalies

    def _write_xyz(path, atoms, comment):
        lines = [str(len(atoms)), comment]
        for el, x, y, z in atoms:
            lines.append(f"{el:<2s} {x:15.6f} {y:15.6f} {z:15.6f}")
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")

    stem = os.path.splitext(os.path.basename(a["complex_mae"]))[0]
    lig_xyz = os.path.join(out_dir, stem + "_ligand.xyz")
    pocket_xyz = os.path.join(out_dir, stem + "_pocket.xyz")
    complex_xyz = os.path.join(out_dir, stem + "_complex.xyz")
    _write_xyz(lig_xyz, lig_atoms, f"ligand  q={lig_q} mult={lig_mult}")
    _write_xyz(
        pocket_xyz,
        pocket_atoms,
        f"pocket(capped)  q={pocket_q} mult={pocket_mult} caps={len(pocket_caps)}",
    )
    _write_xyz(
        complex_xyz, complex_atoms, f"complex  q={complex_q} mult={complex_mult}"
    )

    nL, nP = len(lig_atoms), len(pocket_atoms)
    manifest = {
        "complex_mae": a["complex_mae"],
        "ligand_asl": lig_asl,
        "radius": radius,
        "cap": a["cap"],
        "n_input_structures": len(sts),
        "n_atoms": {
            "ligand": nL,
            "pocket": nP,
            "complex": nL + nP,
            "caps_added": len(lig_caps) + len(pocket_caps),
        },
        "total_charge": {"ligand": lig_q, "pocket": pocket_q, "complex": complex_q},
        "net_charge_per_fragment": {
            "ligand": lig_q,
            "pocket": pocket_q,
            "complex": complex_q,
        },
        "multiplicity": {
            "ligand": lig_mult,
            "pocket": pocket_mult,
            "complex": complex_mult,
        },
        "fragment_atom_ranges": {"ligand": [1, nL], "pocket": [nL + 1, nL + nP]},
        "cut_bonds": cut_bonds,
        "valence_check": {
            "passed": bool(valence_ok),
            "caps_equal_cuts": len(lig_caps) + len(pocket_caps) == cut_bonds,
            "n_anomalies": len(anomalies),
            "anomalies": anomalies[:25],
        },
        "files": {
            "ligand_xyz": lig_xyz,
            "pocket_xyz": pocket_xyz,
            "complex_xyz": complex_xyz,
        },
    }
    manifest_path = os.path.join(out_dir, stem + "_qmcluster.json")
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    manifest["manifest"] = manifest_path
    manifest["ok"] = True
    return manifest


def _jaguar_in(a):
    """Build a Jaguar input (.in) from a structure + a dict of &gen keyword/value pairs, via
    schrodinger.application.jaguar.input.JaguarInput(structure=, genkeys=).saveAs() — the
    genkeys kwarg is applied through setValues() by the constructor (verified input.py:281-322)."""
    from schrodinger import structure
    from schrodinger.application.jaguar.input import JaguarInput

    st = next(iter(structure.StructureReader(a["structure_file"])))
    genkeys = {k: str(v) for k, v in (a.get("genkeys") or {}).items()}
    ji = JaguarInput(structure=st, genkeys=genkeys)
    ji.saveAs(a["out_in"])
    return {
        "ok": True,
        "in_file": a["out_in"],
        "atoms": st.atom_total,
        "genkeys": genkeys,
    }


def _jaguar_energy(a):
    """Parse the final energy (Hartrees) from a Jaguar .out via JaguarOutput. Returns the SCF
    energy plus gas/solution-phase energies and a `converged` flag (status == OK). Attribute
    names verified against the installed jaguar-v13.2 output.py/results.py."""
    from schrodinger.application.jaguar.output import JaguarOutput

    try:
        jo = JaguarOutput(a["out_file"])
    except Exception as e:
        return {
            "error": "JaguarOutput parse failed: " + repr(e),
            "out_file": a["out_file"],
        }
    out = {"ok": True, "out_file": a["out_file"]}
    for attr in ("energy", "gas_phase_energy", "solution_phase_energy"):
        try:
            v = getattr(jo, attr, None)
        except Exception:
            v = None
        out[attr] = float(v) if isinstance(v, (int, float)) else v
    try:  # status is an int 0/1/2 == UNKNOWN/OK/SPLAT; OK => ok
        status = getattr(jo, "status", None)
        out["converged"] = (
            (status == JaguarOutput.OK) if isinstance(status, int) else None
        )
    except Exception:
        out["converged"] = None
    try:  # solvation flag lives on jo.opts in this build
        sv = getattr(jo, "solvation", None)
        if sv is None:
            opts = getattr(jo, "opts", None)
            sv = getattr(opts, "solvation", None) if opts is not None else None
        out["solvation"] = bool(sv) if sv is not None else None
    except Exception:
        out["solvation"] = None
    return out


def _jaguar_pka_in(a):
    """Author a SINGLE Jaguar pKa input (.in) from a structure: write a bare .in, auto-detect
    ionizable sites via mm.mmjag_pka_find_sites(name, allow_zwit), then set the ipka* keyword set
    (ipka_prot_deprot=both + ipkasites). ipka_max_conf=1 keeps it a single -NOJOBID job (no
    conformer subjobs). Falls back to ipkasearch=all if site detection returns nothing. The ipka
    keywords + the find_sites signature are verified vs jaguar-v13.2 (pka_modules/driver.py,
    examples/wflow-pka_jaguar-0001.in)."""
    from schrodinger import structure
    from schrodinger.application.jaguar import input as jaginp
    import schrodinger.infra.mm as mm

    st = next(iter(structure.StructureReader(a["structure_file"])))
    out_in = a["out_in"]
    jaginp.JaguarInput(structure=st).saveAs(out_in)  # bare .in for the site scan
    sites = []
    for cand in (
        os.path.splitext(out_in)[0],
        out_in,
    ):  # driver passes a jobname; try both forms
        try:
            found = mm.mmjag_pka_find_sites(cand, False)  # allow_zwit=False
        except Exception:
            found = None
        if found:
            sites = [str(s) for s in found]
            break
    genkeys = {
        "ipka_prot_deprot": "both",
        "ipka_solv_opt": "1",
        "ipka_max_conf": "1",
        "ipka_csrch_acc": "0",
        "ipka_lower_cut": "0.0",
        "ipka_upper_cut": "14.0",
    }
    if sites:
        genkeys["ipkasites"] = ",".join(sites)
    else:
        genkeys["ipkasearch"] = "all"
    jaginp.JaguarInput(structure=st, genkeys=genkeys).saveAs(out_in)
    return {
        "ok": True,
        "in_file": out_in,
        "sites": sites,
        "n_sites": len(sites),
        "site_mode": "ipkasites" if sites else "ipkasearch",
    }


def _epik_pka_parse(a):
    """Read Epik (EpikX/query) output structure(s) and collect every r_epik*pKa* property, both
    structure-level (acidic/basic macro-pKa) and per-atom (site pKa) - name-agnostic so it works
    for either the EpikX or legacy property set (props verified vs epikx/constants.py)."""
    from schrodinger import structure

    def _pka_props(bag):
        try:
            keys = list(bag.keys())
        except Exception:
            return {}
        return {k: bag[k] for k in keys if "epik" in k.lower() and "pka" in k.lower()}

    out = {"ok": True, "output": a["output"], "structures": []}
    for st in structure.StructureReader(a["output"]):
        rec = {
            "title": st.title,
            "total_charge": int(st.formal_charge),
            "structure_pka": _pka_props(st.property),
            "site_pka": [],
        }
        for at in st.atom:
            ap = _pka_props(at.property)
            if ap:
                rec["site_pka"].append({"atom": at.index, "element": at.element, **ap})
        out["structures"].append(rec)
        if len(out["structures"]) >= 50:
            break
    if out["structures"]:  # convenience: surface acidic/basic macro pKa
        for k, v in out["structures"][0]["structure_pka"].items():
            kl = k.lower()
            if "acid" in kl:
                out["most_acidic_pka"] = v
            elif "bas" in kl:
                out["most_basic_pka"] = v
    return out


# ============================================================================
# ==== APPENDED HELPER GROUP: g03_parse ====
# ============================================================================

# _sch_helper.py additions for group g03_parse (Parse + doctor).
# CMDS: "proplist": _proplist
#
# _proplist backs the server-side structure_properties_extract tool. It runs INSIDE the
# Schrodinger interpreter (like the existing _convert) so it can import schrodinger.structure
# and read the per-structure m2io property block directly (no text-parsing of a CLI).


def _proplist(a):
    """Tabulate per-structure m2io properties from a structure file via schrodinger.structure.
    No `properties` -> discovery mode: list every available property key (+ dtypes + a sample row).
    Else subset columns by case-insensitive substring, with optional numeric-aware sort_by /
    descending / limit. This is the structure-file counterpart of qikprop_parse_results (CSV)."""
    from schrodinger import structure

    src = a["src"]
    props = a.get("properties") or []
    sort_by = a.get("sort_by") or ""
    descending = bool(a.get("descending", False))
    limit = max(1, int(a.get("limit", 200)))
    read_cap = 100000  # guard a pathologically large library from exhausting memory
    rows, keytypes, truncated = [], {}, False
    for st in structure.StructureReader(src):
        d = {}
        try:
            d.update(dict(st.property))  # block-level props: r_/i_/s_/b_ ...
        except Exception:
            pass
        d.setdefault("s_m_title", st.title or "")  # always carry an identifier
        rows.append(d)
        for k, v in d.items():
            keytypes.setdefault(k, type(v).__name__)
        if len(rows) >= read_cap:
            truncated = True
            break
    n = len(rows)
    if n == 0:
        return {"src": src, "n_structures": 0, "property_keys": [], "structures": []}
    all_keys = sorted(keytypes)
    if not props:  # discovery / no-arg mode: list all keys so the caller can pick
        return {
            "src": src,
            "mode": "keys",
            "n_structures": n,
            "truncated": truncated,
            "property_keys": all_keys,
            "property_types": keytypes,
            "sample": {k: rows[0].get(k) for k in all_keys},
        }
    # subset: always keep title/name identifier columns + any key matching a substring
    id_keys = [
        k
        for k in all_keys
        if k.lower() in ("s_m_title", "s_m_entry_name", "s_m_entry_id")
        or "title" in k.lower()
        or "name" in k.lower()
    ]
    keep, seen = [], set()
    for k in all_keys:
        if k in seen:
            continue
        if k in id_keys or any(p.lower() in k.lower() for p in props):
            keep.append(k)
            seen.add(k)
    table = [
        dict({"_index": i + 1}, **{k: r.get(k) for k in keep})
        for i, r in enumerate(rows)
    ]
    if sort_by:  # resolve sort_by to an actual kept key (exact, else substring)
        skey = next((k for k in keep if k.lower() == sort_by.lower()), None)
        if skey is None:
            skey = next((k for k in keep if sort_by.lower() in k.lower()), None)
        if skey is not None:

            def _key(row):
                v = row.get(skey)
                try:
                    return (
                        0,
                        float(v),
                    )  # numeric-aware ordering (scores are r_ floats)
                except (TypeError, ValueError):
                    return (1, str(v) if v is not None else "")

            table.sort(key=_key, reverse=descending)
    return {
        "src": src,
        "mode": "table",
        "n_structures": n,
        "truncated": truncated,
        "columns": ["_index"] + keep,
        "sorted_by": sort_by or None,
        "structures": table[:limit],
    }


# ============================================================================
# ==== APPENDED HELPER GROUP: g04_poseqc ====
# ============================================================================

# _sch_helper.py additions for group g04_poseqc (Pose QC).
# Two LIBRARY commands (run inside the Schrodinger interpreter: schrodinger + rdkit + numpy).
# All schrodinger/rdkit imports are lazy (inside the functions) to match the existing style
# (_smiles_to_3d imports rdkit inside). Every check is guarded so one bad pose / one failing
# check never aborts the batch; the parent (_helper) parses the single trailing JSON line, and
# schrodinger DeprecationWarnings / rdkit logs go to stderr so they cannot corrupt stdout.
#
# CMDS: "pose_validity": _pose_validity
# CMDS: "pose_ifp": _pose_ifp


def _reslabel(atom):
    """Human residue label for a _StructureAtom, e.g. 'A:ARG161' (chain:pdbres+resnum+inscode)."""
    ch = (atom.chain or "").strip() or "_"
    res = (atom.pdbres or "").strip() or "UNK"
    ins = (atom.inscode or "").strip()
    return f"{ch}:{res}{atom.resnum}{ins}"


def _rank(vals):
    """Ascending competition rank (0 = smallest/most-negative = best) for a list of numbers."""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    rank = [0] * len(vals)
    for pos, i in enumerate(order):
        rank[i] = pos
    return rank


def _max_ring_oop(mol):
    """Max out-of-plane deviation (A) of any AROMATIC ring from its best-fit plane (RDKit + SVD).
    Returns None if there is no aromatic ring / no 3D conformer."""
    import numpy as np

    if mol is None or mol.GetNumConformers() == 0:
        return None
    ri = mol.GetRingInfo()
    conf = mol.GetConformer()
    worst, found = 0.0, False
    for ring in ri.AtomRings():
        if not all(mol.GetAtomWithIdx(idx).GetIsAromatic() for idx in ring):
            continue
        found = True
        pts = np.array(
            [
                [
                    conf.GetAtomPosition(i).x,
                    conf.GetAtomPosition(i).y,
                    conf.GetAtomPosition(i).z,
                ]
                for i in ring
            ]
        )
        cen = pts.mean(axis=0)
        # plane normal = last right-singular vector of the centered coords
        _, _, vt = np.linalg.svd(pts - cen)
        normal = vt[2]
        dev = float(np.abs((pts - cen) @ normal).max())
        worst = max(worst, dev)
    return worst if found else None


def _mmff_strain(mol):
    """MMFF94s strain energy of a docked pose: (E_pose, E_pose - E_relaxed) in kcal/mol.
    Relaxes an in-place copy and returns the drop. Returns (None, None) if MMFF is unavailable
    (missing atom types) or the mol lacks a 3D conformer."""
    import math
    from rdkit import Chem
    from rdkit.Chem import AllChem

    if mol is None or mol.GetNumConformers() == 0:
        return None, None
    try:
        m = Chem.Mol(mol)
        m = Chem.AddHs(
            m, addCoords=True
        )  # no-op if H already explicit; keeps 3D geometry
        props = AllChem.MMFFGetMoleculeProperties(m, mmffVariant="MMFF94s")
        if props is None:
            return None, None
        ff = AllChem.MMFFGetMoleculeForceField(m, props)
        if ff is None:
            return None, None
        e_pose = float(ff.CalcEnergy())
        ff.Minimize(maxIts=2000)
        e_min = float(ff.CalcEnergy())
        # A badly-clashing pose (exactly what this QC flags) can drive MMFF to a
        # non-finite energy; NaN/inf are invalid JSON, so return None instead ->
        # the field serializes as null and never corrupts the tool result.
        if not (math.isfinite(e_pose) and math.isfinite(e_min)):
            return None, None
        return e_pose, e_pose - e_min
    except Exception:
        return None, None


def _pose_validity(a):
    """PoseBusters-style per-pose validity + strain QC over a Glide pose-viewer / Prime -out.maegz.

    a = {"pose_viewer": <path>, "ref_input": <path|''>, "strain_threshold": float,
         "clash_cutoff": float}  (clash_cutoff = vdw-ratio cutoff for a steric clash, ~0.75)

    Convention: structure[0] = receptor, structure[1:] = ligand poses. Per pose we run RDKit
    sanitize + InChI round-trip, bond-length sanity, aromatic-ring planarity, internal + ligand-
    protein steric clash (+ overlap volume), stereo/connectivity vs an optional reference ligand,
    and MMFF strain. When both r_i_glide_gscore and r_psp_MMGBSA_dG_Bind are present, a
    Glide-vs-Prime rank-disagreement consensus_flag is set. Structutils-based checks (clashes,
    bond lengths) run even when RDKit sanitize fails, so a broken pose still gets diagnosed."""
    from schrodinger import structure, adapter
    from schrodinger.structutils import measure
    from schrodinger.structutils.interactions.steric_clash import (
        get_steric_clashes,
        sphere_overlap_volume,
    )
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")  # keep noise off (rdkit logs stderr, but be tidy)

    pv = a["pose_viewer"]
    ref_path = a.get("ref_input") or ""
    strain_threshold = float(a.get("strain_threshold", 20.0))
    clash_cutoff = float(a.get("clash_cutoff", 0.75))

    try:
        sts = list(structure.StructureReader(pv))
    except Exception as e:
        return {"error": f"could not read {pv}: {e!r}"}
    if not sts:
        return {"error": "no structures in " + pv}
    if len(sts) >= 2:
        receptor, poses, has_receptor = sts[0], sts[1:], True
    else:
        receptor, poses, has_receptor = None, sts, False

    # optional reference connectivity/stereo keys (from a prepared reference ligand file)
    ref_first, ref_full, ref_err = None, None, None
    if ref_path:
        try:
            ref_st = next(structure.StructureReader(ref_path))
            rk = Chem.MolToInchiKey(adapter.to_rdkit(ref_st))
            ref_first, ref_full = rk.split("-")[0], rk
        except Exception as e:
            ref_err = repr(e)[:200]

    # consensus prep: Glide gscore vs Prime MM-GBSA dG_bind ranks across the set
    gs, mm = [], []
    for st in poses:
        g = st.property.get("r_i_glide_gscore")
        if g is None:
            g = st.property.get("r_i_docking_score")
        gs.append(g)
        mm.append(st.property.get("r_psp_MMGBSA_dG_Bind"))
    consensus_available = (
        len(poses) >= 3
        and all(x is not None for x in gs)
        and all(x is not None for x in mm)
    )
    gs_rank = _rank(gs) if consensus_available else None
    mm_rank = _rank(mm) if consensus_available else None
    cons_thr = max(2, (len(poses) + 1) // 2)

    results = []
    for i, lig in enumerate(poses):
        try:
            failed, advisory, notes = [], [], {}

            # --- RDKit sanitize + InChI round-trip ---
            # adapter.to_rdkit is a builtin that takes NO keyword args; sanitize
            # explicitly so ring/aromaticity perception is valid for the downstream
            # planarity + MMFF checks (and so a broken pose is caught here).
            mol = None
            try:
                mol = adapter.to_rdkit(lig)
                if mol is None:
                    failed.append("sanitize")
                else:
                    Chem.SanitizeMol(mol)
            except Exception as e:
                mol = None
                failed.append("sanitize")
                notes["sanitize_error"] = repr(e)[:200]
            pose_first = pose_full = None
            if mol is not None:
                try:
                    inchi = Chem.MolToInchi(mol)
                    ok = bool(inchi) and (Chem.MolFromInchi(inchi) is not None)
                    if not ok:
                        failed.append("inchi_roundtrip")
                    key = Chem.MolToInchiKey(mol)
                    if key:
                        pose_first, pose_full = key.split("-")[0], key
                except Exception as e:
                    failed.append("inchi_roundtrip")
                    notes["inchi_error"] = repr(e)[:200]
            else:
                failed.append("inchi_roundtrip")

            # --- bond-length sanity (structutils; no RDKit needed) ---
            bad_bonds = 0
            try:
                for at in lig.atom:
                    for nb in at.bonded_atoms:
                        if nb.index > at.index:
                            d = measure.measure_distance(at, nb)
                            if d < 0.5 or d > 3.0:
                                bad_bonds += 1
            except Exception as e:
                notes["bond_error"] = repr(e)[:200]
            if bad_bonds:
                failed.append("bad_bond_lengths")

            # --- aromatic-ring planarity (RDKit) ---
            ring_oop = _max_ring_oop(mol)
            if ring_oop is not None and ring_oop > 0.25:
                failed.append("nonplanar_aromatic_ring")

            # --- internal steric clash (structutils; exclude 1-4 bonded) ---
            n_internal = None
            try:
                n_internal = len(
                    get_steric_clashes(lig, cutoff=clash_cutoff, include1_4=False)
                )
                if n_internal:
                    failed.append("internal_clash")
            except Exception as e:
                notes["internal_clash_error"] = repr(e)[:200]

            # --- ligand-protein clash + overlap volume (structutils) ---
            n_protein, overlap_vol = None, None
            if has_receptor:
                try:
                    pairs = get_steric_clashes(lig, st2=receptor, cutoff=clash_cutoff)
                    n_protein = len(pairs)
                    vol = 0.0
                    for al, ar in pairs:
                        d = measure.measure_distance(al, ar)
                        vol += sphere_overlap_volume(al.radius, ar.radius, d)
                    overlap_vol = round(vol, 2)
                    if n_protein:
                        failed.append("protein_clash")
                except Exception as e:
                    notes["protein_clash_error"] = repr(e)[:200]

            # --- stereo / connectivity vs reference ligand ---
            if ref_full and not ref_err:
                if pose_first is None:
                    advisory.append("stereo_check_unavailable")
                elif pose_first != ref_first:
                    failed.append("connectivity_changed")
                elif pose_full != ref_full:
                    failed.append("stereo_changed")

            # --- MMFF strain energy ---
            e_pose, strain = _mmff_strain(mol)
            high_strain = bool(strain is not None and strain > strain_threshold)
            if high_strain:
                advisory.append("high_strain")

            # --- Glide vs Prime consensus disagreement ---
            cflag = None
            if consensus_available:
                cflag = bool(abs(gs_rank[i] - mm_rank[i]) >= cons_thr)

            row = {
                "pose": i + 1,
                "title": (lig.title or "").strip() or None,
                "pass": not failed,
                "failed_checks": failed,
                "strain_kcal": (round(strain, 2) if strain is not None else None),
                "pose_energy_kcal": (round(e_pose, 2) if e_pose is not None else None),
                "consensus_flag": cflag,
                "internal_clashes": n_internal,
                "protein_clashes": n_protein,
                "clash_overlap_volume_A3": overlap_vol,
                "max_aromatic_ring_oop_A": (
                    round(ring_oop, 3) if ring_oop is not None else None
                ),
                "bad_bond_lengths": bad_bonds,
                "glide_gscore": (round(gs[i], 3) if gs[i] is not None else None),
                "mmgbsa_dg_bind": (round(mm[i], 3) if mm[i] is not None else None),
                "advisory_flags": advisory,
                "inchikey_first_block": pose_first,
            }
            if notes:
                row["diagnostics"] = notes
            results.append(row)
        except Exception as e:  # never let one pose kill the batch
            results.append(
                {
                    "pose": i + 1,
                    "pass": False,
                    "failed_checks": ["exception"],
                    "strain_kcal": None,
                    "consensus_flag": None,
                    "error": repr(e)[:300],
                }
            )

    out = {
        "pose_viewer": pv,
        "n_poses": len(poses),
        "has_receptor": has_receptor,
        "ref_input": ref_path or None,
        "strain_threshold_kcal": strain_threshold,
        "clash_ratio_cutoff": clash_cutoff,
        "consensus_available": consensus_available,
        "n_pass": sum(1 for r in results if r.get("pass")),
        "poses": results,
    }
    if ref_err:
        out["ref_input_error"] = ref_err
    return out


def _pose_ifp(a):
    """Per-residue protein-ligand interaction fingerprint for docked poses.

    a = {"pose_maegz": <path>, "recept_asl": <ASL, default 'protein'>}

    Convention: structure[0] = receptor, structure[1:] = ligand poses. Each pose is merged with
    the receptor into one complex so interactions map cleanly onto receptor atom indices
    (<= n_receptor). Via schrodinger.structutils.interactions we collect, per receptor residue:
    H-bonds (receptor donor/acceptor role + distance/angle), salt bridges, pi-pi (face/edge),
    pi-cation, and hydrophobic C-C contacts. The phenibut zwitterion NH3+/COO- salt bridge to
    the GABA-B orthosteric site is the load-bearing contact this surfaces."""
    from schrodinger import structure
    from schrodinger.structutils import analyze, measure
    from schrodinger.structutils import interactions
    from schrodinger.structutils.interactions import hbond
    from schrodinger.structutils.interactions.salt_bridge import OrderBy

    pv = a["pose_maegz"]
    recept_asl = a.get("recept_asl") or "protein"
    try:
        sts = list(structure.StructureReader(pv))
    except Exception as e:
        return {"error": f"could not read {pv}: {e!r}"}
    if len(sts) < 2:
        return {
            "error": "pose file must contain a receptor (first CT) followed by >=1 ligand pose"
        }
    receptor = sts[0]
    poses = sts[1:]

    def _hbond_angle(cx, measure_mod, a1, a2):
        """D-H..A angle (deg) for an H-bonded pair; finds the bridging H robustly. None if absent."""
        # case: both heavy -> locate the donor's H that bridges to the other heavy atom
        for heavy, other in ((a1, a2), (a2, a1)):
            if heavy.atomic_number == 1:
                continue
            for nb in heavy.bonded_atoms:
                if nb.atomic_number == 1:
                    try:
                        if measure_mod.measure_distance(nb, other) <= 2.6:
                            return measure_mod.measure_bond_angle(heavy, nb, other)
                    except Exception:
                        pass
        # case: one member of the pair IS the hydrogen
        for h, other in ((a1, a2), (a2, a1)):
            if h.atomic_number == 1:
                heavies = [nb for nb in h.bonded_atoms if nb.atomic_number != 1]
                if heavies:
                    try:
                        return measure_mod.measure_bond_angle(heavies[0], h, other)
                    except Exception:
                        return None
        return None

    results = []
    for i, lig in enumerate(poses):
        try:
            cx = receptor.merge(lig)
            n_rec = receptor.atom_total
            lig_atoms = list(range(n_rec + 1, cx.atom_total + 1))
            try:
                sel = analyze.evaluate_asl(cx, recept_asl)
            except Exception:
                sel = list(range(1, n_rec + 1))
            rec_atoms = [x for x in sel if x <= n_rec] or list(range(1, n_rec + 1))

            per_res = {}
            diagnostics = {}

            def _blank(lab):
                return {
                    "residue": lab,
                    "hbonds": [],
                    "salt_bridges": [],
                    "pi_pi": [],
                    "pi_cation": [],
                    "hydrophobic": [],
                }

            def _bump(lab, kind, info):
                per_res.setdefault(lab, _blank(lab))[kind].append(info)

            # --- hydrogen bonds (ligand <-> receptor) ---
            try:
                for donor, acc in hbond.get_hydrogen_bonds(
                    cx, atoms1=lig_atoms, atoms2=rec_atoms
                ):
                    rec_at = donor if donor.index <= n_rec else acc
                    role = "donor" if rec_at is donor else "acceptor"
                    dist = measure.measure_distance(donor, acc)
                    ang = _hbond_angle(cx, measure, donor, acc)
                    _bump(
                        _reslabel(rec_at),
                        "hbonds",
                        {
                            "receptor_role": role,
                            "receptor_atom": (rec_at.pdbname or "").strip()
                            or rec_at.element,
                            "distance": round(dist, 2),
                            "angle": (round(ang, 1) if ang is not None else None),
                        },
                    )
            except Exception as e:
                diagnostics["hbond_error"] = repr(e)[:200]

            # --- salt bridges (InputOrder -> (ligand_atom, receptor_atom)) ---
            try:
                for al, ar in interactions.get_salt_bridges(
                    cx, group1=lig_atoms, group2=rec_atoms, order_by=OrderBy.InputOrder
                ):
                    _bump(
                        _reslabel(ar),
                        "salt_bridges",
                        {
                            "receptor_atom": (ar.pdbname or "").strip() or ar.element,
                            "ligand_atom": (al.pdbname or "").strip() or al.element,
                            "distance": round(measure.measure_distance(al, ar), 2),
                        },
                    )
            except Exception as e:
                diagnostics["salt_bridge_error"] = repr(e)[:200]

            # --- pi-pi (ring1 = ligand, ring2 = receptor) ---
            try:
                for pp in interactions.find_pi_pi_interactions(
                    cx, atoms1=lig_atoms, atoms2=rec_atoms
                ):
                    rlab = _reslabel(cx.atom[pp.ring2.atoms[0]])
                    _bump(
                        rlab,
                        "pi_pi",
                        {
                            "type": (
                                "face-to-face" if pp.face_to_face else "edge-to-face"
                            ),
                            "distance": round(pp.distance, 2),
                            "angle": round(pp.angle, 1),
                        },
                    )
            except Exception as e:
                diagnostics["pi_pi_error"] = repr(e)[:200]

            # --- pi-cation (either side can carry the cation) ---
            try:
                for pc in interactions.find_pi_cation_interactions(
                    cx, atoms1=lig_atoms, atoms2=rec_atoms
                ):
                    cation_idx = pc.cation_centroid.atoms[0]
                    if (
                        cation_idx <= n_rec
                    ):  # receptor Arg/Lys/His cation -> ligand ring
                        lab, rrole = _reslabel(cx.atom[cation_idx]), "cation"
                    else:  # ligand cation (e.g. phenibut NH3+) -> receptor aromatic ring
                        lab, rrole = (
                            _reslabel(cx.atom[pc.pi_centroid.atoms[0]]),
                            "aromatic",
                        )
                    _bump(
                        lab,
                        "pi_cation",
                        {
                            "receptor_role": rrole,
                            "distance": round(pc.distance, 2),
                            "angle": round(pc.angle, 1),
                        },
                    )
            except Exception as e:
                diagnostics["pi_cation_error"] = repr(e)[:200]

            # --- hydrophobic C-C contacts (<= 4.5 A), min-distance + count per residue ---
            try:
                lig_c = [x for x in lig_atoms if cx.atom[x].atomic_number == 6]
                rec_c = [x for x in rec_atoms if cx.atom[x].atomic_number == 6]
                if lig_c and rec_c:
                    rec_c_set = set(rec_c)
                    dc = measure.DistanceCellIterator(cx, 4.5, rec_c)
                    hyd = {}
                    for li, neigh in dc.iterateNeighboringAtoms(cx, lig_c):
                        la = cx.atom[li]
                        for rj in neigh:
                            if rj in rec_c_set:
                                d = measure.measure_distance(la, cx.atom[rj])
                                if d <= 4.5:
                                    lab = _reslabel(cx.atom[rj])
                                    if lab not in hyd:
                                        hyd[lab] = [d, 1]
                                    else:
                                        hyd[lab][1] += 1
                                        if d < hyd[lab][0]:
                                            hyd[lab][0] = d
                    for lab, (mind, cnt) in hyd.items():
                        _bump(
                            lab,
                            "hydrophobic",
                            {"min_distance": round(mind, 2), "contacts": cnt},
                        )
            except Exception as e:
                diagnostics["hydrophobic_error"] = repr(e)[:200]

            residues = sorted(per_res.values(), key=lambda d: d["residue"])
            n_hbonds = sum(len(d["hbonds"]) for d in residues)
            n_salt = sum(len(d["salt_bridges"]) for d in residues)
            row = {
                "pose": i + 1,
                "title": (lig.title or "").strip() or None,
                "n_contact_residues": len(residues),
                "n_hbonds": n_hbonds,
                "n_salt_bridges": n_salt,
                "salt_bridge": bool(n_salt),
                "residues": residues,
            }
            if diagnostics:
                row["diagnostics"] = diagnostics
            results.append(row)
        except Exception as e:  # never let one pose kill the batch
            results.append({"pose": i + 1, "error": repr(e)[:300]})

    return {
        "pose_maegz": pv,
        "recept_asl": recept_asl,
        "n_poses": len(poses),
        "poses": results,
    }


# ============================================================================
# ==== APPENDED HELPER GROUP: g05_structglue ====
# ============================================================================

# CMDS: "pose_viewer_split": _pose_viewer_split, "reaction_enumerate": _reaction_enumerate, "mmod_confsearch": _mmod_confsearch
#
# GROUP g05_structglue — _sch_helper.py functions (append + register in CMDS).
# All three run INSIDE the Schrodinger interpreter (need schrodinger.structure /
# macromodel utils / bundled rdkit). Each returns one JSON-able dict.


def _pose_viewer_split(a):
    """Split a Glide pose-viewer (*_pv.maegz: structure[0]=receptor, [1:]=ligand poses) into
    per-pose files. mode=complex -> receptor+ligand as a single-pose pose-viewer (ligand written
    last, the downstream convention); ligand -> the pose only; receptor -> the shared receptor
    once. One file per pose (except mode=receptor)."""
    pv = a["pv_maegz"]
    out_dir = a["out_dir"]
    mode = a.get("mode", "complex")
    if mode not in ("complex", "ligand", "receptor"):
        return {"error": "mode must be complex|ligand|receptor"}
    from schrodinger import structure

    os.makedirs(out_dir, exist_ok=True)
    sts = list(structure.StructureReader(pv))
    if len(sts) < 2:
        return {
            "error": f"not a pose-viewer (need receptor + >=1 pose; got {len(sts)} structures)"
        }
    receptor, poses = sts[0], sts[1:]
    stem = os.path.splitext(os.path.basename(pv))[0]
    if stem.endswith("_pv"):
        stem = stem[:-3]
    if mode == "receptor":
        dest = os.path.join(out_dir, stem + "_receptor.maegz")
        receptor.write(dest)
        return {
            "ok": True,
            "mode": mode,
            "n_poses": len(poses),
            "n_files": 1,
            "files": [dest],
            "receptor_title": receptor.title,
        }
    files, entries = [], []
    for i, lig in enumerate(poses, start=1):
        if mode == "complex":
            dest = os.path.join(out_dir, f"{stem}_pose{i}_pv.maegz")
            with structure.StructureWriter(dest) as w:
                w.append(
                    receptor
                )  # receptor first, ligand last = single-pose pose-viewer
                w.append(lig)
        else:  # ligand
            dest = os.path.join(out_dir, f"{stem}_pose{i}_lig.maegz")
            lig.write(dest)
        files.append(dest)
        entries.append({"pose": i, "title": lig.title, "file": dest})
    return {
        "ok": True,
        "mode": mode,
        "receptor_title": receptor.title,
        "n_poses": len(poses),
        "n_files": len(files),
        "files": files,
        "poses": entries,
    }


def _parse_property_filter(property_filter):
    """Parse the documented numeric/boolean descriptor expression without executable code."""
    if len(property_filter) > 500:
        raise ValueError("invalid property_filter (max 500 chars)")
    try:
        filter_expr = ast.parse(property_filter, mode="eval")
    except (SyntaxError, ValueError) as exc:
        detail = getattr(exc, "msg", str(exc))
        raise ValueError(f"invalid property_filter syntax: {detail}") from exc

    allowed_nodes = (
        ast.Expression,
        ast.BoolOp,
        ast.BinOp,
        ast.UnaryOp,
        ast.Compare,
        ast.Name,
        ast.Constant,
        ast.Load,
        ast.And,
        ast.Or,
        ast.Not,
        ast.UAdd,
        ast.USub,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
    )
    filter_nodes = list(ast.walk(filter_expr))
    if len(filter_nodes) > 100:
        raise ValueError("invalid property_filter (max 100 syntax nodes)")
    descriptor_names = {"mw", "logp", "hbd", "hba", "tpsa", "rotb", "rings", "qed"}
    for node in filter_nodes:
        if not isinstance(node, allowed_nodes):
            raise ValueError(
                "unsupported property_filter syntax: " + type(node).__name__
            )
        if isinstance(node, ast.Name) and node.id not in descriptor_names:
            raise ValueError(f"unknown property_filter descriptor: {node.id}")
        if isinstance(node, ast.Constant) and type(node.value) not in (
            bool,
            int,
            float,
        ):
            raise ValueError("property_filter constants must be numeric or boolean")
    return filter_expr.body


def _eval_property_filter(node, values):
    """Evaluate a node already accepted by _parse_property_filter."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.BoolOp):
        result = _eval_property_filter(node.values[0], values)
        for value in node.values[1:]:
            if isinstance(node.op, ast.And):
                if not result:
                    return result
            elif result:
                return result
            result = _eval_property_filter(value, values)
        return result
    if isinstance(node, ast.UnaryOp):
        operand = _eval_property_filter(node.operand, values)
        if isinstance(node.op, ast.Not):
            return not bool(operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        return -operand
    if isinstance(node, ast.BinOp):
        left = _eval_property_filter(node.left, values)
        right = _eval_property_filter(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        return left % right
    if isinstance(node, ast.Compare):
        left = _eval_property_filter(node.left, values)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_property_filter(comparator, values)
            if isinstance(op, ast.Eq):
                passed = left == right
            elif isinstance(op, ast.NotEq):
                passed = left != right
            elif isinstance(op, ast.Lt):
                passed = left < right
            elif isinstance(op, ast.LtE):
                passed = left <= right
            elif isinstance(op, ast.Gt):
                passed = left > right
            else:
                passed = left >= right
            if not passed:
                return False
            left = right
        return True
    raise ValueError("unsupported property_filter syntax")


def _reaction_enumerate(a):
    """Combinatorial R-group / reaction enumeration from a reaction SMARTS + one reagent file per
    reactant slot, via bundled RDKit. Dedups by canonical SMILES, applies an optional descriptor
    filter, caps at max_products, writes products to .sdf (default) or .smi."""
    import gzip
    import itertools
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors, Crippen, Lipinski, rdMolDescriptors

    core_smarts = a["core_smarts"]
    reagent_files = a["reagent_files"]
    out_file = a["out_file"]
    max_products = int(a.get("max_products", 1000))
    property_filter = (a.get("property_filter") or "").strip()
    # Bound the combinatorial walk so an over-selective filter can't loop for hours.
    max_combos = max(200000, max_products * 500)

    def _read_reagents(path):
        low = path.lower()
        mols = []
        if low.endswith((".sdf.gz", ".sdfgz")):
            for m in Chem.ForwardSDMolSupplier(gzip.open(path)):
                if m is not None:
                    mols.append(m)
        elif low.endswith((".sdf", ".sd")):
            for m in Chem.SDMolSupplier(path):
                if m is not None:
                    mols.append(m)
        elif low.endswith((".mae", ".maegz", ".mae.gz")):
            from schrodinger import structure

            # Use the high-level bundled-RDKit adapter (all kwargs defaulted). The raw
            # schrodinger.adapter.to_rdkit REQUIRES a second options object, so calling it
            # bare raises TypeError; rdkit_adapter.to_rdkit builds those options internally.
            from schrodinger.rdkit.rdkit_adapter import to_rdkit

            for st in structure.StructureReader(path):
                try:
                    m = to_rdkit(
                        st, implicitH=True
                    )  # implicit H => matches SMILES-derived reagents
                except Exception:
                    m = None
                if m is not None:
                    if st.title:
                        m.SetProp("_Name", st.title)
                    mols.append(m)
        else:  # .smi / .smiles / .txt / .csv : "SMILES [title]" per line
            with open(path) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.replace(",", " ").split()
                    m = Chem.MolFromSmiles(parts[0])
                    if m is not None:
                        if len(parts) > 1:
                            m.SetProp("_Name", parts[1])
                        mols.append(m)
        return mols

    rxn = AllChem.ReactionFromSmarts(core_smarts)
    if rxn is None:
        return {"error": f"could not parse reaction SMARTS: {core_smarts!r}"}
    n_slots = rxn.GetNumReactantTemplates()
    if n_slots != len(reagent_files):
        return {
            "error": f"reaction has {n_slots} reactant slot(s) but "
            f"{len(reagent_files)} reagent file(s) given"
        }
    reagents = []
    for f in reagent_files:
        ms = _read_reagents(f)
        if not ms:
            return {"error": f"no valid reagents read from {f}"}
        reagents.append(ms)

    # Calls, attributes, indexing, comprehensions, and all other executable forms are rejected.
    filter_expr = None
    if property_filter:
        try:
            filter_expr = _parse_property_filter(property_filter)
        except ValueError as exc:
            return {"error": str(exc)}

    def _passes(mol):
        if filter_expr is None:
            return True
        ns = {
            "mw": Descriptors.MolWt(mol),
            "logp": Crippen.MolLogP(mol),
            "hbd": Lipinski.NumHDonors(mol),
            "hba": Lipinski.NumHAcceptors(mol),
            "tpsa": Descriptors.TPSA(mol),
            "rotb": Descriptors.NumRotatableBonds(mol),
            "rings": rdMolDescriptors.CalcNumRings(mol),
            "qed": Descriptors.qed(mol),
        }
        try:
            return bool(_eval_property_filter(filter_expr, ns))
        except (ArithmeticError, TypeError, ValueError):
            return False

    seen, products = set(), []
    combos_tried = 0
    done = False
    for combo in itertools.product(*reagents):
        combos_tried += 1
        if combos_tried > max_combos:
            break
        try:
            product_sets = rxn.RunReactants(combo)
        except Exception:
            continue
        for pset in product_sets:
            for prod in pset:
                try:
                    Chem.SanitizeMol(prod)
                except Exception:
                    continue
                smi = Chem.MolToSmiles(prod)
                if smi in seen or not _passes(prod):
                    continue
                seen.add(smi)
                names = [r.GetProp("_Name") for r in combo if r.HasProp("_Name")]
                prod.SetProp(
                    "_Name", "_".join(names) if names else f"prod{len(products) + 1}"
                )
                products.append(prod)
                if len(products) >= max_products:
                    done = True
                    break
            if done:
                break
        if done:
            break

    if not products:
        return {
            "error": "no products generated (check that the reaction SMARTS atom-mapping "
            "matches the reagents)",
            "combos_tried": combos_tried,
        }

    os.makedirs(os.path.dirname(out_file) or ".", exist_ok=True)
    low = out_file.lower()
    if low.endswith((".smi", ".smiles", ".txt")):
        with open(out_file, "w") as fh:
            for m in products:
                fh.write(f"{Chem.MolToSmiles(m)}\t{m.GetProp('_Name')}\n")
    else:  # .sdf (default)
        w = Chem.SDWriter(out_file)
        for m in products:
            try:
                AllChem.Compute2DCoords(m)
            except Exception:
                pass
            w.write(m)
        w.close()
    return {
        "ok": True,
        "out_file": out_file,
        "n_products": len(products),
        "n_reactant_slots": n_slots,
        "reagent_counts": [len(r) for r in reagents],
        "combos_tried": combos_tried,
        "capped": len(products) >= max_products,
        "combo_limit_hit": combos_tried > max_combos,
        "size_bytes": os.path.getsize(out_file) if os.path.exists(out_file) else 0,
    }


def _mmod_confsearch(a):
    """Stage the input as a local .mae and write a MacroModel MCMM .com via ComUtil.mcmm().
    Runs in the Schrodinger interpreter; server.py then runs `bmin -WAIT <job>`. The input/output
    filenames are written into the .com as basenames (relative), so bmin resolves them in `wd`
    (ComUtil.mcmm only serializes the names into the .com; it never opens the input itself)."""
    from schrodinger import structure
    from schrodinger.application.macromodel import utils as mmod_utils

    input_mae = a["input_mae"]
    out_mae = a["out_mae"]
    ffld = a.get("ffld", "OPLS4")
    solvent = a.get("solvent", "Water")
    job = a["job"]
    wd = a.get("wd") or (os.path.dirname(out_mae) or ".")
    os.makedirs(wd, exist_ok=True)
    # Stage the input structure locally as <job>_in.mae (any input fmt -> uncompressed .mae).
    in_base = job + "_in.mae"
    staged = os.path.join(wd, in_base)
    n = 0
    with structure.StructureWriter(staged) as w:
        for st in structure.StructureReader(input_mae):
            w.append(st)
            n += 1
    if not n:
        return {"error": f"no structures read from {input_mae}"}
    # Force field is resolved by the ComUtil ctor (OPLS4/OPLS3e/S-OPLS -> FFLD 16). GB/SA solvent
    # via the SOLV opcode: SOLV[1]=3 (GB/SA), SOLV[2] selects the solvent. The Water=1 / CHCl3=5 /
    # Octanol=9 codes are exactly those Schrodinger's own macromodel/input.py writes, verified
    # against the installed 2026-2 source.
    mcu = mmod_utils.ComUtil(ffld=ffld, wait=True, subs=False)
    sl = solvent.lower()
    if sl == "none":
        mcu.solv = False
    elif sl == "water":
        mcu.solv = True
        mcu.SOLV[2] = 1
    elif sl == "chcl3":
        mcu.solv = True
        mcu.SOLV[2] = 5
    elif sl == "octanol":
        mcu.solv = True
        mcu.SOLV[2] = 9
    else:
        return {
            "error": f"unsupported solvent {solvent!r}; use Water|None|CHCl3|Octanol"
        }
    if mcu.solv:
        mcu.exnb = True  # extended nonbonded list, recommended with a GB/SA continuum
    out_base = os.path.basename(out_mae)
    com_file = os.path.join(wd, job + ".com")
    written = mcu.mcmm(mae_file=in_base, com_file=com_file, out_file=out_base)
    return {
        "ok": True,
        "com_file": written,
        "jobname": job,
        "wd": wd,
        "staged_input": staged,
        "n_input": n,
        "expected_out": os.path.join(wd, out_base),
    }


# ============================================================================
# ==== APPENDED HELPER GROUP: g06_traj ====
# ============================================================================

# CMDS: "trj_interactions": _trj_interactions
#
# _sch_helper.py ADDITION for group g06_traj (Trajectory + membrane).
# Append _trj_interactions below and register the CMDS entry above.
# Extends the trajectory-analysis pattern of _trj_analyze (_sch_helper.py:151):
# same traj_util.read_cms_and_traj + analysis.analyze flow, no new top-level imports.
# API VERIFIED against the local Schrodinger 2026-2 install source
#   $SCHRODINGER/internal/lib/site-packages/schrodinger/application/desmond/packages/analysis.py:
#     class ProtLigInter(staf.CompositeAnalyzer)                                    (@3332)
#       __init__(self, msys_model, cms_model, prot_asl, lig_asl, metal_asl=None)    (@3349)
#       -> result is a PER-FRAME list of dicts (class docstring); one CompositeAnalyzer,
#          so analyze(tr, pli) returns that list directly (no per-analyzer wrapping).
#     def analyze(tr, analyzer, *arg, **kwarg)                                      (@3519)
#   result-key -> Result namedtuple (receptor-side aid field) — fields verified EXACT:
#     HBondResult       _Hbond(prot_aid, prot_type, lig_aid)
#     PolarResult       _PolarInter(prot_aid, polar_type, lig_aid, distance)     # salt bridge
#     WaterBridgeResult _WaterBridge(prot_aid, prot_type, lig_aid, lig_type, wat_res_num)
#     MetalResult       _MetalP(ion_aid, ion_ele, prot_aid, distance) | _MetalL(ion_aid, ion_ele, lig_aid, distance)
#     PiPiResult        _Pipi(ca_aid, frag_idx, ring_idx, distance, angle, type)
#     PiCatResult       _PiLCatP(prot_aid, frag_idx, ring_idx, distance, angle) | _PiPCatL(ca_aid, lig_aid, distance, angle)
#     HalogenBondResult _HalogenBond(prot_aid, lig_aid)
#     HydrophobicResult _Hydrophobic(ca_aid, frag_idx)


def _trj_interactions(a):
    """Protein-ligand interaction persistence over a Desmond -out.cms trajectory.
    Uses schrodinger.application.desmond.packages.analysis.ProtLigInter across every
    frame (same read_cms_and_traj pattern as _trj_analyze) and returns, keyed by
    RECEPTOR RESIDUE, the averaged PERSISTENCE (fraction of frames a contact is present)
    of H-bond / pi-pi / pi-cation / salt-bridge / metal / water-bridge (+ halogen /
    hydrophobic) contacts, plus compact per-frame contact counts. Needs a completed
    -out.cms (its sibling _trj is auto-found by read_cms_and_traj)."""
    from schrodinger.application.desmond.packages import analysis, traj_util

    cms_file = a["cms_file"]
    prot_asl = a.get("prot_asl") or "protein"
    lig_asl = a.get("lig_asl") or "not protein and not water and not ion"
    metal_asl = a.get("metal_asl") or None
    stride = max(1, int(a.get("stride", 1)))
    top = max(1, int(a.get("top", 200)))
    msys, cms, tr = traj_util.read_cms_and_traj(cms_file)
    if stride > 1:
        tr = tr[::stride]
    if not cms.select_atom(prot_asl):
        return {"error": f"prot_asl matched 0 atoms: {prot_asl!r}"}
    if not cms.select_atom(lig_asl):
        return {"error": f"lig_asl matched 0 atoms: {lig_asl!r}"}
    # ProtLigInter is ONE CompositeAnalyzer (no .reduce) -> analyze() returns a plain
    # list, one per-frame dict per element (schrodinger/.../analysis.py analyze() docstring).
    pli = analysis.ProtLigInter(msys, cms, prot_asl, lig_asl, metal_asl)
    frames = analysis.analyze(tr, pli)
    n = len(frames)
    if n == 0:
        return {"error": "trajectory has 0 frames", "cms_file": cms_file}

    # ProtLigInter result-key -> stable interaction-type label (verified vs 2026-2 source).
    TYPES = {
        "HBondResult": "hbond",
        "PiPiResult": "pi_pi",
        "PiCatResult": "pi_cation",
        "PolarResult": "salt_bridge",
        "MetalResult": "metal",
        "WaterBridgeResult": "water_bridge",
        "HalogenBondResult": "halogen_bond",
        "HydrophobicResult": "hydrophobic",
    }

    def _res_label(aid):
        # Receptor-residue key "chain:RESNAME_resnum" from the full-system cms atom
        # (same cms_model.atom[aid] indexing ProtLigInter uses internally).
        atom = cms.atom[aid]
        chain = (atom.chain or "").strip() or "_"
        resname = (atom.pdbres or "").strip() or "UNK"
        return f"{chain}:{resname}_{atom.resnum}"

    def _recv_aid(item):
        # Receptor-side atom AID for a Result namedtuple: prot_aid, else the alpha-carbon
        # ca_aid (pi-pi / protein-pi-cation / hydrophobic), else the metal ion_aid
        # (metal-to-ligand). Field-name introspection stays valid if fields are reordered.
        for fld in ("prot_aid", "ca_aid", "ion_aid"):
            if fld in getattr(item, "_fields", ()):
                return getattr(item, fld)
        return None

    counts = {t: [0] * n for t in TYPES.values()}
    counts["total"] = [0] * n
    present = {}  # (residue, type) -> number of frames the contact is present
    res_any = {}  # residue -> number of frames with any contact
    for fi, fr in enumerate(frames):
        seen_res = set()
        for key, items in (fr or {}).items():
            typ = TYPES.get(key)
            if not typ or not items:
                continue
            residues = (
                set()
            )  # dedupe multiple same-type contacts to one residue / frame
            for item in items:
                aid = _recv_aid(item)
                if aid is None:
                    continue
                try:
                    residues.add(_res_label(aid))
                except Exception:
                    continue
            for res in residues:
                present[(res, typ)] = present.get((res, typ), 0) + 1
                seen_res.add(res)
            counts[typ][fi] += len(residues)
            counts["total"][fi] += len(residues)
        for res in seen_res:
            res_any[res] = res_any.get(res, 0) + 1

    persistence = [
        {"residue": r, "type": t, "frames_present": c, "persistence": round(c / n, 4)}
        for (r, t), c in present.items()
    ]
    persistence.sort(
        key=lambda d: (d["persistence"], d["frames_present"]), reverse=True
    )
    by_residue = {}
    for (r, t), c in present.items():
        by_residue.setdefault(r, {})[t] = round(c / n, 4)
    for r, c in res_any.items():
        by_residue.setdefault(r, {})["any"] = round(c / n, 4)

    return {
        "cms_file": cms_file,
        "n_frames": n,
        "sim_time_ns": round(tr[-1].time / 1000.0, 4) if tr else None,
        "prot_asl": prot_asl,
        "lig_asl": lig_asl,
        "metal_asl": metal_asl,
        "per_frame_counts": counts,
        "persistence": persistence[:top],
        "by_residue": by_residue,
        "summary": {
            "n_frames": n,
            "n_contacts": len(persistence),
            "n_residues": len(by_residue),
            "top_contacts": persistence[:15],
        },
    }


# ============================================================================
# ==== APPENDED HELPER GROUP: g10_composites ====
# ============================================================================

# CMDS: "cns_mpo": _cns_mpo, "pv_scores": _pv_scores, "write_subset": _write_subset,
# CMDS: "enumerate_analogs": _enumerate_analogs, "cluster_frames": _cluster_frames
#
# _sch_helper.py additions for the g10 composite tools. Each runs INSIDE the Schrodinger
# interpreter (import schrodinger / rdkit available) and returns one JSON-able dict.


def _cns_mpo(a):
    """CNS-MPO surrogate (Wager 2010) + QED for a set of molecules. Accepts EITHER
    {"smiles_list":[...], optional "titles":[...]} or {"structure_file": path}. ClogP/TPSA/HBD/
    MW/HBA/QED from RDKit. 5-parameter MPO over {ClogP, ClogD, MW, HBD, TPSA} (the pKa term is
    dropped - RDKit has no pKa; supply per-title 'pkas' to refine ClogD via Henderson-Hasselbalch
    at pH 7.4, else ClogD is approximated as ClogP). Reports mpo (0-5), cns_mpo_max=5, and per-
    molecule 'pass' at cns_mpo/5 >= mpo_norm_min. No license token."""
    import math
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors

    def _dec(x, good, bad):  # 1.0 at x<=good, 0.0 at x>=bad, linear between (good<bad)
        if x <= good:
            return 1.0
        if x >= bad:
            return 0.0
        return (bad - x) / (bad - good)

    def _hump(
        x, a0, a1, b1, b0
    ):  # 0 below a0, rise to 1 at a1, plateau to b1, fall to 0 at b0
        if x <= a0 or x >= b0:
            return 0.0
        if x < a1:
            return (x - a0) / (a1 - a0)
        if x <= b1:
            return 1.0
        return (b0 - x) / (b0 - b1)

    def _logd(clogp, pka):
        if pka is None:
            return clogp, True
        try:  # most-basic centre -> cationic fraction at pH 7.4 lowers logD
            return clogp - math.log10(1.0 + 10 ** (float(pka) - 7.4)), False
        except Exception:
            return clogp, True

    mols = []  # (title, smiles, rdkit_mol)
    if a.get("structure_file"):
        from schrodinger import structure, adapter

        for i, st in enumerate(structure.StructureReader(a["structure_file"])):
            title = st.title or ("mol_%d" % (i + 1))
            rm = None
            try:  # schrodinger.adapter is the supported Structure<->RDKit bridge (2021+)
                rm = adapter.to_rdkit(st)
            except Exception:
                rm = None
            if (
                rm is None
            ):  # fall back via a canonical SMILES (structutils.smiles is retired in 2026-2)
                try:
                    rm = Chem.MolFromSmiles(adapter.to_smiles(st))
                except Exception:
                    rm = None
            smi = Chem.MolToSmiles(rm) if rm is not None else None
            mols.append((title, smi, rm))
    else:
        smiles_list = a.get("smiles_list") or []
        titles = a.get("titles") or []
        for i, smi in enumerate(smiles_list):
            title = titles[i] if i < len(titles) else ("mol_%d" % (i + 1))
            mols.append((title, smi, Chem.MolFromSmiles(smi)))

    pkas = a.get("pkas") or {}
    thr = float(a.get("mpo_norm_min", 0.7))
    approx_any = False
    out = []
    for title, smi, m in mols:
        if m is None:
            out.append(
                {"title": title, "smiles": smi, "error": "invalid/unreadable molecule"}
            )
            continue
        clogp = Crippen.MolLogP(m)
        mw = Descriptors.MolWt(m)
        tpsa = rdMolDescriptors.CalcTPSA(m)
        hbd = Lipinski.NumHDonors(m)
        hba = Lipinski.NumHAcceptors(m)
        qed = Descriptors.qed(m)
        clogd, approx = _logd(clogp, pkas.get(title))
        approx_any = approx_any or approx
        comp = {
            "clogp": round(_dec(clogp, 3.0, 5.0), 3),
            "clogd": round(_dec(clogd, 2.0, 4.0), 3),
            "mw": round(_dec(mw, 360.0, 500.0), 3),
            "hbd": round(_dec(hbd, 0.5, 3.5), 3),
            "tpsa": round(_hump(tpsa, 20.0, 40.0, 90.0, 120.0), 3),
        }
        mpo = sum(comp.values())
        out.append(
            {
                "title": title,
                "smiles": Chem.MolToSmiles(m) if smi is None else smi,
                "mw": round(mw, 2),
                "clogp": round(clogp, 2),
                "clogd": round(clogd, 2),
                "tpsa": round(tpsa, 2),
                "hbd": hbd,
                "hba": hba,
                "qed": round(qed, 3),
                "cns_mpo": round(mpo, 3),
                "cns_mpo_max": 5.0,
                "components": comp,
                "clogd_approximated": approx,
                "pass": bool((mpo / 5.0) >= thr),
            }
        )
    return {
        "n": len(out),
        "mpo_norm_min": thr,
        "note": "5-parameter CNS-MPO surrogate (pKa term omitted; RDKit has no pKa). "
        "ClogD approximated from ClogP unless per-title 'pkas' supplied."
        + (" Some ClogD values are approximated." if approx_any else ""),
        "molecules": out,
    }


def _pv_scores(a):
    """Best Glide score per ligand title from a pose file (a *_pv.maegz / poses maegz). Skips the
    receptor entry (no score property); keeps the minimum (best) r_i_glide_gscore per title."""
    from schrodinger import structure

    prop = a.get("score_prop", "r_i_glide_gscore")
    alt = "r_i_docking_score"
    best, n_poses = {}, 0
    for i, st in enumerate(structure.StructureReader(a["pose_file"])):
        sc = st.property.get(prop)
        if sc is None:
            sc = st.property.get(alt)
        if sc is None:  # receptor / unscored entry
            continue
        n_poses += 1
        title = st.title or ("pose_%d" % i)
        s = float(sc)
        if title not in best or s < best[title]:
            best[title] = s
    ranked = sorted(best.items(), key=lambda kv: kv[1])
    return {
        "n_titles": len(best),
        "n_poses": n_poses,
        "score_prop": prop,
        "scores": {t: round(s, 4) for t, s in best.items()},
        "ranked_titles": [t for t, _ in ranked],
    }


def _write_subset(a):
    """Write structures whose title is in `titles` from `src` to `dst` (format from dst suffix)."""
    import os
    from schrodinger import structure

    keep = set(a["titles"])
    n = 0
    with structure.StructureWriter(a["dst"]) as w:
        for st in structure.StructureReader(a["src"]):
            if (st.title or "") in keep:
                w.append(st)
                n += 1
    return {
        "dst": a["dst"],
        "n_written": n,
        "size_bytes": os.path.getsize(a["dst"]) if os.path.exists(a["dst"]) else 0,
    }


def _enumerate_analogs(a):
    """Combinatorial R-group enumeration (RDKit molzip). `core_smiles` carries attachment dummies
    [*:1],[*:2],...; `rgroups` maps the map-number (str) -> [substituent SMILES] (each attaches via
    its first atom; '[H]'/'' = keep hydrogen). Products = Cartesian across sites (deduped by
    canonical SMILES, capped by `max_products`) plus the all-H parent (title 'parent')."""
    import itertools
    from rdkit import Chem

    core_smi = a["core_smiles"]
    core = Chem.MolFromSmiles(core_smi)
    if core is None:
        return {"error": "invalid core_smiles: %r" % core_smi}
    maps = sorted(
        {
            at.GetAtomMapNum()
            for at in core.GetAtoms()
            if at.GetSymbol() == "*" and at.GetAtomMapNum() > 0
        }
    )
    if not maps:
        return {
            "error": "core_smiles has no attachment dummies [*:n] (e.g. 'c1ccccc1[*:1]')"
        }
    if not hasattr(Chem, "molzip"):
        return {
            "error": "bundled RDKit lacks Chem.molzip (need >=2020.09) for enumeration"
        }
    rgroups = a.get("rgroups") or {}
    cap = int(a.get("max_products", 5000))

    def _is_h(sub):
        return (sub or "").strip() in ("", "[H]", "H", "[*][H]")

    def _frag(sub, mn):
        s = (sub or "").strip()
        f = Chem.MolFromSmiles("[*:%d]%s" % (mn, s))
        if f is None:
            f = Chem.MolFromSmiles("[*:%d](%s)" % (mn, s))
        return f

    def _build(combo):
        merged = core
        for mn, sub in zip(maps, combo):
            if _is_h(sub):
                continue
            fr = _frag(sub, mn)
            if fr is None:
                return None
            merged = Chem.CombineMols(merged, fr)
        try:
            z = Chem.RWMol(Chem.molzip(merged))
            for at in list(z.GetAtoms()):  # leftover [*:n] (H choices) -> hydrogen
                if at.GetSymbol() == "*" and at.GetAtomMapNum() in maps:
                    at.SetAtomicNum(1)
                    at.SetAtomMapNum(0)
            m = z.GetMol()
            Chem.SanitizeMol(m)
            return Chem.MolToSmiles(Chem.RemoveHs(m))
        except Exception:
            return None

    site_subs = [(rgroups.get(str(mn)) or rgroups.get(mn) or ["[H]"]) for mn in maps]
    seen, products, idx, truncated = set(), [], 0, False
    for combo in itertools.product(*site_subs):
        if len(products) >= cap:
            truncated = True
            break
        smi = _build(list(combo))
        if not smi or smi in seen:
            continue
        seen.add(smi)
        is_parent = all(_is_h(s) for s in combo)
        idx += 1
        products.append(
            {
                "title": "parent" if is_parent else "an_%04d" % idx,
                "smiles": smi,
                "rgroups": {
                    str(mn): (s if not _is_h(s) else "[H]")
                    for mn, s in zip(maps, combo)
                },
                "is_parent": is_parent,
            }
        )
    if not any(p["is_parent"] for p in products):
        psmi = _build(["[H]"] * len(maps))
        if psmi and psmi not in seen:
            products.insert(
                0,
                {
                    "title": "parent",
                    "smiles": psmi,
                    "rgroups": {str(mn): "[H]" for mn in maps},
                    "is_parent": True,
                },
            )
    return {
        "n": len(products),
        "attachment_points": list(maps),
        "truncated": truncated,
        "molecules": products,
    }


def _cluster_frames(a):
    """Cluster a Desmond trajectory by protein Ca-RMSD and write N representative receptor
    snapshots (protein only) as .mae - one per cluster centre frame - each with a binding-site
    centroid (from `site_asl`, default the bound non-protein ligand) for grid centring. Greedy
    k-centre clustering on translation-centred Ca coords (numpy only). NOTE: uses the Desmond
    analysis packages (traj_util/topo) - needs a completed MD -out.cms + its _trj to run; the
    frame->CT update path is version-sensitive, so validate the first invocation."""
    import os
    import numpy as np
    from schrodinger.structutils.analyze import evaluate_asl
    from schrodinger.application.desmond.packages import traj_util, topo

    cms_file = a["cms_file"]
    n = max(1, int(a.get("n_snapshots", 5)))
    stride = max(1, int(a.get("stride", 1)))
    fit_asl = a.get("fit_asl", 'protein and atom.ptype " CA "')
    recep_asl = a.get("receptor_asl", "protein")
    site_asl = a.get("site_asl") or "not (protein or water or ions or metals)"
    out_dir = a.get("out_dir") or (os.path.dirname(cms_file) or ".")
    prefix = a.get("prefix", "ensemble_snap")
    os.makedirs(out_dir, exist_ok=True)

    msys, cms, tr = traj_util.read_cms_and_traj(cms_file)
    if stride > 1:
        tr = tr[::stride]
    frames = len(tr)
    if frames == 0:
        return {"error": "no frames in trajectory"}
    ca_aids = cms.select_atom(fit_asl)
    if not ca_aids:
        return {"error": "fit_asl matched 0 atoms: %r" % fit_asl}
    ca_gids = topo.aids2gids(cms, ca_aids, include_pseudoatoms=False)
    coords = np.array(
        [np.asarray(fr.pos())[ca_gids] for fr in tr], dtype=float
    )  # (F, A, 3)
    cen = coords - coords.mean(axis=1, keepdims=True)
    flat = cen.reshape(frames, -1)
    natoms = cen.shape[1]

    def _rmsd(i, j):
        d = flat[i] - flat[j]
        return float(np.sqrt(float((d * d).sum()) / natoms))

    nsel = min(n, frames)
    centers = [0]
    mind = np.array([_rmsd(0, j) for j in range(frames)])
    while len(centers) < nsel:
        nxt = int(mind.argmax())
        if nxt in centers:
            break
        centers.append(nxt)
        mind = np.minimum(mind, np.array([_rmsd(nxt, j) for j in range(frames)]))
    centers = sorted(set(centers))
    assign = np.array(
        [int(np.argmin([_rmsd(c, j) for c in centers])) for j in range(frames)]
    )

    snaps = []
    for k, ci in enumerate(centers):
        try:  # push frame coords into the full-system CT
            topo.update_ct(cms.fsys_ct, cms, tr[ci])
        except Exception:
            try:
                cms.setXYZ(np.asarray(tr[ci].pos()))
            except Exception as e:
                return {"error": "frame->CT update failed: %r" % e}
        full = cms.fsys_ct
        rec_idx = evaluate_asl(full, recep_asl)
        recep = full.extract(rec_idx) if rec_idx else full.copy()
        dst = os.path.join(out_dir, "%s_%d.mae" % (prefix, k + 1))
        recep.title = "%s_%d_frame%d" % (prefix, k + 1, ci)
        recep.write(dst)
        center = None
        site_idx = evaluate_asl(full, site_asl)
        if site_idx:
            xs = [full.atom[i].x for i in site_idx]
            ys = [full.atom[i].y for i in site_idx]
            zs = [full.atom[i].z for i in site_idx]
            center = [
                round(sum(xs) / len(xs), 4),
                round(sum(ys) / len(ys), 4),
                round(sum(zs) / len(zs), 4),
            ]
        snaps.append(
            {
                "snapshot_mae": dst if os.path.exists(dst) else None,
                "frame_index": int(ci),
                "cluster_size": int((assign == k).sum()),
                "grid_center": center,
            }
        )
    return {
        "n_snapshots": len(snaps),
        "n_frames": frames,
        "centers": [int(c) for c in centers],
        "snapshots": snaps,
    }


# ============================================================================
# ==== APPENDED HELPER GROUP: g11_monitor ====
# ============================================================================

# CMDS: "fep_edges": _fep_edges
#
# g11_monitor helper — one _sch_helper.py function. Append _fep_edges and add its CMDS entry.
# Used by server._derive_total to compute the FEP+ progress denominator (edge count) for the
# taskwatch progress.json heartbeat. The .fmp is protobuf binary, so the edge count is only
# obtainable through the scisol FEP Graph API (in-interpreter) — hence a helper, not a server fn.


def _fep_edges(a):
    """Count perturbation edges (and nodes) in a FEP map (.fmp) via the scisol FEP Graph API —
    the map denominator for FEP+ progress. The Graph class's MODULE varies by scisol version:
    2026-2 (scisol-v6.2) exposes it as `submaps`, NOT `graph` (a hard `import graph` raises
    ImportError there). So resolve the class by introspection — the proven fep_sar.parse_fep
    path — trying the known module names first, then scanning the fep package. Returns
    {edges, nodes, module, fmp}; on any failure {error, fmp} so the caller degrades to no %."""
    import importlib
    import pkgutil
    import schrodinger.application.scisol.packages.fep as fep

    graph_cls = None
    module = None
    # Fast-path the known module names (submaps = 2026-2, graph = older), then scan the rest.
    names = ["submaps", "graph"]
    pkg_dir = os.path.dirname(fep.__file__)
    names += [n for _, n, _ in pkgutil.iter_modules([pkg_dir]) if n not in names]
    for name in names:
        try:
            m = importlib.import_module(
                "schrodinger.application.scisol.packages.fep." + name
            )
        except Exception:
            continue
        cls = getattr(m, "Graph", None)
        if cls is not None and hasattr(cls, "deserialize"):
            graph_cls, module = cls, name
            break
    if graph_cls is None:
        return {
            "error": "no scisol FEP Graph class with deserialize() found",
            "fmp": a["fmp"],
        }
    g = graph_cls.deserialize(a["fmp"])
    edges = sum(1 for _ in g.edges_iter())
    try:
        nodes = sum(1 for _ in g.nodes_iter())
    except Exception:
        nodes = None
    return {"edges": edges, "nodes": nodes, "module": module, "fmp": a["fmp"]}


# ============================================================================
# ==== APPENDED HELPER GROUP: g12_filters ====
# ============================================================================

# CMDS: "count_structures": _count_structures
#
# GROUP g12_filters helper additions for _sch_helper.py.
# Add `_count_structures` alongside the existing helper fns and register it in the CMDS dict:
#     CMDS = {..., "count_structures": _count_structures}
# (imports `sys, os, json` are already at the top of _sch_helper.py; StructureReader is imported
# lazily inside the fn, matching the existing _convert / _smiles_to_3d pattern.)


def _count_structures(a):
    """Count structures in one or more files via schrodinger.structure.StructureReader.

    Lets the ligfilter/propfilter server tools report REAL pass/total counts without importing
    `schrodinger` in the server venv. `a["paths"]` is a list of structure-file paths (.mae/.maegz/
    .sdf/.pdb; formats StructureReader cannot stream — e.g. bare .smi — yield None, not an error).
    Returns {"counts": {path: n | None}, "errors": {path: repr}} (errors omitted when empty)."""
    from schrodinger import structure

    counts, errors = {}, {}
    for p in a.get("paths", []):
        try:
            counts[p] = sum(1 for _ in structure.StructureReader(p))
        except Exception as e:
            counts[p] = None
            errors[p] = repr(e)
    out = {"counts": counts}
    if errors:
        out["errors"] = errors
    return out


# ============================================================================
# ==== APPENDED HELPER GROUP: g13_mlcompose ====
# ============================================================================

# CMDS: "al_prep": _al_prep, "al_scores": _al_scores, "al_acquire": _al_acquire, "al_write_smiles": _al_write_smiles
#
# Helper functions for the al_dock active-learning docking loop (rdkit + numpy + scikit-learn, all
# bundled with Schrodinger 2026-2). Each returns a JSON-able dict; any raise is caught by the
# module __main__ wrapper and reported as {"error": repr(e)}. All imports are lazy (module style).


def _al_prep(a):
    """AL step 1: read a SMILES library (.smi/.csv, or a structure file), Morgan-FP featurize every
    valid molecule, cache the FP matrix (_al_fp.npy) + titles/SMILES (_al_lib.json) under out_dir,
    and pick a random seed batch (written to _al_batch_0.smi). Titles are sanitized to be
    whitespace-free so the two-column `<smiles> <title>` .smi round-trip through ligprep/glide (on
    which the score<->library mapping depends) stays intact. Returns cache paths, the seed .smi,
    library size, and whether rdkit/sklearn are importable."""
    import os
    import json
    import random

    out = {"rdkit": False, "sklearn": False}
    import numpy as np

    try:
        from rdkit import Chem
        from rdkit.DataStructs import ConvertToNumpyArray

        out["rdkit"] = True
    except Exception as e:
        return {"error": "rdkit unavailable: " + repr(e)}
    try:
        import sklearn  # noqa: F401

        out["sklearn"] = True
    except Exception:
        out["sklearn"] = False
    # Prefer the modern generator API; fall back to the legacy helper on older rdkit.
    radius, nbits = int(a.get("fp_radius", 2)), int(a.get("fp_bits", 2048))
    try:
        from rdkit.Chem import rdFingerprintGenerator as _rfg

        _gen = _rfg.GetMorganGenerator(radius=radius, fpSize=nbits)

        def _fp(m):
            return _gen.GetFingerprint(m)
    except Exception:
        from rdkit.Chem import AllChem

        def _fp(m):
            return AllChem.GetMorganFingerprintAsBitVect(m, radius, nBits=nbits)

    library, out_dir = a["library"], a["out_dir"]
    batch, seed = max(1, int(a.get("batch", 48))), int(a.get("seed", 0))
    ext = os.path.splitext(library)[1].lower()
    raw = []  # (title, smiles)
    if ext in (".smi", ".ismi", ".txt"):
        with open(library) as fh:
            for i, line in enumerate(fh):
                parts = line.split()
                if parts:
                    raw.append((parts[1] if len(parts) > 1 else f"mol_{i}", parts[0]))
    elif ext == ".csv":
        import csv as _c

        with open(library, newline="") as fh:
            rdr = list(_c.reader(fh))
        if rdr:
            hdr = [h.lower() for h in rdr[0]]
            si = next((k for k, h in enumerate(hdr) if "smiles" in h), 0)
            ni = next(
                (
                    k
                    for k, h in enumerate(hdr)
                    if h in ("name", "title", "id", "mol_id")
                ),
                None,
            )
            for i, row in enumerate(rdr[1:]):
                if row and si < len(row) and row[si].strip():
                    t = (
                        row[ni].strip()
                        if (ni is not None and ni < len(row) and row[ni].strip())
                        else f"mol_{i}"
                    )
                    raw.append((t, row[si].strip()))
    else:  # structure file -> canonical SMILES
        from schrodinger import structure
        from schrodinger.structutils import analyze

        for i, st in enumerate(structure.StructureReader(library)):
            raw.append((st.title or f"mol_{i}", analyze.generate_smiles(st)))
    if not raw:
        return {"error": f"no molecules read from {library}"}
    titles, smis, rows, seen = [], [], [], {}
    for i, (t, s) in enumerate(raw):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        # Collapse any internal whitespace (spaces/tabs/newlines) so the title survives the
        # `<smiles> <title>` .smi format and matches back exactly when glide keys results by title.
        t = "_".join(str(t).split()) or f"mol_{i}"
        if t in seen:  # keep titles unique (glide keys results by title)
            seen[t] += 1
            t = f"{t}_{seen[t]}"
        else:
            seen[t] = 0
        arr = np.zeros((nbits,), dtype=np.uint8)
        ConvertToNumpyArray(_fp(m), arr)
        rows.append(arr)
        titles.append(t)
        smis.append(s)
    if not rows:
        return {"error": "no valid SMILES after rdkit parsing"}
    X = np.vstack(rows).astype(np.uint8)
    fp_cache = os.path.join(out_dir, "_al_fp.npy")
    lib_cache = os.path.join(out_dir, "_al_lib.json")
    np.save(fp_cache, X)
    with open(lib_cache, "w") as fh:
        json.dump(
            {"titles": titles, "smiles": smis, "fp_radius": radius, "fp_bits": nbits},
            fh,
        )
    n = len(titles)
    seed_idx = random.Random(seed).sample(range(n), min(batch, n))
    seed_smi = os.path.join(out_dir, "_al_batch_0.smi")
    with open(seed_smi, "w") as fh:
        for i in seed_idx:
            fh.write(f"{smis[i]} {titles[i]}\n")
    out.update(
        {
            "n_library": n,
            "fp_cache": fp_cache,
            "lib_cache": lib_cache,
            "seed_smi": seed_smi,
            "seed_titles": [titles[i] for i in seed_idx],
        }
    )
    return out


def _al_scores(a):
    """AL helper: best Glide docking score per ligand title from a pose-viewer file (_pv.maegz).
    Reads r_i_docking_score (falling back to r_i_glide_gscore); entries with neither (the receptor)
    are skipped. Lower score = better. Returns {scores: {title: score}, n}."""
    from schrodinger import structure

    best = {}
    for st in structure.StructureReader(a["pose_file"]):
        sc = None
        for key in ("r_i_docking_score", "r_i_glide_gscore"):
            if key in st.property:
                sc = float(st.property[key])
                break
        if sc is None:
            continue  # receptor / non-scored entry
        t = st.title or st.property.get("s_m_title", "")
        if t and (t not in best or sc < best[t]):
            best[t] = sc
    return {"scores": best, "n": len(best)}


def _al_acquire(a):
    """AL step 2: train a cheap surrogate (surrogate='ridge'|'rf') on the FP of already-docked
    titles vs their docking score, predict the unlabeled remainder, and acquire the next batch by
    uncertainty-aware UCB (mean - kappa*std; docking score is MINIMIZED). Uncertainty = RF tree
    dispersion, or a bootstrap-Ridge ensemble std for ridge. Writes _al_batch_<iter>.smi. Returns
    {batch_smi, batch_titles, model:{r2_cv,rmse_cv,n_train}, predicted_top}."""
    import os
    import json
    import numpy as np

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.linear_model import Ridge
        from sklearn.model_selection import cross_val_score
    except Exception as e:
        return {"error": "scikit-learn unavailable: " + repr(e)}
    out_dir, labeled = a["out_dir"], (a.get("labeled") or {})
    acquire_n = max(1, int(a.get("acquire_n", 48)))
    surrogate, kappa = a.get("surrogate", "ridge"), float(a.get("kappa", 1.0))
    seed, it = int(a.get("seed", 0)), int(a.get("iter_idx", 1))
    X = np.load(os.path.join(out_dir, "_al_fp.npy"))
    with open(os.path.join(out_dir, "_al_lib.json")) as fh:
        lib = json.load(fh)
    titles, smis = lib["titles"], lib["smiles"]
    tindex = {t: i for i, t in enumerate(titles)}
    tr_idx = [tindex[t] for t in labeled if t in tindex]
    if len(tr_idx) < 2:
        return {"error": f"too few labeled points to train a surrogate ({len(tr_idx)})"}
    labeled_set = set(labeled)
    unl_idx = [i for i, t in enumerate(titles) if t not in labeled_set]
    if not unl_idx:
        return {
            "error": "library exhausted - no unlabeled molecules remain",
            "batch_smi": None,
        }
    Xtr = X[tr_idx].astype(np.float32)
    ytr = np.array([labeled[titles[i]] for i in tr_idx], dtype=np.float32)
    Xun = X[unl_idx].astype(np.float32)
    if surrogate == "rf":
        model = RandomForestRegressor(
            n_estimators=100, random_state=seed, n_jobs=-1
        ).fit(Xtr, ytr)
        mean = model.predict(Xun)
        std = np.stack([t.predict(Xun) for t in model.estimators_]).std(axis=0)
        base = RandomForestRegressor(n_estimators=60, random_state=seed, n_jobs=-1)
    else:  # ridge point estimate + bootstrap-ensemble uncertainty
        rng = np.random.RandomState(seed)
        n = len(ytr)
        preds = np.stack(
            [
                Ridge(alpha=1.0).fit(Xtr[bi], ytr[bi]).predict(Xun)
                for bi in (rng.randint(0, n, n) for _ in range(min(25, max(5, n))))
            ]
        )
        mean, std = preds.mean(axis=0), preds.std(axis=0)
        base = Ridge(alpha=1.0)
    ucb = mean - kappa * std  # minimize docking score -> smallest UCB is most promising
    order = list(np.argsort(ucb)[:acquire_n])
    pick = [unl_idx[j] for j in order]
    stats = {"surrogate": surrogate, "n_train": int(len(tr_idx))}
    if len(tr_idx) >= 5:
        try:
            cv = min(5, len(tr_idx))
            stats["r2_cv"] = round(
                float(cross_val_score(base, Xtr, ytr, cv=cv, scoring="r2").mean()), 4
            )
            stats["rmse_cv"] = round(
                float(
                    -cross_val_score(
                        base, Xtr, ytr, cv=cv, scoring="neg_root_mean_squared_error"
                    ).mean()
                ),
                4,
            )
        except Exception as e:
            stats["cv_error"] = repr(e)
    batch_smi = os.path.join(out_dir, f"_al_batch_{it}.smi")
    with open(batch_smi, "w") as fh:
        for i in pick:
            fh.write(f"{smis[i]} {titles[i]}\n")
    return {
        "batch_smi": batch_smi,
        "batch_titles": [titles[i] for i in pick],
        "model": stats,
        "predicted_top": [
            {
                "title": titles[unl_idx[j]],
                "pred": round(float(mean[j]), 4),
                "ucb": round(float(ucb[j]), 4),
            }
            for j in order[:10]
        ],
    }


def _al_write_smiles(a):
    """AL helper: write the cached SMILES for a list of titles to a .smi (for the top_k refine dock).
    Returns {out_smi, n} (out_smi is None if no title resolved)."""
    import os  # noqa: F401  (kept explicit; path is pre-joined by the caller)
    import json

    with open(os.path.join(a["out_dir"], "_al_lib.json")) as fh:
        lib = json.load(fh)
    idx = {t: i for i, t in enumerate(lib["titles"])}
    out_smi, wrote = a["out_smi"], 0
    with open(out_smi, "w") as fh:
        for t in a["titles"]:
            if t in idx:
                fh.write(f"{lib['smiles'][idx[t]]} {t}\n")
                wrote += 1
    return {"out_smi": out_smi if wrote else None, "n": wrote}


CMDS = {
    "info": _info,
    "smiles_to_3d": _smiles_to_3d,
    "properties": _properties,
    "convert": _convert,
    "job_status": _job_status,
    "job_wait": _job_wait,
    "launch": _launch,
    "trj_analyze": _trj_analyze,
    # g01_feploop
    "fep_map_qc": _fep_map_qc,
    "fep_parse_results": _fep_parse_results,
    # g02_qmprep
    "qm_cluster_extract": _qm_cluster_extract,
    "jaguar_in": _jaguar_in,
    "jaguar_energy": _jaguar_energy,
    "jaguar_pka_in": _jaguar_pka_in,
    "epik_pka_parse": _epik_pka_parse,
    # g03_parse
    "proplist": _proplist,
    # g04_poseqc
    "pose_validity": _pose_validity,
    "pose_ifp": _pose_ifp,
    # g05_structglue
    "pose_viewer_split": _pose_viewer_split,
    "reaction_enumerate": _reaction_enumerate,
    "mmod_confsearch": _mmod_confsearch,
    # g06_traj
    "trj_interactions": _trj_interactions,
    # g10_composites
    "cns_mpo": _cns_mpo,
    "pv_scores": _pv_scores,
    "write_subset": _write_subset,
    "enumerate_analogs": _enumerate_analogs,
    "cluster_frames": _cluster_frames,
    # g11_monitor
    "fep_edges": _fep_edges,
    # g12_filters
    "count_structures": _count_structures,
    # g13_mlcompose
    "al_prep": _al_prep,
    "al_scores": _al_scores,
    "al_acquire": _al_acquire,
    "al_write_smiles": _al_write_smiles,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "info"
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    try:
        print(json.dumps(CMDS[cmd](args)))
    except Exception as e:
        print(json.dumps({"error": repr(e)}))
