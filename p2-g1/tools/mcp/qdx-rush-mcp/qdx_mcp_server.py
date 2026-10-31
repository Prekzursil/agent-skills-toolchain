"""
QDX Rush / EXESS MCP server  (v2 — hardened)
============================================
Drives QDX's Rush cloud (quantum chemistry + drug-discovery) via `rush-py` 7.1.0:
  • EXESS QM — single-point energy, ESP-fit/Mulliken charges, QM interaction energy, geometry opt, QM/MM
  • fast NN-xTB, fragmented EXESS, structure prep, SMILES→3D, MSA, Boltz co-fold+affinity, PB solvation
  • run lifecycle — status, PARSED result collection, save-to-disk, list, delete

Auth: rush-py auto-loads RUSH_TOKEN + RUSH_PROJECT from `~/.rush/.env`. Jobs are asynchronous and cost
credits: submit → run_status/run_collect. This server holds no secrets.

Hardening (v2): run_collect now performs the second fetch and returns PARSED energies (kcal/mol) instead of
object-store pointers; transient 5xx/429/timeouts retry with backoff; failures return terminal-state
envelopes; RI methods fail fast without aux_basis; KSDFT requires a functional; Optional params accept null.
"""

from __future__ import annotations

import os
import json
import logging
import time
import random
import dataclasses
from pathlib import Path

# Load credentials from ~/.rush/.env BEFORE importing rush (kept out of any committed file).
try:
    from dotenv import load_dotenv

    load_dotenv(Path.home() / ".rush" / ".env")
except Exception:
    pass

from mcp.server.fastmcp import FastMCP

import rush
from rush import exess, auto3d, prepare, boltz, mmseqs2, pbsa, fried, nnxtb

mcp = FastMCP("qdx-rush")

HARTREE_TO_KCAL = 627.5094740631

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------- helpers: errors, retry, envelopes
def _err(e) -> str:
    return json.dumps({"error": type(e).__name__, "message": str(e)[:1500]})


def _retryable(e) -> bool:
    """Retry transient transport errors (5xx/429/connection/timeout); never GraphQL/4xx/auth."""
    name = type(e).__name__
    if name in ("TransportQueryError", "RunModuleError"):
        return False
    if name in (
        "TransportServerError",
        "ConnectionError",
        "Timeout",
        "ConnectTimeout",
        "ReadTimeout",
        "ConnectionResetError",
    ):
        return True
    msg = str(e)
    return any(
        tok in msg
        for tok in (
            "429",
            " 500",
            " 502",
            " 503",
            " 504",
            "Service Unavailable",
            "Bad Gateway",
            "temporarily",
        )
    )


def _with_retry(fn, *a, _tries=5, **k):
    delay = 0.6
    for i in range(_tries):
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001
            if i == _tries - 1 or not _retryable(e):
                raise
            time.sleep(delay + random.random() * 0.3)
            delay = min(delay * 2, 8.0)


def _fields(obj, names) -> dict:
    """Pull named attributes into a strictly JSON-safe dict (primitives, lists-of-primitives, else str).
    Guards against PyO3 objects like FragmentRef leaking into json.dumps (which would force a parse fallback)."""
    out = {}
    for n in names:
        try:
            v = getattr(obj, n)
        except Exception:
            continue
        if v is None or callable(v):
            continue
        if isinstance(v, (int, float, str, bool)):
            out[n] = v
        elif isinstance(v, (list, tuple)):
            out[n] = [x for x in list(v)[:12] if isinstance(x, (int, float, str, bool))]
        else:
            out[n] = str(v)[:200]
    return out


def _spec(gpus=None, walltime_min=None, target=None):
    kw = {}
    if gpus is not None:
        kw["gpus"] = gpus
    if walltime_min is not None:
        kw["walltime"] = walltime_min
    if target:
        kw["target"] = target
    return rush.RunSpec(**kw) if kw else None


def _opts(name, tags=None):
    return rush.RunOpts(name=name, tags=tags or ["mcp"])


_RI_METHODS = {"RestrictedRIMP2", "UnrestrictedRIMP2"}


def _validate(method, aux_basis):
    """Return an error-string if the method/param combo is unsupported, else None.
    (KSDFT without an explicit functional is allowed — EXESS applies its default B3LYP via the KSDFT sentinel.)"""
    if method in _RI_METHODS and not aux_basis:
        return f"method '{method}' (RI) REQUIRES aux_basis (e.g. 'cc-pVDZ-RIFIT'). Pass aux_basis."
    if (
        method
        and method.startswith("Unrestricted")
        and ("KSDFT" in method or "RIMP2" in method)
    ):
        return f"method '{method}' is not supported by EXESS (no unrestricted KS-DFT / RI-MP2)."
    return None


def _exkw(aux_basis=None, functional=None, gpus=None, walltime_min=None, target=None):
    kw = {}
    if aux_basis:
        kw["aux_basis"] = aux_basis
    if functional:
        kw["ksdft_keywords"] = exess.KSDFTKeywords(functional=functional)
    spec = _spec(gpus, walltime_min, target)
    if spec is not None:
        kw["run_spec"] = spec
    return kw


def _parse_charge_exports(exports, strict: bool = False) -> dict:
    """Return complete atom-charge arrays without the truncation applied by _fields().

    ``strict=False`` (the shared / auto energy path, the default): a malformed-but-present
    charge export must NOT flip an otherwise-complete energy result to non-done, so the
    malformation is logged and swallowed — the caller keeps its energy fields and just gets
    no charge fields. ``strict=True`` (the explicit ``charges`` path): re-raise so the caller
    surfaces the precise malformation.
    """
    if not isinstance(exports, dict):
        return {}
    try:
        return _charge_exports_or_raise(exports)
    except ValueError:
        if strict:
            raise
        logger.warning(
            "EXESS charge exports are malformed; omitting charge fields from the energy result",
            exc_info=True,
        )
        return {}


def _charge_exports_or_raise(exports: dict) -> dict:
    """Strict parse of the CHELPG/Mulliken atom-charge arrays; raises ValueError on any
    malformed-but-present array. Absent arrays are skipped (returns {} when none present)."""
    out = {}
    for key in ("chelpg_charges", "mulliken_charges"):
        values = exports.get(key)
        if values is None:
            continue
        if not isinstance(values, (list, tuple)) or not values:
            raise ValueError(f"EXESS export '{key}' is not a non-empty charge array")
        try:
            out[key] = [float(value) for value in values]
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"EXESS export '{key}' contains a non-numeric charge"
            ) from e

    if not out:
        return {}

    lengths = {len(values) for values in out.values()}
    if len(lengths) != 1:
        raise ValueError("CHELPG and Mulliken charge arrays have different atom counts")

    primary = out.get("chelpg_charges") or out["mulliken_charges"]
    out.update(
        {
            "charges": primary,
            "charge_model": ("CHELPG" if "chelpg_charges" in out else "Mulliken"),
            "n_atoms": len(primary),
            "units": "elementary_charge",
            "atom_order": "input_topology",
        }
    )
    if "chelpg_charges" in out:
        out["chelpg_charge_sum"] = round(sum(out["chelpg_charges"]), 10)
    if "mulliken_charges" in out:
        out["mulliken_charge_sum"] = round(sum(out["mulliken_charges"]), 10)
    return out


# ----------------------------------------------------------------- result parsers (the F1 fix)
def _parse_exess(raw) -> dict:
    res = exess.ResultRef.from_raw_output(raw).fetch()
    mbe = res.calc.qmmbe
    d = _fields(
        mbe,
        [
            "expanded_hf_energy",
            "expanded_mp2_ss_correction",
            "expanded_mp2_os_correction",
            "expanded_ccsd_correction",
            "reference_fragment",
            "num_iters",
        ],
    )
    comps = [
        d[k]
        for k in (
            "expanded_hf_energy",
            "expanded_mp2_ss_correction",
            "expanded_mp2_os_correction",
            "expanded_ccsd_correction",
        )
        if isinstance(d.get(k), (int, float))
    ]
    total = sum(comps) if comps else None
    d["total_hartree"] = total
    d["total_kcal_per_mol"] = (
        round(total * HARTREE_TO_KCAL, 4) if total is not None else None
    )
    d["is_interaction_energy"] = d.get("reference_fragment") is not None
    d.update(_parse_charge_exports(getattr(res, "exports", None)))
    return d


def _parse_charges(raw) -> dict:
    res = exess.ResultRef.from_raw_output(raw).fetch()
    out = _parse_charge_exports(getattr(res, "exports", None), strict=True)
    missing = [key for key in ("chelpg_charges", "mulliken_charges") if key not in out]
    if missing:
        raise ValueError(
            f"EXESS result is missing charge exports: {', '.join(missing)}"
        )
    method = getattr(res.calc.qmmbe, "method", None)
    if isinstance(method, str):
        out["method"] = method
    return out


def _parse_nnxtb(raw) -> dict:
    res = nnxtb.ResultRef.from_raw_output(raw).fetch()
    d = _fields(
        res,
        [
            "energy",
            "energy_hartree",
            "total_energy",
            "forces_mev_per_angstrom",
            "frequencies_inv_cm",
        ],
    )
    e = d.get("energy") or d.get("energy_hartree") or d.get("total_energy")
    if isinstance(e, (int, float)):
        d["energy_kcal_per_mol"] = round(e * HARTREE_TO_KCAL, 4)
    return d


def _parse_boltz(raw) -> dict:
    res = boltz.ResultRef.from_raw_output(raw).fetch()
    aff = getattr(res, "affinities", None)
    return (
        _fields(
            aff,
            [
                "affinity_pred_value",
                "affinity_probability_binary",
                "affinity_pred_value1",
                "affinity_probability_binary1",
            ],
        )
        if aff is not None
        else {}
    )


def _parse_pbsa(raw) -> dict:
    res = pbsa.ResultRef.from_raw_output(raw).fetch()
    return _fields(
        res, ["solvation_energy", "total_energy", "energy", "polar", "nonpolar"]
    )


def _parse_opt(raw) -> dict:
    res = exess.OptimizationResultRef.from_raw_output(raw).fetch()
    steps = getattr(res, "steps", None)
    out = {}
    try:
        if steps:
            out["n_steps"] = len(steps)
            out["final_energy_hartree"] = getattr(steps[-1], "total_energy", None)
            if isinstance(out["final_energy_hartree"], (int, float)):
                out["final_energy_kcal_per_mol"] = round(
                    out["final_energy_hartree"] * HARTREE_TO_KCAL, 4
                )
    except Exception:
        pass
    return out


_PARSERS = {
    "exess": _parse_exess,
    "energy": _parse_exess,
    "interaction": _parse_exess,
    "interaction_energy": _parse_exess,
    "calculate": _parse_exess,
    "qmmm": _parse_exess,
    "charges": _parse_charges,
    "esp_charges": _parse_charges,
    "nnxtb": _parse_nnxtb,
    "boltz": _parse_boltz,
    "pbsa": _parse_pbsa,
    "optimization": _parse_opt,
}


# ----------------------------------------------------------------- config / auth
@mcp.tool()
def qdx_whoami() -> str:
    """Report Rush auth + project config (does not expose the token)."""
    from importlib.metadata import version, PackageNotFoundError

    try:
        rp = version("rush-py")
    except PackageNotFoundError:
        rp = "?"
    from rush import session

    tok = os.getenv("RUSH_TOKEN")
    return json.dumps(
        {
            "rush_token_set": bool(tok),
            "rush_token_tail": (tok[-6:] if tok else None),
            "rush_project": os.getenv("RUSH_PROJECT"),
            "project_set": bool(os.getenv("RUSH_PROJECT")),
            "endpoint": getattr(session, "GRAPHQL_ENDPOINT", "?"),
            "rush_py": rp,
        }
    )


# ----------------------------------------------------------------- EXESS quantum chemistry
@mcp.tool()
def exess_energy(
    structure_path: str,
    method: str = "RestrictedHF",
    basis: str = "cc-pVDZ",
    aux_basis: str | None = None,
    functional: str | None = None,
    gpus: int | None = None,
    walltime_min: int | None = None,
    target: str | None = None,
    name: str = "exess_energy",
) -> str:
    """Submit an EXESS single-point QM energy. method: RestrictedHF | RestrictedRIMP2 | RestrictedKSDFT.
    aux_basis is REQUIRED for RI-MP2 (e.g. 'cc-pVDZ-RIFIT'); functional REQUIRED for KSDFT (e.g. 'B3LYP').
    gpus/walltime_min/target (Bullet/Bullet2/Bullet3/Gadi/Setonix) cap cost. Returns a run_id."""
    bad = _validate(method, aux_basis)
    if bad:
        return json.dumps({"error": "invalid_request", "message": bad})
    try:
        run = exess.energy(
            structure_path,
            method=method,
            basis=basis,
            run_opts=_opts(name),
            **_exkw(aux_basis, functional, gpus, walltime_min, target),
        )
        return json.dumps(
            {"run_id": str(run.id), "kind": "energy", "method": method, "basis": basis}
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def exess_esp_charges(
    structure_path: str,
    method: str = "RestrictedKSDFT",
    basis: str = "cc-pVDZ",
    aux_basis: str | None = None,
    functional: str | None = None,
    gpus: int | None = None,
    walltime_min: int | None = None,
    target: str | None = None,
    name: str = "exess_esp_charges",
) -> str:
    """Submit QM partial charges for a LIGAND-ONLY topology. CHELPG is the electrostatic-potential (ESP)
    fit used as `charges`; Mulliken charges are returned for comparison. The topology supplies protonation
    and formal charge. Returns a run_id; retrieve arrays with run_collect(run_id, kind='charges')."""
    bad = _validate(method, aux_basis)
    if bad:
        return json.dumps({"error": "invalid_request", "message": bad})

    try:
        run = exess.energy(
            structure_path,
            method=method,
            basis=basis,
            frag_keywords=None,
            export_keywords=exess.ExportKeywords(
                export_chelpg_charges=True,
                export_mulliken_charges=True,
            ),
            convert_hdf5_to_json=True,
            run_opts=_opts(name),
            **_exkw(aux_basis, functional, gpus, walltime_min, target),
        )
        return json.dumps(
            {
                "run_id": str(run.id),
                "kind": "charges",
                "method": method,
                "basis": basis,
                "aux_basis": aux_basis,
                "functional": (
                    functional
                    if functional is not None
                    else ("B3LYP" if method == "RestrictedKSDFT" else None)
                ),
                "charge_models": ["CHELPG", "Mulliken"],
                "next": "run_collect(run_id, kind='charges')",
            }
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def exess_interaction_energy(
    structure_path: str,
    reference_fragment: int,
    method: str = "RestrictedRIMP2",
    basis: str = "cc-pVDZ",
    aux_basis: str | None = "cc-pVDZ-RIFIT",
    functional: str | None = None,
    fragmentation_level: str = "Dimer",
    dimer_cutoff: float | None = 12.0,
    trimer_cutoff: float | None = None,
    included_fragments: list[int] | None = None,
    gpus: int | None = None,
    walltime_min: int | None = None,
    target: str | None = None,
    name: str = "exess_interaction",
) -> str:
    """Submit an EXESS QM INTERACTION energy (negative = binding). Structure must define fragments;
    reference_fragment (0-indexed, usually the ligand) is measured against the rest. Defaults to RI-MP2 with
    aux_basis. fragmentation_level Dimer|Trimer|Tetramer; dimer_cutoff/trimer_cutoff (Å) trade accuracy vs cost;
    included_fragments restricts to a pocket (reference auto-included). Returns a run_id."""
    bad = _validate(method, aux_basis)
    if bad:
        return json.dumps({"error": "invalid_request", "message": bad})
    try:
        fkw = {"reference_fragment": reference_fragment, "level": fragmentation_level}
        if dimer_cutoff is not None:
            fkw["dimer_cutoff"] = dimer_cutoff
        if trimer_cutoff is not None:
            fkw["trimer_cutoff"] = trimer_cutoff
        if included_fragments is not None:
            fkw["included_fragments"] = sorted(
                set(list(included_fragments) + [reference_fragment])
            )
        extra = _exkw(aux_basis, functional, gpus, walltime_min, target)
        extra["frag_keywords"] = exess.FragKeywords(**fkw)
        run = exess.interaction_energy(
            structure_path,
            reference_fragment=reference_fragment,
            method=method,
            basis=basis,
            run_opts=_opts(name),
            **extra,
        )
        return json.dumps(
            {
                "run_id": str(run.id),
                "kind": "interaction",
                "reference_fragment": reference_fragment,
                "method": method,
                "level": fragmentation_level,
            }
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def exess_optimization(
    structure_path: str,
    max_iters: int = 100,
    method: str = "RestrictedHF",
    basis: str = "cc-pVDZ",
    aux_basis: str | None = None,
    gpus: int | None = None,
    walltime_min: int | None = None,
    target: str | None = None,
    name: str = "exess_opt",
) -> str:
    """Submit an EXESS geometry optimization. Gradients (and thus opt) support only RestrictedHF /
    RestrictedRIMP2 (NOT KSDFT). aux_basis REQUIRED for RI-MP2. Returns a run_id."""
    if method == "RestrictedKSDFT":
        return json.dumps(
            {
                "error": "invalid_request",
                "message": "EXESS geometry optimization does not support KSDFT (no analytical gradients). Use RestrictedHF or RestrictedRIMP2 (+aux_basis).",
            }
        )
    bad = _validate(method, aux_basis)
    if bad:
        return json.dumps({"error": "invalid_request", "message": bad})
    try:
        run = exess.optimization(
            structure_path,
            max_iters=max_iters,
            method=method,
            basis=basis,
            run_opts=_opts(name),
            **_exkw(aux_basis, None, gpus, walltime_min, target),
        )
        return json.dumps(
            {"run_id": str(run.id), "kind": "optimization", "max_iters": max_iters}
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def exess_calculate(
    structure_path: str,
    driver: str = "Energy",
    method: str = "RestrictedHF",
    basis: str = "cc-pVDZ",
    aux_basis: str | None = None,
    functional: str | None = None,
    gpus: int | None = None,
    walltime_min: int | None = None,
    target: str | None = None,
    name: str = "exess_calc",
) -> str:
    """Generic EXESS calc with explicit driver: Energy | Gradient | Optimization | Dynamics. Escape hatch.
    aux_basis REQUIRED for RI-MP2; functional REQUIRED for KSDFT. Returns a run_id."""
    bad = _validate(method, aux_basis)
    if bad:
        return json.dumps({"error": "invalid_request", "message": bad})
    try:
        run = exess.calculate(
            structure_path,
            driver=driver,
            method=method,
            basis=basis,
            run_opts=_opts(name),
            **_exkw(aux_basis, functional, gpus, walltime_min, target),
        )
        return json.dumps(
            {"run_id": str(run.id), "kind": "calculate", "driver": driver}
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def exess_qmmm(
    structure_path: str,
    n_timesteps: int,
    dt_ps: float = 0.002,
    temperature_kelvin: float = 290.0,
    pressure_atm: float | None = None,
    qm_fragments: list[int] | None = None,
    mm_fragments: list[int] | None = None,
    method: str = "RestrictedHF",
    basis: str = "cc-pVDZ",
    aux_basis: str | None = None,
    functional: str | None = None,
    gpus: int | None = None,
    walltime_min: int | None = None,
    target: str | None = None,
    name: str = "exess_qmmm",
) -> str:
    """EXESS QM/MM Born-Oppenheimer MD. qm_fragments/mm_fragments are 0-indexed fragment lists (QM = ligand +
    key residues). pressure_atm set → NPT else NVT. aux_basis REQUIRED for RI-MP2. Returns a run_id."""
    bad = _validate(method, aux_basis)
    if bad:
        return json.dumps({"error": "invalid_request", "message": bad})
    try:
        kw = dict(
            n_timesteps=n_timesteps,
            dt_ps=dt_ps,
            temperature_kelvin=temperature_kelvin,
            qm_fragments=qm_fragments,
            mm_fragments=mm_fragments,
            method=method,
            basis=basis,
            run_opts=_opts(name),
            **_exkw(aux_basis, functional, gpus, walltime_min, target),
        )
        if pressure_atm is not None:
            kw["pressure_atm"] = pressure_atm
        run = exess.qmmm(structure_path, **kw)
        return json.dumps(
            {"run_id": str(run.id), "kind": "qmmm", "n_timesteps": n_timesteps}
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ----------------------------------------------------------------- fast QM / fragmented / prep
@mcp.tool()
def nnxtb_energy(
    structure_path: str,
    multiplicity: int | None = None,
    compute_forces: bool = False,
    compute_frequencies: bool = False,
    name: str = "nnxtb",
) -> str:
    """Fast neural-network xTB energy (semiempirical; cheap conformer/pre-screen). IMPORTANT: net charge and
    protonation come from the INPUT STRUCTURE's formal charges (nnxtb.energy takes no charge argument) — prepare
    a charged/zwitterionic ligand (e.g. phenibut) at the correct state first, or the energy is wrong. Returns a run_id."""
    try:
        run = nnxtb.energy(
            structure_path,
            compute_forces=compute_forces,
            compute_frequencies=compute_frequencies,
            multiplicity=multiplicity,
            run_opts=_opts(name),
        )
        return json.dumps({"run_id": str(run.id), "kind": "nnxtb"})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def fried_fragmented_exess(
    input_file: str, distance_threshold: float = 4.0, trimer_cutoff_cap: float = 15.0
) -> str:
    """Fragmented EXESS for a ligand complex — auto-fragments the pocket around the ligand within
    distance_threshold (Å) and submits fragment EXESS jobs. Level of theory is module-fixed; potentially
    expensive/unbounded. Returns a LIST of run_ids (collect each with run_collect kind='exess')."""
    try:
        runs = (
            fried.fragmented_exess(
                input_file,
                distance_threshold=distance_threshold,
                trimer_cutoff_cap=trimer_cutoff_cap,
                collect=False,
            )
            or []
        )
        return json.dumps(
            {"run_ids": [str(r.id) for r in runs], "kind": "exess", "n_jobs": len(runs)}
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def auto3d_generate(smiles: list[str], k: int = 1, name: str = "auto3d") -> str:
    """SMILES → 3D conformers (auto3d). Async producer — retrieve/save the structure with save_run(kind='structure')."""
    try:
        run = auto3d.generate(smiles, k=k, run_opts=_opts(name))
        return json.dumps(
            {"run_id": str(run.id), "kind": "structure", "n_smiles": len(smiles)}
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def prepare_protein(
    structure_path: str, ph: float = 7.4, name: str = "prepare_protein"
) -> str:
    """Prepare a protein (protonation/capping). Async producer — save output with save_run(kind='structure')."""
    try:
        run = prepare.protein(structure_path, ph=ph, run_opts=_opts(name))
        return json.dumps({"run_id": str(run.id), "kind": "structure", "ph": ph})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def prepare_protein_ligand(
    structure_path: str,
    ligand_names: list[str],
    out_path: str,
    ph: float = 7.4,
    max_wait_min: int = 30,
    name: str = "prepare_complex",
) -> str:
    """Prepare a protein-ligand COMPLEX and write it to out_path. NOTE: this tool BLOCKS — the ligand
    extraction + merge happens in-process and cannot be recovered by a later run_collect, so it collects,
    merges, and saves here. ligand_names are the ligand residue names. Returns {complex_path}."""
    try:
        run = prepare.protein_ligand(
            structure_path, ligand_names=ligand_names, ph=ph, run_opts=_opts(name)
        )
        trcs = run.collect(
            max_wait_time=max_wait_min * 60
        ).fetch()  # prepare.ResultRef.fetch() -> list[PyTRC]
        rush.save_structure(trcs, out_path)
        n = len(trcs) if isinstance(trcs, list) else 1
        return json.dumps(
            {
                "status": "done",
                "complex_path": out_path,
                "n_structures": n,
                "ligand_names": ligand_names,
            }
        )
    except rush.RunError as e:
        return json.dumps({"status": "failed", "error": str(e)[:2000]})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def mmseqs2_search(sequences: list[str], name: str = "mmseqs2") -> str:
    """Sequence/MSA search (MMseqs2) → the MSA boltz_fold needs. Async producer — save with save_run(kind='structure')."""
    try:
        run = mmseqs2.search(sequences, run_opts=_opts(name))
        return json.dumps(
            {"run_id": str(run.id), "kind": "structure", "n_sequences": len(sequences)}
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def boltz_fold(
    protein_sequence: str,
    ligand_smiles: str,
    msa_path: str,
    protein_chain: str = "A",
    ligand_chain: str = "B",
    name: str = "boltz_fold",
) -> str:
    """Co-fold protein + ligand and predict BINDING AFFINITY (Boltz-2). msa_path = local MSA from mmseqs2_search
    (saved via save_run). Result affinity_pred_value = log10 IC50 (µM), LOWER = stronger; affinity_probability_binary
    (0-1) HIGHER = more likely a binder. Returns a run_id (collect with kind='boltz')."""
    try:
        seqs = [
            boltz.ProteinSequence(
                id=[protein_chain], sequence=protein_sequence, msa=msa_path
            ),
            boltz.LigandSequence(id=[ligand_chain], smiles=ligand_smiles),
        ]
        run = boltz.fold(
            seqs, affinity_binder_chain_id=ligand_chain, run_opts=_opts(name)
        )
        return json.dumps(
            {"run_id": str(run.id), "kind": "boltz", "affinity_binder": ligand_chain}
        )
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def pbsa_solvation(
    structure_path: str,
    solute_dielectric: float = 2.0,
    solvent_dielectric: float = 80.0,
    solvent_radius: float = 1.4,
    ion_concentration: float = 0.15,
    temperature: float = 298.15,
    spacing: float = 0.5,
    sasa_gamma: float = 0.0072,
    sasa_beta: float = 0.0,
    sasa_n_samples: int = 1000,
    convergence: float = 1e-4,
    box_size_factor: float = 2.0,
    name: str = "pbsa",
) -> str:
    """Poisson-Boltzmann + SASA solvation energy (physiological water defaults). Returns a run_id (collect kind='pbsa')."""
    try:
        run = pbsa.solvation_energy(
            structure_path,
            solute_dielectric=solute_dielectric,
            solvent_dielectric=solvent_dielectric,
            solvent_radius=solvent_radius,
            ion_concentration=ion_concentration,
            temperature=temperature,
            spacing=spacing,
            sasa_gamma=sasa_gamma,
            sasa_beta=sasa_beta,
            sasa_n_samples=sasa_n_samples,
            convergence=convergence,
            box_size_factor=box_size_factor,
            run_opts=_opts(name),
        )
        return json.dumps({"run_id": str(run.id), "kind": "pbsa"})
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def structure_info(structure_path: str) -> str:
    """Load a local structure and report atom count + FRAGMENT layout (n_fragments + per-fragment atom counts)
    so you can choose reference_fragment / included_fragments for interaction energy."""
    try:
        trc = rush.load_structure(structure_path)
        trcs = trc if isinstance(trc, list) else [trc]
        out = []
        for i, t in enumerate(trcs):
            d = rush.to_dict(t)
            topo = d.get("topology", d) if isinstance(d, dict) else {}
            info = {"index": i}
            for key in ("symbols", "geometry", "fragments", "fragment_formal_charges"):
                v = topo.get(key)
                if isinstance(v, list):
                    info[key + "_count"] = len(v)
            frags = topo.get("fragments")
            if isinstance(frags, list):
                info["n_fragments"] = len(frags)
                info["fragment_atom_counts"] = [len(f) for f in frags][:300]
            out.append(info)
        return json.dumps(out)[:6000]
    except Exception as e:  # noqa: BLE001
        return _err(e)


# ----------------------------------------------------------------- run lifecycle
@mcp.tool()
def run_status(run_id: str) -> str:
    """Get a run's status/metadata (retries transient errors)."""
    try:
        info = _with_retry(rush.fetch_run_info, run_id)
    except Exception as e:  # noqa: BLE001
        return _err(e)
    if info is None:
        return json.dumps({"status": "not_found", "run_id": run_id})
    d = (
        dataclasses.asdict(info)
        if dataclasses.is_dataclass(info)
        else _fields(
            info, ["name", "description", "status", "tags", "walltime", "deleted_at"]
        )
    )
    for heavy in ("stdout", "trace", "result"):
        if isinstance(d.get(heavy), str) and len(d[heavy]) > 500:
            d[heavy] = d[heavy][:500] + "…[clipped]"
    return json.dumps({"status": "ok", "run_id": run_id, "info": d})[:6000]


@mcp.tool()
def run_collect(run_id: str, kind: str = "auto", max_wait_seconds: int = 1800) -> str:
    """Wait for a run and return PARSED results (energies in hartree + kcal/mol; affinities; etc.).
    kind: exess | interaction | optimization | charges | nnxtb | boltz | pbsa | auto (tries each). Timeout is
    non-terminal → {'status':'still_running'}. For QM/MM/optimization/fried/boltz raise max_wait_seconds."""
    try:
        raw = _with_retry(rush.collect_run, run_id, max_wait_time=max_wait_seconds)
    except rush.RunError as e:
        m = str(e)
        if "time" in m.lower() and "out" in m.lower():
            return json.dumps(
                {
                    "status": "still_running",
                    "run_id": run_id,
                    "waited_seconds": max_wait_seconds,
                }
            )
        return json.dumps({"status": "failed", "run_id": run_id, "error": m[:3000]})
    except Exception as e:  # noqa: BLE001
        return _err(e)
    parsers = (
        [_PARSERS[kind]]
        if kind in _PARSERS
        else [_parse_exess, _parse_nnxtb, _parse_boltz, _parse_pbsa, _parse_opt]
    )
    for p in parsers:
        try:
            out = p(raw)
            if out:
                return json.dumps(
                    {"status": "done", "run_id": run_id, "kind": kind, "result": out}
                )
        except Exception:  # noqa: BLE001
            continue
    return json.dumps(
        {
            "status": "done",
            "run_id": run_id,
            "note": "completed but could not parse into a known result type; use save_run for raw output",
            "raw_preview": str(raw)[:2000],
        }
    )


@mcp.tool()
def save_run(
    run_id: str, out_path: str, kind: str = "structure", max_wait_seconds: int = 1800
) -> str:
    """Materialize a completed run's STRUCTURE output to a local file, so producer runs (prepare_protein /
    prepare_protein_ligand / auto3d) can be chained into EXESS / boltz tools. Fetches the run's TRC(s) via
    `prepare.ResultRef.from_raw_output(raw).fetch()` and writes them with `rush.save_structure`. For MSA or
    energy outputs the MCP cannot target an arbitrary local path — use run_collect or rush-py directly.
    Returns {status, path, n_structures}."""
    if kind != "structure":
        return json.dumps(
            {
                "status": "error",
                "run_id": run_id,
                "message": f"save_run supports kind='structure' only; for '{kind}' output use run_collect or rush-py directly",
            }
        )
    try:
        raw = _with_retry(rush.collect_run, run_id, max_wait_time=max_wait_seconds)
    except rush.RunError as e:
        return json.dumps({"status": "failed", "error": str(e)[:2000]})
    except Exception as e:  # noqa: BLE001
        return _err(e)
    try:
        trcs = prepare.ResultRef.from_raw_output(raw).fetch()  # -> list[PyTRC]
        rush.save_structure(trcs, out_path)
        n = len(trcs) if isinstance(trcs, list) else 1
        return json.dumps(
            {"status": "done", "path": out_path, "run_id": run_id, "n_structures": n}
        )
    except Exception as e:  # noqa: BLE001
        return json.dumps(
            {
                "status": "error",
                "run_id": run_id,
                "message": f"could not materialize as a structure ({type(e).__name__}: {str(e)[:400]}); for MSA/energy outputs use run_collect or rush-py directly",
            }
        )


@mcp.tool()
def list_runs(name_contains: str | None = None, limit: int = 20) -> str:
    """List recent run IDs in the project (retries transient errors)."""
    try:
        ids = _with_retry(rush.fetch_runs, name_contains=name_contains, limit=limit)
        return json.dumps([str(i) for i in ids])
    except Exception as e:  # noqa: BLE001
        return _err(e)


@mcp.tool()
def delete_run(run_id: str) -> str:
    """Delete a run."""
    try:
        _with_retry(rush.delete_run, run_id)
        return json.dumps({"status": "deleted", "run_id": run_id})
    except Exception as e:  # noqa: BLE001
        return _err(e)


if __name__ == "__main__":
    mcp.run()
