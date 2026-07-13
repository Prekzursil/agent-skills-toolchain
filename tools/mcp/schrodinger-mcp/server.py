"""Schrodinger / Maestro MCP server.

A thin, security-conscious MCP wrapper over a local Schrodinger Suite install.
It NEVER imports `schrodinger` in-process (that only works under `$SCHRODINGER/run`);
every tool builds an argv list and hands it to the single `_exec()` chokepoint,
which runs it WITHOUT a shell. Client-supplied paths are validated by `_safe_path`
(rejects flag-like values, normalizes) before they reach any argv -> no shell or
argument injection. `_exec` is the only subprocess site and is not an MCP tool,
so untrusted tool params never flow directly into subprocess.run.

Config (cross-platform):
  - $SCHRODINGER : install root. Defaults to the Windows path; on POSIX set it.
Transport: stdio (Claude Code / Claude Desktop).
"""
import os
import re
import csv as _csv
import glob
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
import time
import urllib.request

from mcp.server.fastmcp import FastMCP

# Default to the licensed 2026-2 install. The .mcp.json env block overrides this at
# runtime, but keep the in-code default current so a bare launch still resolves.
SCHRODINGER = os.environ.get("SCHRODINGER", r"D:\Program Files\Schrodinger 2026-2")
HERE = os.path.dirname(os.path.abspath(__file__))
HELPER = os.path.join(HERE, "_sch_helper.py")

mcp = FastMCP("schrodinger")


# ---------- internal (not MCP tools) ----------

def _run() -> str:
    win = os.path.join(SCHRODINGER, "run.exe")
    return win if os.path.exists(win) else os.path.join(SCHRODINGER, "run")


def _driver(name: str) -> str:
    """Resolve a Schrodinger product driver, checking the install root AND utilities/.
    glide/ligprep/qikprop/prime_mmgbsa live at the root; prepwizard lives in utilities/."""
    for base in (SCHRODINGER, os.path.join(SCHRODINGER, "utilities")):
        for cand in (os.path.join(base, name + ".exe"), os.path.join(base, name)):
            if os.path.exists(cand):
                return cand
    return os.path.join(SCHRODINGER, name)  # fall back to root name for a sensible error


def _safe_path(p: str, must_exist: bool = False) -> str:
    """Validate a client-supplied path before it can reach an argv.
    Rejects empty/flag-like ('-...') values and normalizes to absolute."""
    if not isinstance(p, str) or not p.strip() or p.strip().startswith("-"):
        raise ValueError(f"invalid/unsafe path: {p!r}")
    if any(ch in p for ch in "\r\n\x00"):  # a newline could inject a 2nd Glide .in directive line
        raise ValueError(f"unsafe path (control char): {p!r}")
    ap = os.path.abspath(p)
    if must_exist and not os.path.exists(ap):
        raise FileNotFoundError(ap)
    return ap


# Server-chosen environment-overlay keys a tool may set on a child process. These are
# set by SERVER code (never from a client string) to route a GPU job (CUDA_VISIBLE_DEVICES)
# or carry the license flag; any other key is dropped, so a tool cannot smuggle env in.
_ENV_OVERLAY_ALLOW = frozenset({
    "CUDA_VISIBLE_DEVICES", "SCHRODINGER_FEATURE_FLAGS",
    "SCHRODINGER_JOBSERVER_CONFIG_FILE", "SCHRODINGER_JOBDB2", "OPLSDIR",
})


def _exec(argv, timeout=300, cwd=None, env=None):
    """Single subprocess chokepoint. argv is a pre-built list; never shell=True.
    Callers pass only validated, structured args -> no shell/arg injection here.
    stdin=DEVNULL is REQUIRED: this server runs over stdio (its own stdin is the MCP
    pipe). Without redirecting, a spawned `run python3 ...` child inherits that live
    pipe and blocks forever reading it -> every compute tool hangs to the 300s client
    timeout (while the same command runs in ~1s from a shell). DEVNULL gives an
    immediate EOF so the child never blocks on stdin.

    `env`: an OPTIONAL, SERVER-built dict of extra environment variables overlaid on
    os.environ for the child (e.g. {"CUDA_VISIBLE_DEVICES": "2"} to pin a GPU for the
    multi-GPU pool, or the license feature flag). Only keys in _ENV_OVERLAY_ALLOW are
    honored and values are str()-cast into the env dict -> this is an environment
    mapping, not a shell string, so it adds no injection surface. Passing env=None
    keeps the prior behavior exactly (child inherits this process's environment)."""
    child_env = None
    if env:
        child_env = os.environ.copy()
        for k, v in env.items():
            if k in _ENV_OVERLAY_ALLOW and v is not None:
                child_env[k] = str(v)
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                          stdin=subprocess.DEVNULL, env=child_env)


def _helper(cmd: str, args: dict, timeout: int = 300) -> dict:
    """Invoke _sch_helper.py inside the Schrodinger interpreter; parse its JSON line.
    `args` is JSON-encoded into one argv element (no shell), so values are inert."""
    try:
        p = _exec([_run(), "python3", HELPER, cmd, json.dumps(args)], timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout}s"}
    for line in reversed(p.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {"error": "no JSON from helper", "stdout": p.stdout[-1500:], "stderr": p.stderr[-1500:]}


# ---------- async job control (the enabler for MD/FEP/WaterMap) ----------
# Long GPU-bound jobs (minutes->hours) cannot use _exec's synchronous -WAIT.
# Instead we submit a jobcontrol-aware driver WITHOUT -WAIT: it registers the
# job with the local job SERVER, prints "JobId: <uuid>", and returns in seconds.
# job_status / job_wait then read that job cross-process via schrodinger.job.
# jobcontrol.Job(jobid) (proven: status is readable from a fresh interpreter).
_JOBID_RE = re.compile(r"JobId:\s*(\S+)")


def _jsc(action: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a `jsc local-server-<action>` command (status|start|stop)."""
    return _exec([_driver("jsc"), f"local-server-{action}"], timeout=timeout)


def _ensure_job_server() -> dict:
    """Idempotently ensure the local job server is up (async submit REQUIRES it;
    without it every submission fails with 'requires a locally running job server')."""
    try:
        p = _jsc("status", timeout=60)
        if "RUNNING" in (p.stdout + p.stderr).upper():
            return {"job_server": "running"}
        s = _jsc("start", timeout=120)
        blob = (s.stdout + s.stderr)
        up = ("available" in blob.lower()) or ("started" in blob.lower())
        return {"job_server": "started" if up else "start_failed", "detail": blob[-400:]}
    except Exception as e:  # never let server management crash a tool
        return {"job_server": "error", "detail": repr(e)}


def _submit_async(argv, cwd=None, timeout=300, env=None, total=None) -> dict:
    """Ensure the job server, run a jobcontrol driver WITHOUT -WAIT, parse its JobId.
    The launcher returns in seconds; the compute runs detached under the job server.

    `env`: an OPTIONAL, SERVER-built dict overlaid on the child environment (same
    _ENV_OVERLAY_ALLOW semantics as _exec) - e.g. {"CUDA_VISIBLE_DEVICES": "2"} to pin one
    GPU per ligand for the multi-GPU pool. env=None keeps the prior behavior exactly.
    `total`: an OPTIONAL progress denominator; when None it is auto-derived per driver.

    After a JobId is parsed, best-effort writes taskwatch's progress.json heartbeat into the
    run dir and auto-registers the run in taskwatch's registry (fail-open: a monitor error
    never breaks the submission)."""
    srv = _ensure_job_server()
    try:
        p = _exec(argv, timeout=timeout, cwd=cwd, env=env)
    except subprocess.TimeoutExpired:
        return {"error": f"submission did not return within {timeout}s", "job_server": srv}
    blob = (p.stdout or "") + "\n" + (p.stderr or "")
    m = _JOBID_RE.search(blob)
    if not m:
        return {"error": "no JobId in launcher output - submission likely failed",
                "job_server": srv, "returncode": p.returncode,
                "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    res = {"jobid": m.group(1), "job_server": srv, "returncode": p.returncode,
           "stdout_tail": p.stdout[-600:]}
    # --- taskwatch heartbeat + auto-register (best-effort; never fails the submit) ---
    try:
        driver = os.path.splitext(os.path.basename(argv[0]))[0] if argv else ""
        if driver == "run":
            # A `run`-launched tool (e.g. bpmd: `run -FROM psp binding_pose_metadynamics.py ...`)
            # has the launcher as argv[0], so derive the real driver from the first positional
            # script/exe - skipping flags like `-FROM` and their values like `psp`.
            for _a in argv[1:]:
                _s = str(_a)
                if not _s.startswith("-") and _s.lower().endswith((".py", ".exe")):
                    driver = os.path.splitext(os.path.basename(_s))[0]
                    break
        derived = _derive_total(driver, argv, cwd) if total is None else total
        res["progress"] = _emit_progress(cwd or ".", driver, derived,
                                          log_path=_predict_log(driver, argv, cwd))
    except Exception:
        pass
    return res


# ---------- structure / cheminformatics (license-token-free) ----------

@mcp.tool()
def schrodinger_version() -> str:
    """Schrodinger suite version. Reads `$SCHRODINGER/version.txt` (instant, no
    subprocess); falls back to `run -v` (verbose env dump) only if the file is
    missing. `run -v` is NOT a version command (returns rc 1), so prefer the file."""
    vt = os.path.join(SCHRODINGER, "version.txt")
    try:
        if os.path.exists(vt):
            with open(vt, encoding="utf-8", errors="replace") as fh:
                txt = fh.read().strip()
            if txt:
                return txt
    except Exception:
        pass
    try:
        p = _exec([_run(), "-v"], timeout=30)
        return (p.stdout or p.stderr).strip()
    except Exception as e:
        return f"ERROR: {e!r}  (SCHRODINGER={SCHRODINGER})"


@mcp.tool()
def backend_info() -> dict:
    """Schrodinger build + bundled RDKit version + install path visible to the backend."""
    return _helper("info", {})


@mcp.tool()
def smiles_to_3d(smiles: str, out_path: str, title: str = "") -> dict:
    """SMILES -> 3D structure file (.sdf or .mae). 3D via RDKit ETKDGv3 + MMFF.
    Extension picks the format (.mae for Glide/Prime downstream, .sdf for portability)."""
    out_path = _safe_path(out_path)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    return _helper("smiles_to_3d", {"smiles": smiles, "out_path": out_path, "title": title})


@mcp.tool()
def molecule_properties(smiles: str) -> dict:
    """Drug-likeness panel for a SMILES: formula, MW, logP, HBD/HBA, TPSA, rot-bonds, rings, QED, Lipinski."""
    return _helper("properties", {"smiles": smiles})


@mcp.tool()
def convert_structure(src: str, dst: str) -> dict:
    """Convert a structure file between formats (.sdf <-> .mae <-> .pdb) via schrodinger.structure."""
    src = _safe_path(src, must_exist=True)
    dst = _safe_path(dst)
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    return _helper("convert", {"src": src, "dst": dst})


@mcp.tool()
def run_schrodinger_python(code: str, timeout_s: int = 300) -> dict:
    """Escape hatch: run a Python snippet inside the Schrodinger interpreter (has `schrodinger`+`rdkit`).
    Powerful (arbitrary local code) - this server is intended for local single-user use only."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=HERE) as f:
        f.write(code)
        tmp = f.name
    try:
        p = _exec([_run(), "python3", tmp], timeout=timeout_s)
        return {"returncode": p.returncode, "stdout": p.stdout[-8000:], "stderr": p.stderr[-4000:]}
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ---------- product drivers (consume license tokens; synchronous -WAIT) ----------

@mcp.tool()
def ligprep(input_file: str, output_mae: str, timeout_s: int = 1200) -> dict:
    """LigPrep: prepared 3D ligand states (ionization/tautomers/stereo) from .smi/.sdf/.mae -> MAE."""
    try:
        input_file = _safe_path(input_file, must_exist=True)
        output_mae = _safe_path(output_mae)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    low = input_file.lower()
    inflag = "-ismi" if low.endswith(".smi") else ("-isd" if low.endswith((".sdf", ".sd")) else "-imae")
    # LigPrep requires -omae to resolve UNDER the cwd; an absolute path (esp. with an 8.3
    # short name like PREKZU~1) fails its "not under the current working directory" check.
    # Run in the output dir and pass just the basename.
    wd = os.path.dirname(output_mae) or "."
    os.makedirs(wd, exist_ok=True)
    argv = [_driver("ligprep"), inflag, input_file, "-omae", os.path.basename(output_mae), "-WAIT"]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    return {"returncode": p.returncode, "output": output_mae if os.path.exists(output_mae) else None,
            "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}


@mcp.tool()
def qikprop_admet(structure_file: str, timeout_s: int = 900) -> dict:
    """QikProp ADMET/physchem prediction on a 3D structure (.mae/.sdf). Returns the result CSV path + head."""
    try:
        structure_file = _safe_path(structure_file, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    wd = os.path.dirname(structure_file) or "."
    base = os.path.splitext(os.path.basename(structure_file))[0]
    argv = [_driver("qikprop"), "-WAIT", structure_file]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    csv = os.path.join(wd, base + ".CSV")
    res = {"returncode": p.returncode, "csv": csv if os.path.exists(csv) else None,
           "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    if os.path.exists(csv):
        with open(csv) as fh:
            res["csv_head"] = "".join(fh.readlines()[:3])
    return res


@mcp.tool()
def glide_dock(grid_file: str, ligands_mae: str, precision: str = "SP", timeout_s: int = 3600) -> dict:
    """Glide docking of prepared ligands into a precomputed grid (.zip). precision = HTVS|SP|XP.
    Returns the *_pv.maegz pose-viewer path. Consumes a Glide license token."""
    try:
        grid_file = _safe_path(grid_file, must_exist=True)
        ligands_mae = _safe_path(ligands_mae, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if precision not in ("HTVS", "SP", "XP"):
        return {"error": "precision must be HTVS, SP, or XP"}
    wd = os.path.dirname(ligands_mae) or "."
    job = "glide_dock_job"
    infile = os.path.join(wd, job + ".in")
    with open(infile, "w") as fh:
        # POSE_OUTTYPE poseviewer => writes <job>_pv.maegz (receptor + poses), the input prime_mmgbsa needs.
        fh.write(f"GRIDFILE {grid_file}\nLIGANDFILE {ligands_mae}\nPRECISION {precision}\nPOSE_OUTTYPE poseviewer\n")
    argv = [_driver("glide"), infile, "-WAIT", "-OVERWRITE"]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    pv = os.path.join(wd, job + "_pv.maegz")
    raw = os.path.join(wd, job + "_raw.maegz")
    poses = pv if os.path.exists(pv) else (raw if os.path.exists(raw) else None)
    res = {"returncode": p.returncode, "poses": poses,
           "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    if poses is None:
        # job ran but no pose-viewer (e.g. "NO GOOD POSES FOUND") — surface the per-ligand status
        skip = os.path.join(wd, job + "_skip.csv")
        if os.path.exists(skip):
            with open(skip) as fh:
                res["docking_status"] = "".join(fh.readlines()[:4])[-600:]
    return res


@mcp.tool()
def prepwizard(input_file: str, output_mae: str, ph: float = 7.0, fill_sidechains: bool = True,
               timeout_s: int = 1800) -> dict:
    """Protein Preparation Wizard: clean a raw receptor (.pdb/.mae) for docking - add hydrogens,
    assign bond orders, optionally fill missing side chains, and set protonation at `ph` (PROPKA).
    Output is a prepared .mae ready for glide_grid. (prepwizard lives in $SCHRODINGER/utilities.)"""
    try:
        input_file = _safe_path(input_file, must_exist=True)
        output_mae = _safe_path(output_mae)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    argv = [_driver("prepwizard"), "-WAIT"]
    if fill_sidechains:
        argv.append("-fillsidechains")
    argv += ["-propka_pH", str(float(ph)), input_file, output_mae]
    os.makedirs(os.path.dirname(output_mae) or ".", exist_ok=True)
    try:
        p = _exec(argv, timeout=timeout_s, cwd=os.path.dirname(output_mae) or ".")
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    return {"returncode": p.returncode, "output": output_mae if os.path.exists(output_mae) else None,
            "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}


@mcp.tool()
def glide_grid(receptor_mae: str, out_grid_zip: str, center: str = "", ligand_molnum: int = 0,
               inner_box: int = 10, outer_box: int = 30, timeout_s: int = 1800) -> dict:
    """Generate a Glide docking grid (.zip) from a prepared receptor (.mae/.maegz) - the step
    glide_dock needs and that no other tool produced. Define the box EITHER with explicit
    `center="x,y,z"` coordinates OR with `ligand_molnum` (1-based molecule number of a
    co-crystallized ligand already in the receptor file). Consumes a Glide token."""
    try:
        receptor_mae = _safe_path(receptor_mae, must_exist=True)
        out_grid_zip = _safe_path(out_grid_zip)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not center and not ligand_molnum:
        return {"error": "provide either center='x,y,z' or ligand_molnum (1-based) to define the grid box"}
    if center and not all(c in "0123456789.,-+eE " for c in center):
        return {"error": f"center must be numeric 'x,y,z', got {center!r}"}
    wd = os.path.dirname(out_grid_zip) or "."
    os.makedirs(wd, exist_ok=True)
    job = os.path.splitext(os.path.basename(out_grid_zip))[0] + "_gridgen"
    infile = os.path.join(wd, job + ".in")
    lines = [f"GRIDFILE {out_grid_zip}", f"RECEP_FILE {receptor_mae}"]
    if center:
        lines.append(f"GRID_CENTER {center.replace(' ', '')}")
    else:
        lines.append(f"LIGAND_MOLECULE {int(ligand_molnum)}")
    lines += [f"INNERBOX {inner_box}, {inner_box}, {inner_box}",
              f"OUTERBOX {outer_box}, {outer_box}, {outer_box}"]
    with open(infile, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    try:
        p = _exec([_driver("glide"), infile, "-WAIT", "-OVERWRITE"], timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    return {"returncode": p.returncode, "grid": out_grid_zip if os.path.exists(out_grid_zip) else None,
            "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}


@mcp.tool()
def prime_mmgbsa(pose_viewer: str, timeout_s: int = 3600) -> dict:
    """Prime MM-GBSA: binding free-energy (dG bind) rescoring of docked poses - far more reliable
    than the raw Glide score. Input is a Glide pose-viewer file (the *_pv.maegz from glide_dock).
    Returns the result CSV (with r_psp_MMGBSA_dG_Bind) + the -out.maegz. Consumes a Prime token."""
    try:
        pose_viewer = _safe_path(pose_viewer, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    wd = os.path.dirname(pose_viewer) or "."
    base = os.path.splitext(os.path.basename(pose_viewer))[0]
    # Prime derives the jobname by dropping a trailing _pv: <job>_pv.maegz -> <job>-out.csv
    job = base[:-3] if base.endswith("_pv") else base
    try:
        p = _exec([_driver("prime_mmgbsa"), pose_viewer, "-WAIT"], timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    csv = os.path.join(wd, job + "-out.csv")
    out_mae = os.path.join(wd, job + "-out.maegz")
    res = {"returncode": p.returncode,
           "csv": csv if os.path.exists(csv) else None,
           "out_maegz": out_mae if os.path.exists(out_mae) else None,
           "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    if os.path.exists(csv):
        with open(csv) as fh:
            res["csv_head"] = "".join(fh.readlines()[:3])
    return res


# ---------- structure acquisition (no license token) ----------

@mcp.tool()
def pdb_fetch(pdb_id: str, out_dir: str, fmt: str = "pdb") -> dict:
    """Download a receptor structure from the RCSB PDB by 4-char ID (no Schrodinger token).
    fmt = 'pdb' | 'cif'. GABA-B cryo-EM structures of interest: 7EB2, 7C7Q, 6UO8, 7CA3, 7CA5.
    Pure-Python urllib fetch. Returns {pdb_path, size_bytes, url}."""
    pid = pdb_id.strip().lower()
    if not (len(pid) == 4 and pid.isalnum()):
        return {"error": f"invalid PDB id: {pdb_id!r} (expect 4 alphanumerics)"}
    if fmt not in ("pdb", "cif"):
        return {"error": "fmt must be 'pdb' or 'cif'"}
    try:
        out_dir = _safe_path(out_dir)
    except ValueError as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, f"{pid}.{fmt}")
    url = f"https://files.rcsb.org/download/{pid}.{fmt}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as fh:
            fh.write(r.read())
    except Exception as e:
        return {"error": f"download failed: {e!r}", "url": url}
    return {"pdb_path": dest, "size_bytes": os.path.getsize(dest), "url": url}


# ---------- ADMET result parsing (no license token; closes the QikProp loop) ----------

@mcp.tool()
def qikprop_parse_results(csv_path: str, properties: list = None) -> dict:
    """Parse a QikProp .CSV into structured per-molecule ADMET rows (pure file read, no token).
    Pass `properties` to subset columns by case-insensitive substring (e.g.
    ['QPlogBB','QPPMDCK','CNS','QPlogPo/w','QPlogHERG']). Returns {columns, n_molecules, molecules}."""
    try:
        csv_path = _safe_path(csv_path, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    with open(csv_path, newline="") as fh:
        rows = list(_csv.DictReader(fh))
    if not rows:
        return {"columns": [], "n_molecules": 0, "molecules": []}
    cols = list(rows[0].keys())
    if properties:
        idcols = [c for c in cols if c.lower() in ("molecule", "title", "name")]
        keep = idcols + [c for c in cols if c not in idcols
                         and any(p.lower() in c.lower() for p in properties)]
        rows = [{k: r.get(k) for k in keep} for r in rows]
        cols = keep
    return {"columns": cols, "n_molecules": len(rows), "molecules": rows[:200]}


# ---------- pocket detection (synchronous -WAIT; consumes a SiteMap token) ----------

@mcp.tool()
def sitemap(receptor_mae: str, out_dir: str, job_name: str = "sitemap_job",
            max_sites: int = 5, sitescore_min: float = 0.80, timeout_s: int = 1800) -> dict:
    """SiteMap: detect & rank druggable pockets on a prepared receptor (.mae) - locates the
    orthosteric + any allosteric/cryptic sites before grid generation. Returns the *_out.maegz
    (parse SiteScore/Dscore/volume via run_schrodinger_python). NOTE: untested against a live
    run; mirrors the proven synchronous -WAIT driver pattern - verify the first invocation."""
    try:
        receptor_mae = _safe_path(receptor_mae, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not job_name.replace("_", "").replace("-", "").isalnum():
        return {"error": f"invalid job_name: {job_name!r}"}
    os.makedirs(out_dir, exist_ok=True)
    argv = [_driver("sitemap"), "-WAIT", "-prot", receptor_mae,
            "-maxsites", str(int(max_sites)), "-sitescore_cutoff", str(float(sitescore_min)),
            "-j", job_name]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    out_mae = os.path.join(out_dir, job_name + "_out.maegz")
    return {"returncode": p.returncode, "out_maegz": out_mae if os.path.exists(out_mae) else None,
            "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}


# ---------- QM pKa (synchronous -WAIT; consumes a JAGUAR token) ----------

@mcp.tool()
def jaguar_pka(structure_file: str, out_dir: str, timeout_s: int = 7200) -> dict:
    """Jaguar QM pKa prediction (zwitterion-aware) for a small molecule (.mae/.sdf). Far more
    accurate than PROPKA for phenibut's COOH (~4.1) / NH3+ (~9.3) groups - the protonation state
    is load-bearing for the GABA-B binding mode. Builds a single Jaguar pKa input
    (ipka_prot_deprot=both + auto-detected ipkasites via mm.mmjag_pka_find_sites) then runs
    `jaguar run <pka.in> -NOJOBID` - the session-proven bypass of the `jaguar pka` driver's
    job-control staging bug (-NOJOBID is synchronous, in-process, single-job). Parses pKa from the
    .out. Consumes a Jaguar token. NOTE: the ipka keyword set, -NOJOBID single-job behaviour and
    the find_sites API are verified vs the installed jaguar-v13.2 source; confidence=low remains on
    whether ipka_max_conf=1 keeps a multi-site run single-process, so confirm the first live run."""
    try:
        structure_file = _safe_path(structure_file, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)
    # job basename flows into argv as a POSITIONAL arg -> _jobname sanitizes to [A-Za-z0-9_-]
    # and lstrip('-') guarantees it can never be read as a flag.
    job = _jobname(structure_file, "_pka").lstrip("-") or "job_pka"
    in_file = os.path.join(out_dir, job + ".in")
    built = _helper("jaguar_pka_in",
                    {"structure_file": structure_file, "out_in": in_file}, timeout=600)
    if not isinstance(built, dict) or "error" in built or not os.path.exists(in_file):
        return {"error": "failed to build Jaguar pKa input", "detail": built}
    argv = [_driver("jaguar"), "run", os.path.basename(in_file), "-NOJOBID"]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s", "sites": built.get("sites")}
    out = os.path.join(out_dir, job + ".out")
    res = {"returncode": p.returncode, "pka_out": out if os.path.exists(out) else None,
           "pka_in": in_file, "sites": built.get("sites"),
           "stdout_tail": p.stdout[-2000:], "stderr_tail": p.stderr[-1500:]}
    if os.path.exists(out):
        try:
            with open(out, encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
            vals = re.findall(r"pKa\D{0,40}(-?\d+\.\d+)", txt)
            res["pka_values"] = [float(v) for v in vals[-8:]]
        except OSError:
            pass
    return res


# ---------- protonation enumeration (synchronous -WAIT; consumes an Epik token) ----------

@mcp.tool()
def epik_enumerate(input_mae: str, output_mae: str, ph: float = 7.4, ph_tolerance: float = 2.0,
                   timeout_s: int = 1800) -> dict:
    """Epik: enumerate protonation/tautomer states at a target pH (more rigorous than LigPrep's
    built-in call) - for phenibut/analog zwitterion species at physiological or local (lysosomal,
    BBB-transporter) pH. Returns the output MAE. NOTE: untested against a live run; verify first use."""
    try:
        input_mae = _safe_path(input_mae, must_exist=True)
        output_mae = _safe_path(output_mae)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    wd = os.path.dirname(output_mae) or "."
    os.makedirs(wd, exist_ok=True)
    argv = [_driver("epik"), "-imae", input_mae, "-omae", os.path.basename(output_mae),
            "-ph", str(float(ph)), "-pht", str(float(ph_tolerance)), "-WAIT"]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    return {"returncode": p.returncode, "output": output_mae if os.path.exists(output_mae) else None,
            "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}


# ---------- publication figures (no Schrodinger token; bundled Incentive PyMOL) ----------

@mcp.tool()
def pymol_render(input_files: list, output_png: str, width: int = 1600, height: int = 1200,
                 dpi: int = 300, style: str = "publication", highlight_selection: str = "",
                 pml_commands: str = "", timeout_s: int = 180) -> dict:
    """Render a ray-traced PNG from structure files (.mae/.maegz/.pdb/.sdf) via headless PyMOL.
    Uses the bundled Schrodinger-Incentive PyMOL (reads .mae natively), closing the only gap in
    the automated pipeline - figure generation. style = publication|cartoon|surface|sticks.
    `highlight_selection` is a PyMOL selection shown as wheat sticks; `pml_commands` is an escape
    hatch. Override the binary with $PYMOL_EXE. Returns {output_png, size_bytes}."""
    if not isinstance(input_files, list) or not input_files:
        return {"error": "input_files must be a non-empty list of structure paths"}
    if style not in ("publication", "cartoon", "surface", "sticks"):
        return {"error": "style must be publication|cartoon|surface|sticks"}
    try:
        ins = [_safe_path(f, must_exist=True) for f in input_files]
        output_png = _safe_path(output_png)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(os.path.dirname(output_png) or ".", exist_ok=True)
    for inj in (highlight_selection, pml_commands):
        if any(c in inj for c in "\r\n\x00"):
            return {"error": "unsafe newline/null in highlight_selection or pml_commands"}
    pml = [f"load {f}, obj{i}" for i, f in enumerate(ins)] + ["hide everything"]
    if style == "surface":
        pml += ["show surface, polymer", "show sticks, hetatm and not solvent"]
    elif style == "sticks":
        pml += ["show sticks, not solvent"]
    elif style == "cartoon":
        pml += ["show cartoon, polymer", "show sticks, hetatm and not solvent"]
    else:  # publication
        pml += ["show cartoon, polymer", "show sticks, hetatm and not solvent", "util.cbag hetatm"]
    if highlight_selection:
        pml += [f"select hl, {highlight_selection}", "show sticks, hl", "color wheat, hl"]
    pml += ["bg_color white", "set ray_shadows, 0", "set ray_opaque_background, on",
            "set antialias, 2", f"viewport {int(width)}, {int(height)}"]
    if pml_commands:
        pml.append(pml_commands)
    pml += [f"ray {int(width)}, {int(height)}",
            f"png {output_png}, width={int(width)}, height={int(height)}, dpi={int(dpi)}, ray=0",
            "quit"]
    with tempfile.NamedTemporaryFile("w", suffix=".pml", delete=False, dir=HERE) as f:
        f.write("\n".join(pml))
        script = f.name
    pymol_exe = os.environ.get("PYMOL_EXE", r"D:\Program Files\PyMOL\Scripts\pymol.exe")
    try:
        p = _exec([pymol_exe, "-cq", script], timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass
    ok = os.path.exists(output_png)
    return {"returncode": p.returncode, "output_png": output_png if ok else None,
            "size_bytes": os.path.getsize(output_png) if ok else 0,
            "stdout_tail": p.stdout[-800:], "stderr_tail": p.stderr[-800:]}


# ---------- Desmond molecular dynamics (P1 headline) ----------
# The shipped Desmond standard NPT relaxation protocol, embedded verbatim
# (from $SCHRODINGER/mmshare-*/data/desmond/desmond_npt_relax.msj). Reproduced
# exactly so it stays valid without depending on the mmshare version in the path.
_DESMOND_RELAX_MSJ = '''task {
  task = "desmond:auto"
  set_family = {
    desmond = {
      checkpt.write_last_step = no
    }
  }
}

simulate {
  title       = "Brownian Dynamics NVT, T = 10 K, small timesteps, and restraints on solute heavy atoms, 100ps"
  annealing   = off
  time        = 100
  timestep    = [0.001 0.001 0.003 ]
  temperature = 10.0
  ensemble = {
    class  = "NVT"
    method = "Brownie"
    brownie = {
      delta_max = 0.1
    }
  }
  polarization_restraints = full
  restraints.new = [
    {
      name            = posre_harm
      atoms           = solute_heavy_atom
      force_constants = 50.0
    }
  ]
  eneseq.interval = 0.3
}

simulate {
  title                   = "NVT, T = 10 K, small timesteps, and restraints on solute heavy atoms, 12ps"
  annealing               = off
  time                    = 12
  timestep                = [0.001 0.001 0.003]
  temperature             = 10.0
  polarization_restraints = full
  restraints.new = [
    {
      name            = posre_harm
      atoms           = solute_heavy_atom
      force_constants = 50.0
    }
  ]
  ensemble = {
    class          = NVT
    method         = Langevin
    thermostat.tau = 0.1
  }
  randomize_velocity.interval = 1.0
  eneseq.interval             = 0.3
  trajectory.center           = []
}

simulate {
  title                   = "NPT, T = 10 K, and restraints on solute heavy atoms, 12ps"
  annealing               = off
  time                    = 12
  temperature             = 10.0
  polarization_restraints = full
  restraints.existing     = retain
  ensemble = {
    class          = NPT
    method         = Langevin
    thermostat.tau = 0.1
    barostat.tau   = 50.0
  }
  randomize_velocity.interval = 1.0
  eneseq.interval             = 0.3
  trajectory.center           = []
}

simulate {
  title                   = "NPT and restraints on solute heavy atoms, 12ps"
  effect_if               = [["@*.*.annealing"] 'annealing = off temperature = "@*.*.temperature[0][0]"']
  time                    = 12
  polarization_restraints = full
  restraints.existing     = retain
  ensemble = {
    class          = NPT
    method         = Langevin
    thermostat.tau = 0.1
    barostat.tau   = 50.0
  }
  randomize_velocity.interval = 1.0
  eneseq.interval             = 0.3
  trajectory.center           = []
}

simulate {
  title     = "NPT and no restraints, 24ps"
  effect_if = [["@*.*.annealing"] 'annealing = off temperature = "@*.*.temperature[0][0]"']
  time      = 24
  ensemble = {
    class          = NPT
    method         = Langevin
    thermostat.tau = 0.1
    barostat.tau   = 2.0
  }
  polarization_restraints = decay
  eneseq.interval         = 0.3
  trajectory.center       = solute
}
'''

_DESMOND_TASK_ONLY = 'task {\n  task = "desmond:auto"\n}\n'


def _jobname(path: str, suffix: str = "") -> str:
    """Derive a safe multisim -JOBNAME from an output path basename."""
    base = os.path.splitext(os.path.basename(path))[0]
    base = re.sub(r"[^A-Za-z0-9_-]", "_", base) or "job"
    return (base + suffix)[:60]


def _production_stage(time_ps: float, ensemble: str, temperature_k: float,
                      pressure_bar: float, timestep_fs: float, traj_interval_ps: float) -> str:
    dt = round(timestep_fs / 1000.0, 6)
    ts = f"[{dt} {dt} {round(dt * 3, 6)}]"
    lines = ['simulate {', '  title       = "Production MD"',
             f'  time        = {time_ps}', f'  timestep    = {ts}',
             f'  temperature = {temperature_k}', '  ensemble = {',
             f'    class          = {ensemble}', '    method         = MTK',
             '    thermostat.tau = 1.0']
    if ensemble == "NPT":
        lines.append('    barostat.tau   = 2.0')
    lines.append('  }')
    if ensemble == "NPT" and abs(pressure_bar - 1.01325) > 1e-6:
        lines.append(f'  pressure = {pressure_bar}')
    lines += [f'  trajectory.interval = {traj_interval_ps}',
              f'  eneseq.interval     = {max(1.0, traj_interval_ps / 5.0)}', '}']
    return "\n".join(lines) + "\n"


@mcp.tool()
def desmond_setup(input_structure: str, out_cms: str, box_shape: str = "orthorhombic",
                  buffer_width: float = 10.0, solvent: str = "SPC", neutralize: bool = True,
                  forcefield: str = "OPLS4", timeout_s: int = 3600) -> dict:
    """Desmond system builder: solvate + neutralize a prepared structure (.mae/.pdb) into a
    Desmond `-out.cms` ready for desmond_md. Runs `multisim` build_geometry + assign_forcefield
    synchronously (minutes). box_shape=orthorhombic|cubic|triclinic|...; solvent=SPC|TIP3P|TIP4P|
    TIP4PEW|TIP5P|SPCE; forcefield=OPLS4|OPLS_2005. buffer_width is the solute->box-edge padding (A).
    Requires the local job server (auto-started). Returns {out_cms, jobid_free returncode}."""
    try:
        input_structure = _safe_path(input_structure, must_exist=True)
        out_cms = _safe_path(out_cms)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if box_shape not in ("orthorhombic", "cubic", "triclinic", "dodecahedron_hexagon",
                         "cube", "truncated_octahedron"):
        return {"error": f"unsupported box_shape: {box_shape!r}"}
    wd = os.path.dirname(out_cms) or "."
    os.makedirs(wd, exist_ok=True)
    job = _jobname(out_cms, "_setup")
    build = ['task {', '  task = "desmond:auto"', '}', '', 'build_geometry {',
             f'  box_shape         = {box_shape}', f'  buffer_width      = {float(buffer_width)}',
             '  rezero_system     = yes', f'  neutralize_system = {"yes" if neutralize else "no"}',
             f'  solvent           = {solvent}', '}', '', 'assign_forcefield {',
             f'  forcefield = {forcefield}', '}', '']
    msj = os.path.join(wd, job + ".msj")
    with open(msj, "w") as fh:
        fh.write("\n".join(build))
    srv = _ensure_job_server()
    argv = [_driver("multisim"), "-JOBNAME", job, "-m", os.path.basename(msj),
            "-o", os.path.basename(out_cms), input_structure, "-HOST", "localhost", "-WAIT"]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s", "job_server": srv}
    out = out_cms if os.path.exists(out_cms) else (
        os.path.join(wd, job + "-out.cms") if os.path.exists(os.path.join(wd, job + "-out.cms")) else None)
    return {"returncode": p.returncode, "out_cms": out, "msj": msj, "job_server": srv,
            "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}


@mcp.tool()
def desmond_md(system_cms: str, out_cms: str = "", time_ns: float = 10.0, ensemble: str = "NPT",
               temperature_K: float = 300.0, pressure_bar: float = 1.01325, timestep_fs: float = 2.0,
               traj_interval_ps: float = 50.0, relax: bool = True, timeout_s: int = 300) -> dict:
    """Desmond production MD on a solvated `-out.cms` (from desmond_setup). ASYNC: submits via
    the P0 job-control layer (no -WAIT) and returns a {jobid} - poll with job_status / job_wait.
    Prepends the shipped standard NPT relaxation protocol when relax=True. Parameterize time_ns,
    ensemble (NPT|NVT), temperature_K, pressure_bar (NPT), timestep_fs, traj_interval_ps (frame
    write interval). GPU-bound: practical on the RTX 4050 for modest systems. `out_cms` defaults
    to <system>_md-out.cms. NOTE: msj/argv verified + validated on a tiny system; scale runtime is
    user-dependent."""
    try:
        system_cms = _safe_path(system_cms, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if ensemble not in ("NPT", "NVT"):
        return {"error": "ensemble must be NPT or NVT"}
    wd = os.path.dirname(system_cms) or "."
    if not out_cms:
        out_cms = os.path.join(wd, _jobname(system_cms) + "_md-out.cms")
    try:
        out_cms = _safe_path(out_cms)
    except ValueError as e:
        return {"error": str(e)}
    job = _jobname(out_cms)
    head = _DESMOND_RELAX_MSJ if relax else _DESMOND_TASK_ONLY
    prod = _production_stage(float(time_ns) * 1000.0, ensemble, float(temperature_K),
                             float(pressure_bar), float(timestep_fs), float(traj_interval_ps))
    msj = os.path.join(wd, job + "_prod.msj")
    with open(msj, "w") as fh:
        fh.write(head + "\n" + prod)
    argv = [_driver("multisim"), "-JOBNAME", job, "-m", os.path.basename(msj),
            "-o", os.path.basename(out_cms), system_cms, "-HOST", "localhost"]
    res = _submit_async(argv, cwd=wd, timeout=timeout_s)
    res["msj"] = msj
    res["expected_out_cms"] = out_cms
    res["expected_trajectory"] = os.path.join(wd, job + "_trj")
    return res


@mcp.tool()
def desmond_trajectory_analysis(cms_file: str, lig_asl: str = "", fit_asl: str = "",
                                stride: int = 1, timeout_s: int = 900) -> dict:
    """Analyze a completed Desmond MD trajectory (its `-out.cms`; the sibling `_trj` is auto-found).
    Uses schrodinger.application.desmond.packages.analysis to compute protein C-alpha RMSD (per-frame
    series + mean/min/max/last), C-alpha RMSF (per-residue), radius of gyration, and - if `lig_asl`
    is given - ligand RMSD after protein fit. `fit_asl` overrides the alignment selection
    (default: protein CA). `stride` subsamples frames. NOTE: needs a completed MD run to exercise."""
    try:
        cms_file = _safe_path(cms_file, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    args = {"cms_file": cms_file, "stride": max(1, int(stride))}
    if lig_asl:
        args["lig_asl"] = lig_asl
    if fit_asl:
        args["fit_asl"] = fit_asl
    return _helper("trj_analyze", args, timeout=timeout_s)


@mcp.tool()
def thermal_mmgbsa(cms_file: str, job_name: str = "", lig_asl: str = "", start_frame: int = 0,
                   end_frame: int = -1, step_size: int = 1, njobs: int = 1,
                   timeout_s: int = 300) -> dict:
    """Thermal MM-GBSA: per-frame Prime MM-GBSA binding energies over a Desmond MD trajectory
    (a more converged dG than single-pose Prime). Wraps `$SCHRODINGER/run thermal_mmgbsa.py
    <-out.cms> -j <name> -start_frame N -end_frame M -step_size K -HOST localhost:NJOBS -NJOBS N`.
    ASYNC (Prime subjobs, long): submitted under Job Control -> returns {jobid}; poll job_status.
    `end_frame=-1` means to the last frame. NOTE: argv-verified; needs a real MD trajectory to run."""
    try:
        cms_file = _safe_path(cms_file, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    wd = os.path.dirname(cms_file) or "."
    job = _jobname(job_name or (os.path.basename(cms_file) + "_tmmgbsa"))
    argv = [_run(), "thermal_mmgbsa.py", cms_file, "-j", job,
            "-start_frame", str(int(start_frame)), "-step_size", str(max(1, int(step_size))),
            "-HOST", f"localhost:{max(1, int(njobs))}", "-NJOBS", str(max(1, int(njobs)))]
    if int(end_frame) >= 0:
        argv += ["-end_frame", str(int(end_frame))]
    if lig_asl:
        if any(c in lig_asl for c in "\r\n\x00"):
            return {"error": "unsafe lig_asl (control char)"}
        if lig_asl.strip().startswith("-"):
            return {"error": "unsafe lig_asl (leading '-' could be parsed as a flag)"}
        argv += ["-lig_asl", lig_asl]
    srv = _ensure_job_server()
    res = _helper("launch", {"argv": argv, "launch_dir": wd}, timeout=180)
    res["job_server"] = srv
    res["expected_csv"] = os.path.join(wd, job + "-out.csv")
    return res


# ---------- async job-control MCP tools (P0 enabler) ----------

@mcp.tool()
def job_server_control(action: str = "status") -> dict:
    """Control the local Schrodinger job server that async jobs (MD/FEP/WaterMap) require.
    action = 'status' | 'start' | 'stop'. The async submit tools auto-start it, but this
    lets you check/stop it explicitly. Wraps `$SCHRODINGER/jsc local-server-<action>`."""
    if action not in ("status", "start", "stop"):
        return {"error": "action must be status|start|stop"}
    try:
        p = _jsc(action)
    except subprocess.TimeoutExpired:
        return {"error": "jsc timed out"}
    return {"action": action, "returncode": p.returncode,
            "stdout_tail": p.stdout[-800:], "stderr_tail": p.stderr[-800:]}


@mcp.tool()
def job_status(jobid: str) -> dict:
    """Live status of an async Job Control job by its JobId (from desmond_md/fep_plus/etc.).
    Returns {status, is_complete, succeeded, program, progress, struct_output, output_files, dir}.
    `status` is one of launched/running/completed/died/etc. Read cross-process from the job server."""
    if not isinstance(jobid, str) or not jobid.strip() or jobid.strip().startswith("-"):
        return {"error": f"invalid jobid: {jobid!r}"}
    return _helper("job_status", {"jobid": jobid.strip()}, timeout=120)


@mcp.tool()
def job_wait(jobid: str, timeout_s: int = 600, poll_s: int = 5) -> dict:
    """Block until an async job completes or `timeout_s` elapses, then return its final status.
    For minutes-long jobs. For hours-long MD/FEP, prefer polling job_status periodically instead
    (a long job_wait ties up the client). Returns the job_status fields plus `timed_out`."""
    if not isinstance(jobid, str) or not jobid.strip() or jobid.strip().startswith("-"):
        return {"error": f"invalid jobid: {jobid!r}"}
    timeout_s = max(1, int(timeout_s))
    return _helper("job_wait", {"jobid": jobid.strip(), "timeout": timeout_s, "poll": max(1, int(poll_s))},
                   timeout=timeout_s + 60)


# ---------- cheap CPU workflows (P3: fast, local, high-ROI) ----------

def _canvas_in_flag(path: str) -> str:
    low = path.lower()
    if low.endswith((".smi", ".ismi")):
        return "-ismi"
    if low.endswith((".sdf", ".sd", ".sdfgz")):
        return "-isd"
    if low.endswith(".csv"):
        return "-icsv"
    return "-imae"


@mcp.tool()
def confgen(input_structure: str, num_confs: int = 0, max_confs: int = 0, out_maegz: str = "",
            timeout_s: int = 600) -> dict:
    """ConfGen: generate a 3D conformer ensemble for small molecules (.mae/.sdf/.mol2). Fast, CPU,
    runs locally with -NOJOBID (no job server needed). num_confs (-n target count; 0 = auto by
    quality mode), max_confs (-m cap per input). Writes <job>-out.maegz next to the input.
    Returns {out_maegz, returncode}."""
    try:
        input_structure = _safe_path(input_structure, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    wd = os.path.dirname(input_structure) or "."
    stem = os.path.basename(out_maegz) if out_maegz else (
        os.path.splitext(os.path.basename(input_structure))[0] + "_confgen")
    job = _jobname(re.sub(r"-out$", "", os.path.splitext(stem)[0]))
    argv = [_driver("confgen"), os.path.basename(input_structure), "-j", job, "-NOJOBID"]
    if int(max_confs) > 0:
        argv += ["-m", str(int(max_confs))]
    if int(num_confs) > 0:
        argv += ["-n", str(int(num_confs))]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    out = os.path.join(wd, job + "-out.maegz")
    return {"returncode": p.returncode, "out_maegz": out if os.path.exists(out) else None,
            "stdout_tail": p.stdout[-1000:], "stderr_tail": p.stderr[-1000:]}


@mcp.tool()
def shape_screen(shape_query: str, screen_library: str, out_dir: str = "", flexible: bool = False,
                 max_confs: int = 0, timeout_s: int = 1800) -> dict:
    """Shape screen: rank a library by 3D shape similarity to a query molecule. shape_query &
    screen_library = .mae/.maegz/.sdf. flexible=True generates conformers on the fly (-flex).
    Similarity is written as r_phase_Shape_Sim on <job>_align.maegz. CPU (use shape_screen_gpu on
    the GPU for large libraries). Returns {aligned_maegz, returncode}."""
    try:
        shape_query = _safe_path(shape_query, must_exist=True)
        screen_library = _safe_path(screen_library, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    try:
        wd = _safe_path(out_dir) if out_dir else (os.path.dirname(shape_query) or ".")
    except ValueError as e:
        return {"error": str(e)}
    os.makedirs(wd, exist_ok=True)
    job = "shape_screen_job"
    argv = [_driver("shape_screen"), "-shape", shape_query, "-screen", screen_library,
            "-JOB", job, "-HOST", "localhost", "-WAIT"]
    if flexible:
        argv.append("-flex")
        if int(max_confs) > 0:
            argv += ["-max", str(int(max_confs))]
    srv = _ensure_job_server()
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s", "job_server": srv}
    aligned = os.path.join(wd, job + "_align.maegz")
    return {"returncode": p.returncode, "job_server": srv,
            "aligned_maegz": aligned if os.path.exists(aligned) else None,
            "stdout_tail": p.stdout[-1200:], "stderr_tail": p.stderr[-1200:]}


@mcp.tool()
def canvas_fingerprints(input_structures: str, out_fp: str, fptype: str = "linear",
                        timeout_s: int = 600) -> dict:
    """Canvas 2D fingerprints for a whole library (.mae/.sdf/.smi/.csv) -> binary .fp file.
    fptype = linear|dendritic|radial|maccs|molprint2D|torsion|pairwise|triplet|quartet. Local, CPU.
    Feed the .fp to canvasFPMatrix / canvasSearch for similarity. Returns {out_fp, returncode}."""
    valid = {"linear", "dendritic", "radial", "maccs", "molprint2d", "torsion",
             "pairwise", "triplet", "quartet"}
    if fptype.lower() not in valid:
        return {"error": f"fptype must be one of {sorted(valid)}"}
    try:
        input_structures = _safe_path(input_structures, must_exist=True)
        out_fp = _safe_path(out_fp)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    argv = [_driver("canvasFPGen"), _canvas_in_flag(input_structures), input_structures,
            "-o", out_fp, "-fptype", fptype.lower()]
    os.makedirs(os.path.dirname(out_fp) or ".", exist_ok=True)
    try:
        p = _exec(argv, timeout=timeout_s, cwd=os.path.dirname(out_fp) or ".")
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    return {"returncode": p.returncode, "out_fp": out_fp if os.path.exists(out_fp) else None,
            "stdout_tail": p.stdout[-1000:], "stderr_tail": p.stderr[-1000:]}


@mcp.tool()
def canvas_descriptors(input_structures: str, out_csv: str, timeout_s: int = 600) -> dict:
    """Canvas molecular descriptors: a broad physicochemical/topological panel for a whole library
    (.mae/.sdf/.smi/.csv) -> CSV (-All). Complements molecule_properties (which is single-SMILES).
    Local, CPU. Returns {out_csv, csv_head, returncode}."""
    try:
        input_structures = _safe_path(input_structures, must_exist=True)
        out_csv = _safe_path(out_csv)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    argv = [_driver("canvasMolDescriptors"), _canvas_in_flag(input_structures), input_structures,
            "-All", "-ocsv", out_csv]
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    try:
        p = _exec(argv, timeout=timeout_s, cwd=os.path.dirname(out_csv) or ".")
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    ok = os.path.exists(out_csv)
    res = {"returncode": p.returncode, "out_csv": out_csv if ok else None,
           "stdout_tail": p.stdout[-1000:], "stderr_tail": p.stderr[-1000:]}
    if ok:
        with open(out_csv) as fh:
            res["csv_head"] = "".join(fh.readlines()[:2])
    return res


@mcp.tool()
def phase_pharmacophore(pose_viewer: str, out_dir: str, n_features: int = 7,
                        excluded_volumes: bool = False, feature_defs: str = "",
                        timeout_s: int = 1800) -> dict:
    """Phase e-pharmacophores: build a structure-based pharmacophore hypothesis (.phypo) from a
    Glide XP pose-viewer by mapping XP descriptor energies onto features. `pose_viewer` = a Glide XP
    *_pv.maegz written WITH XP descriptors. n_features caps features (-f); excluded_volumes adds
    receptor-based xvols (-xvol). Wraps $SCHRODINGER/utilities/epharmacophores. Screen the .phypo
    with phase_screen. NOTE: argv-verified; needs a Glide XP descriptor pose-viewer to run."""
    try:
        pose_viewer = _safe_path(pose_viewer, must_exist=True)
        out_dir = _safe_path(out_dir)
        fd = _safe_path(feature_defs, must_exist=True) if feature_defs else ""
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)
    job = "epharm_hypo"
    argv = [_driver("epharmacophores"), "-pv", pose_viewer, "-f", str(int(n_features)), "-j", job]
    if excluded_volumes:
        argv.append("-xvol")
    if fd:
        argv += ["-fd", fd]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    hypo = os.path.join(out_dir, job + ".phypo")
    return {"returncode": p.returncode, "hypothesis": hypo if os.path.exists(hypo) else None,
            "stdout_tail": p.stdout[-1200:], "stderr_tail": p.stderr[-1200:]}


@mcp.tool()
def phase_screen(library: str, hypothesis: str, out_dir: str, flexible: bool = True,
                 max_confs: int = 0, min_sites: int = 0, njobs: int = 1, timeout_s: int = 3600) -> dict:
    """Phase pharmacophore screen: rank a ligand library against a hypothesis (.phypo). library =
    .mae/.sdf/.maegz or a Phase DB. flexible=True samples conformers on the fly (-flex). min_sites
    (-match) = minimum features that must match. Runs under Job Control (auto-starts the server).
    Returns {hits_maegz, returncode}. NOTE: argv-verified; needs a .phypo hypothesis to run."""
    try:
        library = _safe_path(library, must_exist=True)
        hypothesis = _safe_path(hypothesis, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)
    job = "phase_screen_job"
    nj = max(1, int(njobs))
    argv = [_driver("phase_screen"), library, hypothesis, job,
            "-HOST", f"localhost:{nj}", "-NJOBS", str(nj), "-WAIT"]
    if flexible:
        argv.append("-flex")
        if int(max_confs) > 0:
            argv += ["-max", str(int(max_confs))]
    if int(min_sites) > 0:
        argv += ["-match", str(int(min_sites))]
    srv = _ensure_job_server()
    try:
        p = _exec(argv, timeout=timeout_s, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s", "job_server": srv}
    hits = os.path.join(out_dir, job + "-hits.maegz")
    return {"returncode": p.returncode, "job_server": srv,
            "hits_maegz": hits if os.path.exists(hits) else None,
            "stdout_tail": p.stdout[-1200:], "stderr_tail": p.stderr[-1200:]}


# ---------- GPU free-energy (P2: small systems only on 6GB - needs Desmond engine) ----------

@mcp.tool()
def fep_plus(fmp_map: str, out_dir: str = "", subhost_gpus: int = 1, mode: str = "connected",
             maxjob: int = 1, timeout_s: int = 300) -> dict:
    """FEP+ relative binding free energy on a prebuilt FEP map (.fmp) or a multi-ligand pose-viewer
    (.maegz - the fep_plus driver auto-builds the map). ASYNC (GPU, long) via the P0 job-control
    layer -> {jobid}; poll job_status. GPU-scheduling `mode`:
      'connected' (default, VALIDATION-GRADE): runs the WHOLE map as one fep_plus job with
        `-ppj <subhost_gpus> -maxjob <maxjob>`, so cycle-closure + negative-control hold. The proven
        multi-GPU topology is `-ppj N -maxjob 1`; spreading a leg across N GPUs ALSO needs the target
        host's schrodinger.hosts to declare Processors:N + Gpgpu: + env:SCHRODINGER_CUDA_VISIBLE_DEVICES
        (host-side - Desmond only round-robins lambda-windows when that device count is >1; not settable
        through this wrapper's env allowlist).
      'per_edge' (THROUGHPUT-ONLY): the legacy `-SUBHOST localhost:N` style; returns a 'warning'
        because per-edge splitting drops cycle-closure/neg-control -> NOT validation-grade.
    subhost_gpus -> -ppj (GPUs per leg); maxjob -> -maxjob (max simultaneous subjobs; 0=driver default;
    applies to 'connected'). On a 6GB GPU keep maps SMALL. NOTE: also requires the Desmond MD engine,
    NOT installed on this host (see desmond_md) -> argv/submit-verified only here. License: each FEP+
    map consumes Desmond GPU (FEP+) tokens."""
    if mode not in ("connected", "per_edge"):
        return {"error": f"mode must be 'connected' or 'per_edge', got {mode!r}"}
    try:
        fmp_map = _safe_path(fmp_map, must_exist=True)
        wd = _safe_path(out_dir) if out_dir else (os.path.dirname(fmp_map) or ".")
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(wd, exist_ok=True)
    job = _jobname(fmp_map)
    nj = max(1, int(subhost_gpus))
    if mode == "connected":
        argv = [_driver("fep_plus"), fmp_map, "-JOBNAME", job, "-HOST", "localhost",
                "-SUBHOST", "localhost", "-ppj", str(nj), "-maxjob", str(max(0, int(maxjob)))]
    else:  # per_edge - throughput-only, keep the legacy -SUBHOST localhost:N style
        argv = [_driver("fep_plus"), fmp_map, "-JOBNAME", job, "-HOST", "localhost",
                "-SUBHOST", f"localhost:{nj}"]
    res = _submit_async(argv, cwd=wd, timeout=timeout_s)
    res["mode"] = mode
    res["expected_out_fmp"] = os.path.join(wd, job + "_out.fmp")
    if mode == "per_edge":
        res["warning"] = ("per-edge is throughput-only, NOT validation-grade "
                          "(cycle-closure/neg-control fails)")
    return res


@mcp.tool()
def watermap(structure: str, msj_file: str = "", out_cms: str = "", subhost_gpus: int = 1,
             timeout_s: int = 300) -> dict:
    """WaterMap: hydration-site thermodynamics (Desmond MD + water clustering) around a binding
    site - locates high-dG 'unhappy' waters to target. ASYNC -> {jobid}. `structure` = a
    complex/solvated .cms/.mae. `msj_file` = WaterMap protocol msj; defaults to the shipped
    watermap_gpu_template.msj (the site region + simulation time are defined inside it). On a 6GB
    GPU keep the region SMALL. NOTE: requires the Desmond MD engine (NOT installed here) - so this
    is argv/submit-verified only."""
    try:
        structure = _safe_path(structure, must_exist=True)
        out_cms = _safe_path(out_cms) if out_cms else ""
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    wd = (os.path.dirname(out_cms) or ".") if out_cms else (os.path.dirname(structure) or ".")
    os.makedirs(wd, exist_ok=True)
    job = _jobname(out_cms or (os.path.basename(structure) + "_wmap"))
    if msj_file:
        try:
            msj = _safe_path(msj_file, must_exist=True)
        except (ValueError, FileNotFoundError) as e:
            return {"error": str(e)}
    else:  # fall back to the shipped GPU template
        found = glob.glob(os.path.join(SCHRODINGER, "mmshare-*", "data", "desmond",
                                       "watermap_gpu_template.msj"))
        if not found:
            return {"error": "no msj_file given and shipped watermap_gpu_template.msj not found"}
        msj = os.path.join(wd, job + "_wmap.msj")
        shutil.copyfile(found[0], msj)
    nj = max(1, int(subhost_gpus))
    argv = [_driver("watermap"), "-JOBNAME", job, "-m", os.path.basename(msj),
            "-HOST", "localhost", "-SUBHOST", f"localhost:{nj}", structure]
    if out_cms:
        argv += ["-o", os.path.basename(out_cms)]
    res = _submit_async(argv, cwd=wd, timeout=timeout_s)
    res["msj"] = msj
    return res


# ---------- advanced docking (P4: Glide+Prime, no Desmond) ----------

_COVALENT_RXNS = {
    "Michael Addition", "Nucleophilic Addition to a Double Bond",
    "Nucleophilic Addition to a Triple Bond", "Nucleophilic Substitution",
    "Nucleophilic Substitution of a Carbamate", "Boronic Acid Addition", "Epoxide Opening",
    "Imine Condensation", "Phosphonate Addition", "Beta Lactam Addition",
    "Conjugate Addition to Alkene (nitrile activated)",
    "Conjugate Addition to Alkyne (carbonyl activated)",
    "Conjugate Addition to Alkyne (aryl activated)", "Disulfide Formation",
    "Ion Pair to Covalent Bond: Lig(-1)/Rec(+1)", "Ion Pair to Covalent Bond: Lig(+1)/Rec(-1)"}

_IFD_STANDARD_INP = """INPUT_FILE {receptor}

STAGE VDW_SCALING
  BINDING_SITE {site}
  RECEPTOR_SCALING 0.70
  LIGANDS_TO_DOCK self

STAGE PREDICT_FLEXIBILITY
  BINDING_SITE {site}

STAGE INITIAL_DOCKING
  BINDING_SITE {site}
  INNERBOX 10.0
  OUTERBOX auto
  LIGAND_FILE {ligand}
  LIGANDS_TO_DOCK all
  DOCKING_PRECISION {precision}
  DOCKING_POSES_PER_LIG 20

STAGE COMPILE_RESIDUE_LIST
  DISTANCE_CUTOFF 5.0

STAGE PRIME_REFINEMENT
  NUMBER_OF_PASSES 1
  USE_MEMBRANE no

STAGE GLIDE_DOCKING2
  BINDING_SITE {site}
  INNERBOX 5.0
  OUTERBOX auto
  LIGAND_FILE {ligand}
  LIGANDS_TO_DOCK existing
  DOCKING_PRECISION {precision}

STAGE SCORING
  SCORE_NAME r_psp_IFDScore
  TERM 1.0,r_i_glide_gscore,0
  TERM 0.05,r_psp_Prime_Energy,1
  REPORT_FILE report.csv
"""


@mcp.tool()
def induced_fit_docking(inp_file: str = "", receptor_mae: str = "", ligand_mae: str = "",
                        binding_site: str = "", precision: str = "SP", out_dir: str = "",
                        timeout_s: int = 300) -> dict:
    """Induced-Fit Docking (IFD): Glide+Prime flexible-receptor docking (models receptor
    side-chain/backbone rearrangement). ASYNC -> {jobid}. Provide EITHER a prepared `inp_file`
    (an IFD .inp protocol - the exact, verified ifd interface) OR receptor_mae + ligand_mae +
    binding_site to auto-generate the STANDARD IFD protocol. binding_site = 'ligand <ASL>'
    (e.g. 'ligand Z:999'), a residue, or 'x y z' coords. precision = SP|XP. Glide+Prime, no
    Desmond. NOTE: the auto-generated .inp is the documented standard protocol -
    argv/template-verified, runtime-untested; validate against a Maestro IFD export."""
    if precision not in ("SP", "XP"):
        return {"error": "precision must be SP or XP"}
    try:
        if inp_file:
            inp = _safe_path(inp_file, must_exist=True)
            wd = os.path.dirname(inp) or "."
        else:
            if not (receptor_mae and ligand_mae and binding_site):
                return {"error": "provide inp_file OR (receptor_mae + ligand_mae + binding_site)"}
            if any(c in binding_site for c in "\r\n\x00"):
                return {"error": "unsafe binding_site"}
            rec = _safe_path(receptor_mae, must_exist=True)
            lig = _safe_path(ligand_mae, must_exist=True)
            wd = _safe_path(out_dir) if out_dir else (os.path.dirname(rec) or ".")
            os.makedirs(wd, exist_ok=True)
            inp = os.path.join(wd, "ifd_job.inp")
            with open(inp, "w") as fh:
                fh.write(_IFD_STANDARD_INP.format(receptor=rec, ligand=lig,
                                                  site=binding_site, precision=precision))
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    argv = [_driver("ifd"), os.path.basename(inp), "-HOST", "localhost"]
    res = _submit_async(argv, cwd=wd, timeout=timeout_s)
    res["inp"] = inp
    return res


@mcp.tool()
def covalent_docking(receptor_mae: str, ligand_mae: str, attachment_residue: str,
                     rxn_type: str = "Michael Addition", mode: str = "score", out_dir: str = "",
                     njobs: int = 1, timeout_s: int = 300) -> dict:
    """Covalent docking: dock ligands that form a covalent bond to a receptor residue (e.g. a
    warhead to a catalytic Cys). attachment_residue = '<chain>:<resnum>' (e.g. 'A:145', ':3').
    rxn_type = a supported reaction name (Michael Addition, Nucleophilic Substitution, Boronic
    Acid Addition, Disulfide Formation, Epoxide Opening, ...). mode = leadopt|enrichment|score|
    attach. Glide+Prime (no Desmond). ASYNC -> {jobid}. NOTE: argv-verified; needs a prepared
    covalent-ready receptor+ligand to run."""
    if mode not in ("leadopt", "enrichment", "score", "attach"):
        return {"error": "mode must be leadopt|enrichment|score|attach"}
    if rxn_type not in _COVALENT_RXNS:
        return {"error": f"unsupported rxn_type; must be one of {sorted(_COVALENT_RXNS)}"}
    if not re.fullmatch(r"[A-Za-z]?:[0-9]+[A-Za-z]?", attachment_residue or ""):
        return {"error": "attachment_residue must be '<chain>:<resnum>' e.g. 'A:145' or ':3'"}
    try:
        receptor_mae = _safe_path(receptor_mae, must_exist=True)
        ligand_mae = _safe_path(ligand_mae, must_exist=True)
        wd = _safe_path(out_dir) if out_dir else (os.path.dirname(receptor_mae) or ".")
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(wd, exist_ok=True)
    job = "covdock_job"
    nj = max(1, int(njobs))
    argv = [_driver("covalent_docking"), receptor_mae, ligand_mae, attachment_residue,
            "-rxn_type", rxn_type, "-mode", mode, "-JOBNAME", job,
            "-HOST", f"localhost:{nj}", "-NJOBS", str(nj)]
    res = _submit_async(argv, cwd=wd, timeout=timeout_s)
    res["expected_poses"] = os.path.join(wd, job + "-out.maegz")
    return res


# ============================================================================
# ==== APPENDED TOOL GROUP: g01_feploop ====
# ============================================================================

# IMPORTS: (none new — uses os, glob, subprocess already imported at the top of server.py)
#
# GROUP g01_feploop — the FEP+ loop's LOCAL bookends around the existing (remote-submit) fep_plus:
#   fep_map_build   -> authors + QC's the .fmp perturbation graph that fep_plus consumes
#   fep_parse_results -> parses the -out.fmp fep_plus produces (pure read, no token)
# Both are thin server-side wrappers; the schrodinger-import work lives in _sch_helper.py
# (_fep_map_qc / _fep_parse_results), matching how desmond_trajectory_analysis delegates to _helper.
# The fep_mapper CLI + the scisol.fep.graph API used below were VERIFIED against the live
# 2026-2 install (see the helper header); the RUN of the map still needs the Desmond engine.


# ---------- FEP+ map authoring (local prep; LOMAP is CPU, no Desmond/GPU, no token) ----------

@mcp.tool()
def fep_map_build(ligands_mae: str, out_fmp: str, extra_edges: list = None,
                  gpu_edge_budget: int = 24, timeout_s: int = 1800) -> dict:
    """Author a FEP+ perturbation map (.fmp) from prepared ligands (.mae/.maegz — e.g. LigPrep
    output or a pose-viewer _pv.mae) - the input fep_plus needs and the local prep step no other
    tool produced. LOMAP-authors the graph via the VERIFIED CLI
    `$SCHRODINGER/run -FROM scisol fep_mapper.py <ligands> -o <basename>` (CPU MCS/networkx: no
    Desmond, no GPU, no license token; writes <basename>.fmp), then via the scisol fep.graph API
    injects any manual `extra_edges` - a list of [from_id, to_id] node-id pairs LOMAP can't map
    (e.g. an R/S chirality edge; the added edge is a topological placeholder with no precomputed
    atom-mapping, so complete it in Maestro before submitting) - QC's connectivity + independent-
    cycle count, flags orphan/disconnected nodes, and warns if the edge count exceeds
    `gpu_edge_budget` (each edge is ~GPU-hours of FEP). Returns {fmp, n_nodes, n_edges,
    disconnected_nodes[], edges_added}. NOTE: the mapper CLI + the scisol.fep.graph API are
    verified against this 2026-2 install; RUNNING the map (fep_plus) still needs the Desmond
    engine, NOT installed on this host - so authoring is runtime-untested here; validate the first
    live run."""
    try:
        ligands_mae = _safe_path(ligands_mae, must_exist=True)
        out_fmp = _safe_path(out_fmp)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if extra_edges is not None and not isinstance(extra_edges, list):
        return {"error": "extra_edges must be a list of [from_id, to_id] node-id pairs"}
    wd = os.path.dirname(out_fmp) or "."
    os.makedirs(wd, exist_ok=True)
    job = _jobname(out_fmp, "_map")            # sanitized basename ([A-Za-z0-9_-], no extension)
    base_fmp = os.path.join(wd, job + ".fmp")  # fep_mapper writes <basename>.fmp from -o <basename>
    # -FROM scisol makes `run` resolve fep_mapper.py inside the scisol package's scripts dir.
    # -o takes a BASENAME (no extension) — passing "job.fmp" would yield "job.fmp.fmp".
    argv = [_run(), "-FROM", "scisol", "fep_mapper.py", ligands_mae, "-o", job]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    # fep_mapper writes exactly <job>.fmp; accept a <job>*.fmp variant as a defensive fallback.
    cand = [base_fmp] + sorted(glob.glob(os.path.join(wd, job + "*.fmp")))
    produced = next((c for c in cand if os.path.exists(c)), None)
    if produced is None:
        return {"error": "fep_mapper produced no .fmp (mapping failed or CLI mismatch)",
                "returncode": p.returncode, "argv_tail": " ".join(argv[-4:]),
                "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    qc = _helper("fep_map_qc", {"in_fmp": produced, "out_fmp": out_fmp,
                                "extra_edges": extra_edges or [],
                                "gpu_edge_budget": int(gpu_edge_budget)}, timeout=300)
    qc["returncode"] = p.returncode
    qc.setdefault("base_fmp", produced)
    if "error" in qc:  # helper (schrodinger-side) failed — surface the mapper subprocess tails too
        qc.setdefault("stdout_tail", p.stdout[-800:])
        qc["stderr_tail"] = p.stderr[-1200:]
    return qc


# ---------- FEP+ result parsing (no license token; closes the fep_plus loop) ----------

@mcp.tool()
def fep_parse_results(out_fmp: str, hysteresis_kcal: float = 1.0, overlap_min: float = 0.10,
                      ddg_unc_kcal: float = 1.0) -> dict:
    """Parse a completed FEP+ map (the `-out.fmp` fep_plus writes) into structured results - pure
    file read via scisol fep.graph.Graph.deserialize, no license token. Extracts per-edge Bennett
    ddG +/- unc (with the cycle-closure-corrected ccc_ddg and complex/solvent legs when present),
    per-node cycle-closure-corrected pred_dg +/- unc (+ experimental dG when present), fundamental-
    cycle hysteresis, and per-edge reliability flags. Edges failing the thresholds
    (`hysteresis_kcal`, `overlap_min`, `ddg_unc_kcal`) are collected in `recommend_extend`
    (candidates to extend sampling or re-run). Returns {fmp, n_nodes, n_edges, nodes, edges,
    cycle_closure, recommend_extend}. Mirrors qikprop_parse_results' style (structured rows,
    file-only, no token); FEP is graph-shaped so the keys differ. NOTE: attribute names are
    verified against this 2026-2 install; per-edge phase-space-overlap / fwd-rev convergence are
    not exposed on the graph Edge, so the ACTIVE reliability signals are ddG uncertainty and the
    node-dG cycle-closure residual (both always computed)."""
    try:
        out_fmp = _safe_path(out_fmp, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    return _helper("fep_parse_results", {"out_fmp": out_fmp,
                                         "hysteresis_kcal": float(hysteresis_kcal),
                                         "overlap_min": float(overlap_min),
                                         "ddg_unc_kcal": float(ddg_unc_kcal)}, timeout=180)


# ============================================================================
# ==== APPENDED TOOL GROUP: g02_qmprep ====
# ============================================================================

# IMPORTS: (none new) — the fragment reuses existing server.py names: os, subprocess,
#          glob, _safe_path, _helper, _driver, _exec, _jobname. (re/json already imported.)
# PLACEMENT: insert these @mcp.tool() functions BEFORE the trailing
#          `if __name__ == "__main__": mcp.run()` block — the @mcp.tool() decorators must
#          execute at import time, i.e. before mcp.run() runs when the module is __main__.
#
# ==================================================================================
# GROUP g02_qmprep — QM-prep tools (append these @mcp.tool() functions).
#   qm_cluster_extract (no token, structure lib) -> _helper("qm_cluster_extract", ...)
#   jaguar_qm          (Jaguar token)            -> _helper("jaguar_in", ...); `jaguar run <in> -NOJOBID`; _helper("jaguar_energy", ...)
#   epik_pka           (Epik token)              -> `epikx <in> <out> -ph <v> -WAIT [--query|-r]`; _helper("epik_pka_parse", ...)
#   (jaguar_pka is a MODIFY of the existing function — see g02_qmprep.mods.md.)
#
# VERIFIED against the installed Schrodinger 2026-2 source (jaguar-v13.2, epik-v7.6):
#   - JaguarInput(structure=, genkeys=).saveAs()      [application/jaguar/input.py:281-322,572]
#   - JaguarOutput.energy/gas_phase_energy/solution_phase_energy (Hartrees) + .status
#     (0/1/2 = UNKNOWN/OK/SPLAT) convergence flag  [jaguar/output.py:187,504; results.py:2340,2362]
#   - `jaguar run <in> -NOJOBID` = a single synchronous in-process job
#     ("-NOJOBID is only supported with single Jaguar jobs", jaguarc.py:539).
#   - dftname=B97-3c is a shipped composite (HF-3C/PBEH-3C/B97-3C/R2SCAN-3C/WB97X-3C,
#     jaguar_timer_data.py:134) whose basis+D3+gCP are intrinsic -> no `basis` for *-3c.
#     isolv=2 = PBF SCRF; igeopt 0/1/2 = sp/opt/ts. &gen keys dftname/basis/igeopt/molchg/
#     isolv/solvent all present in jaguar-v13.2.
#   - epikx CLI (epikx/arguments.py): positional infile/outfile, -ph, -WAIT, --query
#     ("Query pKas only; do not predict states"), -r/--report. report and --query are
#     MUTUALLY EXCLUSIVE (validate_args: "Reports are only available for state prediction
#     jobs.") -> report=True drops --query. Output props r_epik_acidic/basic_macro-pKa +
#     r_epik_atom_pKa (epikx/constants.py:17-38); parsed name-agnostically.
#   confidence=low (one live run still needed): whether ipka_max_conf=1 truly keeps a pKa
#     job single-process under -NOJOBID (see jaguar_pka in mods.md), and the exact .out pKa
#     text layout the parser targets.


# ---------- QM cluster extraction (no license token; structure library) ----------

@mcp.tool()
def qm_cluster_extract(complex_mae: str, ligand_asl: str, radius: float = 5.0, cap: str = "H",
                       out_dir: str = "", timeout_s: int = 300) -> dict:
    """Carve a capped QM cluster from a protein-ligand complex (.mae/.maegz) for QM / QM-MM. Selects
    whole residues within `radius` A of `ligand_asl` (ASL fillres+within), severs each backbone/
    side-chain bond crossing the cluster boundary, H-caps the cut along the ORIGINAL bond vector
    (at the element's X-H length), and partitions into ligand / pocket / complex. Emits three .xyz
    files + a JSON manifest {total_charge, multiplicity, fragment_atom_ranges, net_charge_per_fragment,
    valence_check} (a formal-charge/valence self-check: caps == cuts + per-atom bond-order audit).
    No license token (schrodinger.structure only). Feeds qdx-rush ExESS or jaguar_qm."""
    try:
        complex_mae = _safe_path(complex_mae, must_exist=True)
        out_dir = _safe_path(out_dir) if out_dir else (os.path.dirname(complex_mae) or ".")
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    # ligand_asl is a query string (goes to schrodinger's ASL evaluator, not a shell); it is
    # JSON-encoded into one _helper argv element -> inert. Block only control chars (newline
    # could smuggle a second ASL/directive line the same way _safe_path guards paths).
    if not isinstance(ligand_asl, str) or not ligand_asl.strip() or \
            any(c in ligand_asl for c in "\r\n\x00"):
        return {"error": "invalid/unsafe ligand_asl"}
    if cap != "H":
        return {"error": "only cap='H' (hydrogen capping) is implemented"}
    os.makedirs(out_dir, exist_ok=True)
    return _helper("qm_cluster_extract",
                   {"complex_mae": complex_mae, "ligand_asl": ligand_asl,
                    "radius": float(radius), "cap": cap, "out_dir": out_dir}, timeout=timeout_s)


# ---------- Jaguar QM single-point / optimization (synchronous -NOJOBID; JAGUAR token) ----------

@mcp.tool()
def jaguar_qm(structure_file: str, out_dir: str, mode: str = "sp", theory: str = "B97-3c",
              solvent: str = "", molchg: int = 0, timeout_s: int = 7200) -> dict:
    """Jaguar QM energy on a SMALL structure (.mae/.sdf). Builds a Jaguar .in (&gen
    dftname/igeopt/molchg[/isolv]) via the jaguar input API, then runs `jaguar run <in> -NOJOBID`
    (single job, synchronous, in-process - no job server). mode = sp|opt|ts (igeopt 0/1/2). theory
    default B97-3c is a shipped composite (def2 basis + D3 + gCP intrinsic -> no basis set); other
    functionals get 6-31G**. solvent!='' turns on PBF continuum solvation (isolv=2). Energy parsed
    from the .out via JaguarOutput (Hartrees). Consumes a Jaguar token. Input API, &gen keys,
    -NOJOBID and the B97-3c composite verified against the installed jaguar-v13.2 source."""
    try:
        structure_file = _safe_path(structure_file, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    igeopt = {"sp": 0, "opt": 1, "ts": 2}.get(mode)
    if igeopt is None:
        return {"error": "mode must be sp|opt|ts"}
    if any(c in theory for c in " \r\n\x00") or any(c in solvent for c in " \r\n\x00"):
        return {"error": "unsafe theory/solvent (no spaces/newlines)"}
    os.makedirs(out_dir, exist_ok=True)
    genkeys = {"dftname": theory, "igeopt": str(igeopt), "molchg": str(int(molchg))}
    if not theory.lower().endswith("-3c"):        # composites carry their own basis; others need one
        genkeys["basis"] = "6-31G**"
    if solvent:                                   # PBF self-consistent reaction field
        genkeys["isolv"] = "2"
        genkeys["solvent"] = solvent
    # job basename flows into argv as a POSITIONAL arg -> _jobname sanitizes to [A-Za-z0-9_-]
    # and lstrip('-') guarantees it can never be read as a flag.
    job = _jobname(structure_file, "_qm").lstrip("-") or "job_qm"
    in_file = os.path.join(out_dir, job + ".in")
    built = _helper("jaguar_in",
                    {"structure_file": structure_file, "out_in": in_file, "genkeys": genkeys},
                    timeout=180)
    if not isinstance(built, dict) or "error" in built or not os.path.exists(in_file):
        return {"error": "failed to build Jaguar input", "detail": built}
    argv = [_driver("jaguar"), "run", os.path.basename(in_file), "-NOJOBID"]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    out_file = os.path.join(out_dir, job + ".out")
    res = {"returncode": p.returncode, "in_file": in_file, "theory": theory, "mode": mode,
           "out_file": out_file if os.path.exists(out_file) else None,
           "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    if os.path.exists(out_file):
        parsed = _helper("jaguar_energy", {"out_file": out_file}, timeout=180)
        if isinstance(parsed, dict):
            res["energy_hartree"] = parsed.get("energy")
            res["gas_phase_energy"] = parsed.get("gas_phase_energy")
            res["solution_phase_energy"] = parsed.get("solution_phase_energy")
            res["converged"] = parsed.get("converged")
    return res


# ---------- fast Epik ML pKa (synchronous -WAIT; consumes an Epik token) ----------

@mcp.tool()
def epik_pka(input_mae: str, out_dir: str, ph: float = 7.4, query_only: bool = True,
             report: bool = False, timeout_s: int = 1800) -> dict:
    """Fast Epik v7 (EpikX) ML pKa on a structure (.mae/.sdf/.smi/.csv) via `epikx --query` -
    predicts site pKas WITHOUT enumerating a full protonation-state ensemble (distinct from
    epik_enumerate). Annotates the output with r_epik_acidic/basic_macro-pKa + per-atom
    r_epik_atom_pKa, parsed back into a {pka} summary. NOTE: `--query` and `--report` are mutually
    exclusive in Epik (a report needs predict-states mode; single structure only), so report=True
    drops --query and runs predict-states with a report dir. Consumes an Epik token. CLI flags +
    the report/query exclusion verified vs the installed epikx arguments.py."""
    try:
        input_mae = _safe_path(input_mae, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)
    # out basename is a POSITIONAL argv arg (epikx <in> <out>) -> sanitize the stem so it can
    # never start with '-' even if the input file's basename does.
    stem = _jobname(input_mae).lstrip("-") or "job"
    out_mae = os.path.join(out_dir, stem + "_epikpka.mae")
    use_query = bool(query_only) and not report          # Epik: report and query are exclusive
    argv = [_driver("epikx"), input_mae, os.path.basename(out_mae), "-ph", str(float(ph)), "-WAIT"]
    if use_query:
        argv.append("--query")
    if report:
        argv.append("-r")
    try:
        p = _exec(argv, timeout=timeout_s, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    res = {"returncode": p.returncode, "mode": "query" if use_query else "predict_states",
           "output": out_mae if os.path.exists(out_mae) else None,
           "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    if report:
        rep = glob.glob(os.path.join(out_dir, "*_report"))
        res["report_dir"] = rep[0] if rep else None
    if os.path.exists(out_mae):
        parsed = _helper("epik_pka_parse", {"output": out_mae}, timeout=180)
        if isinstance(parsed, dict) and "error" not in parsed:
            res["pka"] = parsed
    return res


# ============================================================================
# ==== APPENDED TOOL GROUP: g03_parse ====
# ============================================================================

# IMPORTS: import hashlib
#
# server.py additions for group g03_parse (Parse + doctor).
#   - structure_properties_extract : LIBRARY tool (needs _sch_helper _proplist + CMDS "proplist").
#   - backend_doctor               : local read-only probe tool (pure _exec/os/glob/hashlib; no helper,
#                                    no license token). Fully self-contained (nested probes) so it
#                                    appends cleanly; the ONLY new top-level import is `hashlib`.
# Both call existing internals (_safe_path, _helper, _exec, _driver, _jsc, SCHRODINGER) - none redefined.


# ---------- structure property tabulation (no license token; generalizes qikprop_parse_results) ----------

@mcp.tool()
def structure_properties_extract(structure_file: str, properties: list = None, sort_by: str = "",
                                 descending: bool = False, limit: int = 200,
                                 timeout_s: int = 300) -> dict:
    """Tabulate the per-structure properties embedded in a structure file (.mae/.maegz/.sdf/.sdfgz/
    .pdb) - the m2io keys Glide/Prime/IFD/Epik/SiteMap/BPMD write onto each pose: r_i_glide_gscore,
    r_i_glide_emodel, r_psp_MMGBSA_dG_Bind, r_psp_IFDScore, r_epik_*, r_sitemap_SiteScore/Dscore,
    BPMD CompScore, and any custom property. Call with NO `properties` to list every available
    property key (discovery mode: keys + dtypes + a sample row). Pass `properties` to subset columns
    by case-insensitive substring; `sort_by` orders rows by a property (numeric-aware) with
    `descending`; `limit` caps returned rows. Pure structure read via schrodinger.structure (no
    token). Complements qikprop_parse_results (which parses the QikProp .CSV, not the structure-
    embedded properties) - use this for pose/score files, that for the QikProp table."""
    try:
        structure_file = _safe_path(structure_file, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    return _helper("proplist", {"src": structure_file, "properties": properties or [],
                                "sort_by": sort_by, "descending": bool(descending),
                                "limit": max(1, int(limit))}, timeout=timeout_s)


# ---------- backend readiness doctor (local, read-only; no license token) ----------

@mcp.tool()
def backend_doctor(deep: bool = False) -> dict:
    """Structured backend readiness for the local Schrodinger suite (read-only, no token). Fail-open
    probes: `licadmin STAT` -> per-feature token pools (GLIDE/PRIME/FEP_GPGPU/QIKPROP/JAGUAR/...),
    `jsc local-server-status` -> job server, `nvidia-smi -L` -> GPUs, and Desmond MD engine presence
    (absent on the Windows suite - Desmond GPU is Linux-only). Returns {suite_version, tokens,
    key_tokens, job_server, gpus, gpu_count, desmond_engine, license_ok, ready, ...}. `deep=True`
    adds the Linux x509 license-cure audit: md5-verifies $SCHRODINGER/internal/lib/libmmfileshared.so
    against the vendor cure build (md5 a34a793..., 1080144 B) and asserts SCHRODINGER_FEATURE_FLAGS
    ENABLES SCHRODINGER_LICENSE_MANAGER. Operational-readiness companion to backend_info."""
    lmstat_re = re.compile(
        r"Users of (\S+):\s+\(Total of (\d+) license[s]? issued;\s+"
        r"Total of (\d+) license[s]? in use\)", re.IGNORECASE)
    key_feats = ("GLIDE", "PRIME", "FEP_GPGPU", "QIKPROP", "JAGUAR", "DESMOND", "EPIK", "CANVAS")

    def _tokens():
        """licadmin STAT -> {feature: {issued, in_use}} (FlexLM lmstat passthrough)."""
        try:
            p = _exec([_driver("licadmin"), "STAT"], timeout=60)
        except subprocess.TimeoutExpired:
            return {}, "licadmin STAT timed out after 60s", None
        except (FileNotFoundError, OSError) as e:
            return {}, f"licadmin not runnable: {e!r}", None
        blob = (p.stdout or "") + "\n" + (p.stderr or "")
        toks = {feat: {"issued": int(iss), "in_use": int(use)}
                for feat, iss, use in lmstat_re.findall(blob)}
        return toks, (None if toks else "no FlexLM feature lines parsed from licadmin STAT"), blob[-1200:]

    def _license_valid():
        """Secondary probe for a local-entitlement (SLM) license, where STAT lists no pools.
        Reads `licadmin debug-sources`: x509 failure -> invalid; err=None / rc 0 -> valid."""
        try:
            p = _exec([_driver("licadmin"), "debug-sources"], timeout=60)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return None
        low = ((p.stdout or "") + (p.stderr or "")).lower()
        if "x509 verification failed" in low or "unable to get local issuer" in low:
            return False
        if "err=none" in low.replace(" ", ""):
            return True
        return True if p.returncode == 0 else None

    def _gpus():
        """nvidia-smi -L -> [{index, name, uuid}]; empty if no NVIDIA GPU / tool absent."""
        try:
            p = _exec(["nvidia-smi", "-L"], timeout=30)
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return []
        out = []
        for line in (p.stdout or "").splitlines():
            m = re.match(r"GPU (\d+):\s+(.*?)\s+\(UUID:\s+(\S+?)\)", line.strip())
            if m:
                out.append({"index": int(m.group(1)), "name": m.group(2), "uuid": m.group(3)})
        return out

    def _job_server():
        """jsc local-server-status -> {running, returncode, detail} (reuses the _jsc chokepoint)."""
        try:
            p = _jsc("status", timeout=60)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return {"running": False, "note": f"jsc status error: {e!r}"}
        blob = (p.stdout or "") + (p.stderr or "")
        return {"running": "RUNNING" in blob.upper(), "returncode": p.returncode,
                "detail": blob[-400:]}

    def _desmond():
        """Detect the Desmond MD engine install (product dir or backend binary under mmshare)."""
        hits = (glob.glob(os.path.join(SCHRODINGER, "desmond-v*"))
                or glob.glob(os.path.join(SCHRODINGER, "mmshare-v*", "bin", "*", "desmond"))
                or glob.glob(os.path.join(SCHRODINGER, "mmshare-v*", "bin", "*", "desmond.exe")))
        return bool(hits), (hits[0] if hits else None)

    toks, tok_note, stat_tail = _tokens()
    js = _job_server()
    gpus = _gpus()
    desmond_present, desmond_path = _desmond()

    ver = None  # instant version.txt read (no subprocess), mirroring schrodinger_version
    vt = os.path.join(SCHRODINGER, "version.txt")
    try:
        if os.path.exists(vt):
            with open(vt, encoding="utf-8", errors="replace") as fh:
                ver = fh.read().strip() or None
    except OSError:
        ver = None

    key_tokens = {}  # roll up the flagship product pools by substring (lossless: keeps raw names)
    for feat in key_feats:
        match = {n: c for n, c in toks.items() if feat in n.upper()}
        if match:
            key_tokens[feat] = match

    stat_ok = bool(toks and any(c["issued"] > 0 for c in toks.values()))
    if stat_ok:  # STAT already proves a served license -> skip the extra debug-sources probe
        license_valid, license_ok = None, True
    else:
        license_valid = _license_valid()
        license_ok = license_valid is True

    res = {"schrodinger": SCHRODINGER, "suite_version": ver,
           "tokens": toks, "key_tokens": key_tokens,
           "job_server": js, "gpus": gpus, "gpu_count": len(gpus),
           "desmond_engine": desmond_present, "desmond_engine_path": desmond_path,
           "license_ok": license_ok}
    if tok_note:
        res["licadmin_note"] = tok_note
        if stat_tail:
            res["licadmin_stat_tail"] = stat_tail
    if license_valid is not None:
        res["license_valid"] = license_valid

    if deep:  # x509 license-cure audit (Linux) + feature-flag assertion
        path = os.path.join(SCHRODINGER, "internal", "lib", "libmmfileshared.so")
        cure = {"present": os.path.exists(path), "path": path,
                "expected_md5": "a34a793bd05237c30f8cdc4ac750d290", "expected_bytes": 1080144}
        if cure["present"]:
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
                cure["md5"] = hashlib.md5(data, usedforsecurity=False).hexdigest()  # integrity, not crypto
                cure["size_bytes"] = len(data)
                cure["matches_cure"] = (cure["md5"] == cure["expected_md5"]
                                        and cure["size_bytes"] == cure["expected_bytes"])
            except OSError as e:
                cure["error"] = repr(e)
        else:
            cure["note"] = ("absent - expected on the Windows suite; the x509 libmmfileshared.so "
                            "cure is Linux-only")
        res["license_cure"] = cure
        flags = os.environ.get("SCHRODINGER_FEATURE_FLAGS", "")
        res["feature_flags"] = flags
        # Enabling form is `+SCHRODINGER_LICENSE_MANAGER` (a bare token also enables); an explicit
        # `-SCHRODINGER_LICENSE_MANAGER` DISABLES it - a bare substring test would false-positive.
        _lm = "SCHRODINGER_LICENSE_MANAGER"
        res["feature_flags_ok"] = ("+" + _lm) in flags or (_lm in flags and ("-" + _lm) not in flags)

    res["ready"] = bool(license_ok and js.get("running"))  # license serving + job server reachable
    return res


# ============================================================================
# ==== APPENDED TOOL GROUP: g04_poseqc ====
# ============================================================================

# IMPORTS: (none new — uses existing os / json / subprocess and the internal _safe_path + _helper)
#
# Group g04_poseqc: two LIBRARY (license-token-free) pose-QC tools. Each validates client paths
# with _safe_path, then delegates to _sch_helper.py via _helper() (runs in the Schrodinger
# interpreter where schrodinger.structutils + rdkit are importable). No product driver, no token.

# ---------- pose QC (license-token-free; RDKit + structutils in the interpreter) ----------

@mcp.tool()
def pose_validity(pose_viewer_maegz: str, ref_input: str = "", strain_threshold_kcal: float = 20.0,
                  clash_ratio_cutoff: float = 0.75, timeout_s: int = 600) -> dict:
    """PoseBusters-style per-pose QC on a Glide pose-viewer (*_pv.maegz) or a Prime -out.maegz
    (structure[0] = receptor, rest = ligand poses). Per pose: RDKit sanitize + InChI round-trip,
    bond-length sanity, aromatic-ring planarity, internal + ligand-protein steric clash (with
    overlap volume), stereo/connectivity preserved vs `ref_input` (an optional prepared reference
    ligand file - .mae/.sdf/.pdb), and MMFF94s strain energy (pose vs relaxed). When BOTH
    r_i_glide_gscore and r_psp_MMGBSA_dG_Bind are present it flags Glide-vs-Prime rank
    disagreement (consensus_flag). `clash_ratio_cutoff` is the vdw-ratio clash threshold (~0.75);
    `strain_threshold_kcal` gates the advisory high_strain flag. No license token. Returns per-pose
    {pass, failed_checks[], strain_kcal, consensus_flag, ...}."""
    try:
        pose_viewer_maegz = _safe_path(pose_viewer_maegz, must_exist=True)
        ref = _safe_path(ref_input, must_exist=True) if ref_input else ""
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    return _helper("pose_validity", {"pose_viewer": pose_viewer_maegz, "ref_input": ref,
                                     "strain_threshold": float(strain_threshold_kcal),
                                     "clash_cutoff": float(clash_ratio_cutoff)}, timeout=timeout_s)


@mcp.tool()
def pose_interaction_fingerprint(pose_maegz: str, recept_asl: str = "protein",
                                 timeout_s: int = 600) -> dict:
    """Per-residue protein-ligand interaction fingerprint for docked poses in a pose-viewer
    (structure[0] = receptor, rest = ligand poses). Via schrodinger.structutils.interactions:
    H-bonds (receptor donor/acceptor role + distance/angle), salt bridges, pi-pi (face/edge-to-
    face), pi-cation, and hydrophobic C-C contacts - grouped per receptor residue. The phenibut
    zwitterion NH3+ / COO- salt bridge to the GABA-B orthosteric site is the load-bearing contact
    this surfaces. `recept_asl` restricts the receptor selection within the first CT (default all
    'protein'). No license token. Returns per-pose {n_contact_residues, salt_bridge, residues[...]}."""
    try:
        pose_maegz = _safe_path(pose_maegz, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if any(c in recept_asl for c in "\r\n\x00"):
        return {"error": "unsafe recept_asl (control char)"}
    return _helper("pose_ifp", {"pose_maegz": pose_maegz, "recept_asl": recept_asl}, timeout=timeout_s)


# ============================================================================
# ==== APPENDED TOOL GROUP: g05_structglue ====
# ============================================================================

# IMPORTS: (none new) — uses existing server.py names: os, subprocess, _safe_path,
#          _helper, _driver, _exec, _ensure_job_server, _jobname. shutil is already imported.

# ==================================================================================
# GROUP g05_structglue — structure glue tools (append these @mcp.tool() functions).
#   pose_viewer_split   (local-lib)   -> _helper("pose_viewer_split", ...)
#   reaction_enumerate  (local-lib)   -> _helper("reaction_enumerate", ...)
#   macromodel_confsearch (local-token) -> _helper("mmod_confsearch", ...) then bmin
#
# HARDENED (adversarial review vs installed Schrodinger 2026-2 source):
#   - Verified ComUtil(ffld/wait/subs) ctor, ComUtil.mcmm(mae_file,com_file,out_file) sig,
#     mcu.solv/SOLV[2]/exnb attrs, GB/SA solvent codes (Water=1/CHCL3=5/Octanol=9), and the
#     bmin bare-jobname launch form — all against $SCHRODINGER/.../macromodel/{utils,input}.py.
#   - Fixed the .mae reagent path in _reaction_enumerate (helper): the bundled RDKit adapter
#     is schrodinger.rdkit.rdkit_adapter.to_rdkit (all-defaulted kwargs), NOT the raw
#     schrodinger.adapter.to_rdkit which requires a second `options` object.
#   - Tightened the property_filter eval sandbox (char allowlist + no dunder/import/lambda/**).
# ==================================================================================


# ---------- pose-viewer splitting (no license token; structure library) ----------

@mcp.tool()
def pose_viewer_split(pv_maegz: str, out_dir: str, mode: str = "complex") -> dict:
    """Split a Glide pose-viewer (*_pv.maegz: structure[0]=receptor, [1:]=ligand poses) into
    per-pose files - one output per docked pose. mode=complex -> receptor+ligand written as a
    single-pose pose-viewer (the glue that feeds bpmd / qm_cluster_extract per pose); ligand ->
    the pose only; receptor -> the shared receptor once. schrodinger.structure only, no token.
    Returns {files, poses, n_poses}."""
    if mode not in ("complex", "ligand", "receptor"):
        return {"error": "mode must be complex|ligand|receptor"}
    try:
        pv_maegz = _safe_path(pv_maegz, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)
    return _helper("pose_viewer_split", {"pv_maegz": pv_maegz, "out_dir": out_dir, "mode": mode})


# ---------- combinatorial / R-group enumeration (no license token; RDKit) ----------

@mcp.tool()
def reaction_enumerate(core_smarts: str, reagent_files: list, out_file: str,
                       max_products: int = 1000, property_filter: str = "") -> dict:
    """Combinatorial R-group / reaction enumeration: apply a reaction SMARTS to one reagent file
    per reactant slot and write the enumerated products to .sdf (default) or .smi. `core_smarts` =
    an atom-mapped RDKit reaction SMARTS (e.g. '[C:1](=O)[OH].[N:2]>>[C:1](=O)[N:2]');
    `reagent_files` = a list with ONE file per reactant slot (.smi/.smiles/.txt/.csv/.sdf/.mae).
    `property_filter` = an optional boolean expr over mw,logp,hbd,hba,tpsa,rotb,rings,qed
    (e.g. 'mw<=500 and hbd<=5 and logp<=5'). Dedups by canonical SMILES, caps at max_products.
    RDKit-backed in the Schrodinger interpreter (no license token). Returns {out_file, n_products}."""
    if not isinstance(reagent_files, list) or not reagent_files:
        return {"error": "reagent_files must be a non-empty list (one file per reactant slot)"}
    if not isinstance(core_smarts, str) or not core_smarts.strip() \
            or any(c in core_smarts for c in "\r\n\x00"):
        return {"error": "invalid core_smarts (non-empty, no newline/control chars)"}
    if property_filter and any(c in property_filter for c in "\r\n\x00"):
        return {"error": "invalid property_filter (no newline/control chars)"}
    if int(max_products) < 1:
        return {"error": "max_products must be >= 1"}
    try:
        rf = [_safe_path(f, must_exist=True) for f in reagent_files]
        out_file = _safe_path(out_file)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    return _helper("reaction_enumerate", {"core_smarts": core_smarts, "reagent_files": rf,
                                          "out_file": out_file, "max_products": int(max_products),
                                          "property_filter": property_filter}, timeout=600)


# ---------- MacroModel MCMM conformational search (consumes a MacroModel token) ----------

@mcp.tool()
def macromodel_confsearch(input_mae: str, out_mae: str, ffld: str = "OPLS4", solvent: str = "Water",
                          timeout_s: int = 1800) -> dict:
    """MacroModel MCMM (Monte Carlo Multiple Minimum) exhaustive conformational search + strain
    energy on a small molecule (.mae/.maegz/.sdf). Python writes a valid <job>.com via
    schrodinger.application.macromodel.utils.ComUtil.mcmm() (no shell - ComUtil keeps the no-shell
    contract), then runs `bmin -WAIT <job>` synchronously. ffld = OPLS4|OPLS3e|OPLS_2005|S-OPLS|
    MMFF|MMFFs|AMBER|... ; solvent = Water|None|CHCl3|Octanol (GB/SA continuum). AUTO/AUOP set the
    search depth from rotatable bonds. Returns {out_mae, com, log_tail}. Consumes a MacroModel token.
    NOTE: ComUtil ctor/mcmm() signature, mcu.solv/SOLV[2]/exnb, the GB/SA solvent codes
    (Water=1/CHCl3=5/Octanol=9) and the bare-jobname bmin launch are all verified against the
    installed 2026-2 macromodel/{utils,input}.py; a live bmin run still needs a MacroModel token."""
    try:
        input_mae = _safe_path(input_mae, must_exist=True)
        out_mae = _safe_path(out_mae)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    # ffld strings the ComUtil ctor genuinely resolves (regex chain + mm.opls_name_to_version);
    # OPLS3/OPLS3e/S-OPLS/OPLS4 all map to FFLD version 16. Names outside this set silently fall
    # back to OPLS_2005 in ComUtil, so we reject them rather than run the wrong force field.
    valid_ff = {"AMBER", "AMBER94", "MM2", "MM3", "MMFF", "MMFFs", "OPLS",
                "OPLS_2003", "OPLS_2005", "OPLS3", "OPLS3e", "S-OPLS", "OPLS4"}
    if ffld not in valid_ff:
        return {"error": f"ffld must be one of {sorted(valid_ff)}"}
    if solvent not in ("Water", "None", "CHCl3", "Octanol"):
        return {"error": "solvent must be Water|None|CHCl3|Octanol"}
    wd = os.path.dirname(out_mae) or "."
    os.makedirs(wd, exist_ok=True)
    job = _jobname(out_mae)
    if not job.replace("_", "").replace("-", "").isalnum():
        return {"error": f"could not derive a safe job name from {out_mae!r}"}
    # 1) ComUtil writes the .com (+ stages a local input .mae) inside the Schrodinger interpreter.
    setup = _helper("mmod_confsearch", {"input_mae": input_mae, "out_mae": out_mae,
                                        "ffld": ffld, "solvent": solvent, "job": job, "wd": wd})
    if setup.get("error") or not setup.get("com_file"):
        return {"error": "MacroModel .com setup failed", "detail": setup}
    # 2) bmin runs the search (MacroModel license token; -WAIT synchronous, under Job Control).
    #    bmin takes the BARE jobname (it appends .com itself) — verified via ComUtil.getLaunchCommand.
    srv = _ensure_job_server()
    argv = [_driver("bmin"), "-WAIT", job]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s", "com": setup.get("com_file"),
                "job_server": srv}
    alt = os.path.join(wd, job + "-out.mae")
    out = out_mae if os.path.exists(out_mae) else (alt if os.path.exists(alt) else None)
    res = {"returncode": p.returncode, "out_mae": out, "com": setup.get("com_file"),
           "staged_input": setup.get("staged_input"), "job_server": srv,
           "ffld": ffld, "solvent": solvent,
           "stdout_tail": p.stdout[-1200:], "stderr_tail": p.stderr[-1200:]}
    log = os.path.join(wd, job + ".log")
    if os.path.exists(log):
        try:
            with open(log, encoding="utf-8", errors="replace") as fh:
                res["log_tail"] = fh.read()[-1500:]
        except OSError:
            pass
    return res


# ============================================================================
# ==== APPENDED TOOL GROUP: g06_traj ====
# ============================================================================

# IMPORTS: (none new — uses already-imported os, re, subprocess, json and the existing
# IMPORTS: internal helpers _safe_path, _driver, _jobname, _submit_async, _helper)
#
# server.py ADDITIONS for group g06_traj (Trajectory + membrane). Append both @mcp.tool()
# functions. Place near the Desmond block (after desmond_trajectory_analysis / thermal_mmgbsa).
#   - desmond_interactions   : local-lib  -> _helper("trj_interactions", ...)   (token-free)
#   - desmond_membrane_setup : remote-submit -> _submit_async(multisim build_geometry, no -WAIT)


@mcp.tool()
def desmond_interactions(cms_file: str, lig_asl: str = "", prot_asl: str = "protein",
                         metal_asl: str = "", stride: int = 1, top: int = 200,
                         timeout_s: int = 900) -> dict:
    """Protein-ligand interaction FINGERPRINT + persistence over a completed Desmond MD
    trajectory (pass its `-out.cms`; the sibling `_trj` is auto-found). Runs
    schrodinger.application.desmond.packages.analysis.ProtLigInter across EVERY frame and
    returns, keyed by RECEPTOR RESIDUE (chain:RESNAME_resnum), the averaged PERSISTENCE
    (fraction of frames present) of H-bond, pi-pi, pi-cation, salt-bridge, metal and
    water-bridge (plus halogen / hydrophobic) contacts, plus compact per-frame contact
    counts - the numeric core of a Simulation Interactions Diagram. `lig_asl` defaults to
    'not protein and not water and not ion'; `prot_asl` to 'protein'; `metal_asl` uses the
    ProtLigInter default when blank. `stride` subsamples frames; `top` caps the returned
    contact list. License-token-free (in-interpreter trajectory analysis). NOTE: needs a
    completed MD run to exercise end-to-end."""
    try:
        cms_file = _safe_path(cms_file, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    args = {"cms_file": cms_file, "stride": max(1, int(stride)), "top": max(1, int(top))}
    if lig_asl:
        args["lig_asl"] = lig_asl
    if prot_asl:
        args["prot_asl"] = prot_asl
    if metal_asl:
        args["metal_asl"] = metal_asl
    return _helper("trj_interactions", args, timeout=timeout_s)


@mcp.tool()
def desmond_membrane_setup(input_mae: str, out_cms: str, membrane: str = "POPC",
                           box_shape: str = "orthorhombic", buffer_width: float = 10.0,
                           solvent: str = "SPC", salt_conc: float = 0.15,
                           forcefield: str = "OPLS4", timeout_s: int = 300) -> dict:
    """Desmond MEMBRANE system builder: embed a prepared, PRE-ORIENTED solute (.mae/.pdb) in a
    placed lipid bilayer, then solvate + salt -> a Desmond `-out.cms` ready for desmond_md.
    Like desmond_setup but writes a `build_geometry` with a `membrane_box = { lipid = <membrane> }`
    block (the system_builder membrane path) instead of a plain solvent box - for the LAT1
    transporter arm. ASYNC: submits `multisim` build_geometry WITHOUT -WAIT via the job-control
    layer and returns a {jobid} - poll with job_status / job_wait. `membrane`=POPC|POPE|POPS|
    DPPC|DMPC|DOPC|... (any lipid the builder ships); default 0.15 M NaCl; forcefield=OPLS4|
    OPLS_2005|S-OPLS. IMPORTANT: the solute MUST already be oriented so its transmembrane span
    lies in the bilayer plane (OPM/PPM or Maestro's membrane-placement) BEFORE this - the builder
    only PACKS lipids around the supplied pose, it does NOT orient the protein. Requires Desmond +
    the local job server (auto-started). NOTE: msj/argv-verified against the shipped membrane
    template (mmshare data/desmond/kinetics_membrane_md.msj); needs a real Desmond membrane build
    to exercise end-to-end."""
    try:
        input_mae = _safe_path(input_mae, must_exist=True)
        out_cms = _safe_path(out_cms)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if box_shape not in ("orthorhombic", "triclinic"):
        return {"error": f"unsupported box_shape for a membrane: {box_shape!r} (use orthorhombic)"}
    # These flow into the .msj config file -> constrain to inert tokens (no newline/brace
    # injection of extra msj stages).
    if not re.fullmatch(r"[A-Za-z0-9]+", membrane or ""):
        return {"error": f"unsupported membrane lipid: {membrane!r}"}
    if not re.fullmatch(r"[A-Za-z0-9]+", solvent or ""):
        return {"error": f"unsupported solvent: {solvent!r}"}
    if not re.fullmatch(r"[A-Za-z0-9_-]+", forcefield or ""):
        return {"error": f"unsupported forcefield: {forcefield!r}"}
    wd = os.path.dirname(out_cms) or "."
    job = _jobname(out_cms, "_memb")
    bw = float(buffer_width)
    # build_geometry membrane block — byte-faithful to the shipped template
    # $SCHRODINGER/mmshare-v*/data/desmond/kinetics_membrane_md.msj: box holds shape +
    # size_type=buffer, the box dimensions live in membrane_box.size, salt sets the
    # background NaCl, neutralize_system zeroes net charge, scale_solvent_vdw=0.75 is the
    # standard membrane-pack relaxation, and assign_forcefield carries the water model.
    build = [
        'task {', '  task = "desmond:auto"', '}', '',
        'build_geometry {',
        '  box = {', f'    shape     = {box_shape}', '    size_type = buffer', '  }',
        '  membrane_box = {', f'    lipid = {membrane}', f'    size  = [{bw} {bw} {bw}]', '  }',
        '  salt = {', f'    concentration = {float(salt_conc)}',
        '    negative_ion  = Cl', '    positive_ion  = Na', '  }',
        '  neutralize_system   = true', f'  override_forcefield = {forcefield}',
        '  rezero_system       = false', '  scale_solvent_vdw   = 0.75',
        f'  solvent             = {solvent}', '}', '',
        'assign_forcefield {', f'  forcefield = {forcefield}', f'  water      = {solvent}', '}', '']
    msj = os.path.join(wd, job + ".msj")
    try:
        os.makedirs(wd, exist_ok=True)
        with open(msj, "w") as fh:
            fh.write("\n".join(build) + "\n")
    except OSError as e:
        return {"error": f"could not write msj {msj!r}: {e}"}
    argv = [_driver("multisim"), "-JOBNAME", job, "-m", os.path.basename(msj),
            "-o", os.path.basename(out_cms), input_mae, "-HOST", "localhost"]
    res = _submit_async(argv, cwd=wd, timeout=timeout_s)
    res["msj"] = msj
    res["membrane"] = membrane
    res["expected_out_cms"] = out_cms
    return res


# ============================================================================
# ==== APPENDED TOOL GROUP: g07_gpu ====
# ============================================================================

# IMPORTS: import hashlib
#
# GROUP g07_gpu — Multi-GPU job-server pool + Linux license cure.
# Both tools are driver/_exec/filesystem tools that use ONLY server-built values:
#   - schrodinger_gpu_pool pins a GPU via _exec(..., env={"CUDA_VISIBLE_DEVICES": <int>}),
#     the int built server-side from a validated 0..63 index (never a client string).
#   - install_cure enables the SLM license path by setting SCHRODINGER_FEATURE_FLAGS to a
#     SERVER-CONSTANT value (+SCHRODINGER_LICENSE_MANAGER) on the server process env, so every
#     subsequent Schrodinger _exec child inherits it (this is the PROVEN mechanism — a feature
#     ENV VAR, verified in _schrod_env() + every licadmin diagnostic line, NOT a CLI utility).
# Both env keys are in server.py's _ENV_OVERLAY_ALLOW. Neither tool ever routes a CLIENT value
# into a child environment. Both need the Linux multi-GPU install; on this Windows dev host they
# are argv/flow-verified only. Only new server.py import required: `import hashlib`
# (install_cure md5 guard). glob/shutil/tempfile/subprocess/os/re and the module-level
# _JOBID_RE regex are already present in server.py.


# ---------- multi-GPU job-server pool (one CVD-pinned jobserverd per GPU) ----------
# Root cause (PROVEN on a 4xH100 box via /proc/<pid>/environ): the SHARED local jobserverd
# spawns every GPU subjob in its OWN environment, which carries NO CUDA_VISIBLE_DEVICES ->
# all subjobs fall back to physical GPU 0. A driver-level CVD does NOT survive the job server,
# and the modern jobserverd ignores hosts-file `gpgpu:` entries. Fix: stand up ONE jobserverd
# per GPU, each STARTED with CVD=<i> pinned, each in its own server directory; then route a job
# at LAUNCH time by pointing the GLOBAL-DEFAULT server dir at that GPU's dir (the client picks
# its server from the default at connect), exec the job with CVD=<i>, and restore the default
# dir. (SCHRODINGER_JOBSERVER_CONFIG_FILE is a SERVER var, not client routing -> setting it on
# a job breaks user-cert; hence the `jsc local-server-dir --set`/restore dance rather than a
# per-job config.) Proven + productionized: memory note "Schrodinger multi-GPU on one node",
# tool schrod-gpu-pool.sh (PR #79).

@mcp.tool()
def schrodinger_gpu_pool(action: str = "status", gpus: int = 0, gpu: int = -1,
                         argv: list = None, pool_dir: str = "", default_dir: str = "",
                         cwd: str = "", timeout_s: int = 300) -> dict:
    """Multi-GPU job-server pool: one CUDA_VISIBLE_DEVICES-pinned local jobserverd per GPU - the
    proven cure for 'every Desmond/BPMD subjob lands on GPU0' on a shared job server. Actions:
      'start' (gpus=N): stand up N per-GPU servers - for i in 0..N-1 run `jsc local-server-dir
        --set <pool_dir>/js_gpu<i>` then `jsc local-server-start` with env CVD=<i>; restore the
        default dir after.
      'submit' (gpu=<i>, argv=[...]): route ONE job to GPU i - set that GPU's server dir, `_exec
        (argv, env=CVD=i)` (in `cwd` if given), then restore the default dir. Pass a jobcontrol
        launcher that SELF-SUBMITS (returns once handed to the server); a -WAIT / JobDJ launcher
        instead occupies this call for its whole runtime. argv is a free-form command list run
        WITHOUT a shell (flags like -HOST/-WAIT are legitimate), validated as non-empty
        null-free strings; the path params (pool_dir/default_dir/cwd) go through _safe_path.
      'status' | 'stop': per-GPU server status / stop over the discovered <pool_dir>/js_gpu* dirs.
    `pool_dir` holds the per-GPU server dirs (default <tmp>/sch_gpu_pool). `default_dir` pins the
    restore target (else best-effort captured from `jsc local-server-dir`; pass it explicitly for a
    deterministic restore). Consumes NO license token itself (the submitted job consumes whatever it
    consumes). For FEP+ prefer `multisim -maxjob N` (self-assigns GPUs); use this pool for BPMD /
    anything JobDJ-based. NOTE: needs the Linux multi-GPU box - argv/flow-verified only on this host."""
    if action not in ("start", "submit", "status", "stop"):
        return {"error": "action must be start|submit|status|stop"}
    jsc = _driver("jsc")
    try:
        base = _safe_path(pool_dir) if pool_dir else os.path.join(tempfile.gettempdir(), "sch_gpu_pool")
        restore_to = _safe_path(default_dir) if default_dir else ""
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    step_to = max(30, min(int(timeout_s), 180))  # bound per-jsc control ops

    def _curdir():
        """Best-effort capture of the current global-default server dir (a path token in output)."""
        try:
            c = _exec([jsc, "local-server-dir"], timeout=60)
        except (subprocess.TimeoutExpired, OSError):
            return ""
        for tok in ((c.stdout or "") + " " + (c.stderr or "")).replace("\n", " ").split():
            if os.path.isdir(tok):
                return tok
        return ""

    def _set(d):
        """Point the global-default server dir at `d`. Best-effort; None if jsc is unavailable."""
        try:
            return _exec([jsc, "local-server-dir", "--set", d], timeout=60)
        except (subprocess.TimeoutExpired, OSError):
            return None

    def _restore(orig):
        if orig:
            try:
                _exec([jsc, "local-server-dir", "--set", orig], timeout=60)
            except (subprocess.TimeoutExpired, OSError):
                pass

    def _warn(orig):
        return None if orig else ("could not capture the original default server dir; pass "
                                  "default_dir= to guarantee a deterministic restore")

    if action == "start":
        n = int(gpus)
        if not 1 <= n <= 64:
            return {"error": "start requires gpus=N in 1..64"}
        os.makedirs(base, exist_ok=True)
        orig = restore_to or _curdir()
        servers = []
        try:
            for i in range(n):
                d = os.path.join(base, "js_gpu%d" % i)
                os.makedirs(d, exist_ok=True)
                sset = _set(d)  # route the global default at this GPU's dir before starting it
                try:
                    sstart = _exec([jsc, "local-server-start"], timeout=step_to,
                                   env={"CUDA_VISIBLE_DEVICES": str(i)})
                except (subprocess.TimeoutExpired, OSError) as e:
                    servers.append({"gpu": i, "dir": d,
                                    "set_rc": sset.returncode if sset else None,
                                    "error": "jsc local-server-start failed: %s" % e})
                    continue
                blob = (sstart.stdout or "") + (sstart.stderr or "")
                up = any(k in blob.lower() for k in ("available", "started", "running"))
                servers.append({"gpu": i, "dir": d,
                                "set_rc": sset.returncode if sset else None,
                                "start_rc": sstart.returncode, "up": up, "start_tail": blob[-400:]})
        finally:
            _restore(orig)
        return {"action": "start", "pool_dir": base, "n": n, "servers": servers,
                "restored_default": orig or None, "restore_warning": _warn(orig), "os": os.name}

    if action == "submit":
        g = int(gpu)
        if not 0 <= g <= 63:
            return {"error": "submit requires gpu in 0..63"}
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
            return {"error": "submit requires argv=[non-empty strings] (the full job command)"}
        if any("\x00" in x or "\r" in x or "\n" in x for x in argv):
            return {"error": "unsafe control char (null/newline) in argv"}
        try:
            job_cwd = _safe_path(cwd, must_exist=True) if cwd else None
        except (ValueError, FileNotFoundError) as e:
            return {"error": str(e)}
        d = os.path.join(base, "js_gpu%d" % g)
        if not os.path.isdir(d):
            return {"error": "no server dir for gpu %d at %s - run action='start' first" % (g, d)}
        orig = restore_to or _curdir()
        p, err = None, None
        try:
            _set(d)  # route the global default at GPU g's server before the job connects
            p = _exec(argv, timeout=int(timeout_s), cwd=job_cwd,
                      env={"CUDA_VISIBLE_DEVICES": str(g)})
        except subprocess.TimeoutExpired:
            err = ("job did not return within %ss - a -WAIT/JobDJ launcher blocks this call; "
                   "pass a self-submitting jobcontrol launcher instead" % timeout_s)
        except OSError as e:
            err = "could not launch job (argv[0]=%r): %s" % (argv[0], e)
        finally:
            _restore(orig)  # restore ALWAYS, even on error; the job stays on its server
        if err or p is None:
            return {"action": "submit", "gpu": g, "server_dir": d, "error": err or "job did not run",
                    "restored_default": orig or None, "restore_warning": _warn(orig)}
        blob = (p.stdout or "") + "\n" + (p.stderr or "")
        m = _JOBID_RE.search(blob)
        return {"action": "submit", "gpu": g, "server_dir": d, "returncode": p.returncode,
                "jobid": m.group(1) if m else None, "restored_default": orig or None,
                "restore_warning": _warn(orig), "stdout_tail": (p.stdout or "")[-1000:],
                "stderr_tail": (p.stderr or "")[-1000:]}

    # status | stop: iterate the discovered per-GPU server dirs
    pools = sorted(glob.glob(os.path.join(base, "js_gpu*")))
    orig = restore_to or _curdir()
    rows = []
    try:
        for d in pools:
            if not os.path.isdir(d):
                continue
            bn = os.path.basename(d)
            gi = bn[6:] if bn.startswith("js_gpu") else ""
            gpu_idx = int(gi) if gi.isdigit() else None
            sub = "local-server-status" if action == "status" else "local-server-stop"
            try:
                _set(d)
                r = _exec([jsc, sub], timeout=step_to)
            except (subprocess.TimeoutExpired, OSError) as e:
                rows.append({"dir": d, "gpu": gpu_idx, "error": "jsc %s failed: %s" % (sub, e)})
                continue
            blob = (r.stdout or "") + (r.stderr or "")
            row = {"dir": d, "gpu": gpu_idx, "returncode": r.returncode, "tail": blob[-400:]}
            if action == "status":
                row["running"] = "RUNNING" in blob.upper()
            rows.append(row)
    finally:
        _restore(orig)
    key = "servers" if action == "status" else "stopped"
    return {"action": action, "pool_dir": base, "n": len(rows), key: rows,
            "restored_default": orig or None, "restore_warning": _warn(orig)}


# ---------- Linux license cure (mutates the install tree; NOT the obsolete x509 hook) ----------
# PROVEN (Scaleway H100; same recipe worked on Modal + Databricks). The stock Linux
# libmmfileshared.so fails x509 cert-chain verification ("error 20: unable to get local issuer
# certificate") so SLM licensing is dead even with a valid .lic. The CURRENT minimal cure =
#   1) place 26-2.lic at $SCHRODINGER/licenses/26-2.lic,
#   2) overwrite libmmfileshared.so under $SCHRODINGER with the vendor patched build (from
#      license_tools_linux/internal/lib/; md5 a34a793bd05237c30f8cdc4ac750d290, 1080144 B - both
#      VERIFIED against the project diag logs; canonical target is $SCHRODINGER/internal/lib/,
#      glob-all is a safe superset because the md5 guard only ever writes that one verified build),
#   3) enable the SLM path via the ENV VAR SCHRODINGER_FEATURE_FLAGS=+SCHRODINGER_LICENSE_MANAGER
#      (the PROVEN mechanism - a feature env var honored by every Schrodinger launcher, seen in
#      _schrod_env()/every licadmin diagnostic; it is in _ENV_OVERLAY_ALLOW. There is NO
#      `feature_flags` CLI utility - do NOT invent one).
# shutil.copyfile ONLY (never a truncating New-Item-style create). SUPERSEDES the fragile
# root_inf.pem + trust_hook LD_PRELOAD + sitecustomize monkey-patch dance (do NOT re-introduce it).

@mcp.tool()
def install_cure(patched_so: str, license_file: str = "", timeout_s: int = 120) -> dict:
    """Linux Schrodinger license cure (MUTATES the install tree). (1) Overwrites libmmfileshared.so
    under $SCHRODINGER with the vendor patched build (md5 a34a793bd05237c30f8cdc4ac750d290, 1080144 B)
    that resolves the x509 cert chain the stock Linux lib fails (error 20); (2) optionally places
    `license_file` at $SCHRODINGER/licenses/26-2.lic; (3) enables the SLM license path by setting the
    SCHRODINGER_FEATURE_FLAGS=+SCHRODINGER_LICENSE_MANAGER environment variable on THIS server process
    (a SERVER-constant value; inherited by every subsequent Schrodinger _exec child - the proven
    mechanism, NOT a CLI utility). Uses shutil.copyfile + chmod 755 (NEVER a truncating create) and
    REFUSES to run unless `patched_so` matches the known-good md5+size (guards against deploying an
    unverified binary onto the install tree). The .so cure is Linux-only (Windows uses
    libmmfileshared.dll -> finds none); the .lic + feature-flag steps apply cross-platform. No license
    token. Idempotent (targets already at the good md5 are re-chmod'd, not re-copied). Best-effort
    self-validation via `licadmin debug-sources` (err=None means cured). Returns
    {found, patched, already_cured, feature_flags_env, license_check_tail, ...}."""
    good_md5, good_size = "a34a793bd05237c30f8cdc4ac750d290", 1080144
    try:
        patched_so = _safe_path(patched_so, must_exist=True)
        lic = _safe_path(license_file, must_exist=True) if license_file else ""
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}

    def _md5(path):
        try:
            h = hashlib.md5()
        except ValueError:  # hardened/FIPS build
            h = hashlib.md5(usedforsecurity=False)
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    # Guard: never deploy an unverified binary onto the install tree.
    try:
        src_md5, src_size = _md5(patched_so), os.path.getsize(patched_so)
    except OSError as e:
        return {"error": "cannot read patched_so: %s" % e}
    if src_md5 != good_md5 or src_size != good_size:
        return {"error": ("patched_so failed the good-md5 guard: got md5=%s size=%s, expected md5=%s "
                          "size=%s - refusing to deploy" % (src_md5, src_size, good_md5, good_size))}

    result = {"os": os.name, "schrodinger": SCHRODINGER, "good_md5": good_md5}

    # 1) place the license (optional; non-truncating copy)
    if lic:
        try:
            lic_dir = os.path.join(SCHRODINGER, "licenses")
            os.makedirs(lic_dir, exist_ok=True)
            dst = os.path.join(lic_dir, "26-2.lic")
            shutil.copyfile(lic, dst)
            result["license_placed"] = dst
        except OSError as e:
            result["license_error"] = str(e)
    else:
        result["license_placed"] = None

    # 2) overwrite libmmfileshared.so under $SCHRODINGER (canonical target internal/lib/; glob-all
    #    catches any other bundled copy - safe because the md5 guard only ever writes the one build)
    targets = glob.glob(os.path.join(SCHRODINGER, "**", "libmmfileshared.so"), recursive=True)
    patched, already, failed = [], [], []
    for t in targets:
        try:
            if os.path.abspath(t) == os.path.abspath(patched_so):
                continue  # never copy the source onto itself
            if os.path.isfile(t) and _md5(t) == good_md5:
                os.chmod(t, 0o755)
                already.append(t)
                continue
            shutil.copyfile(patched_so, t)  # copyfile writes full content in place; never truncate-create
            os.chmod(t, 0o755)
            patched.append(t)
        except OSError as e:
            failed.append({"path": t, "error": str(e)})
    result.update({"found": len(targets), "patched": patched, "already_cured": already, "failed": failed})

    # 3) enable the SLM license path via the SCHRODINGER_FEATURE_FLAGS env var (PROVEN mechanism, not
    #    a CLI utility). Merge +SCHRODINGER_LICENSE_MANAGER into any existing value (dropping a
    #    contradictory -SCHRODINGER_LICENSE_MANAGER) and set it on this server process, so every
    #    subsequent Schrodinger _exec child inherits it. The key is in _ENV_OVERLAY_ALLOW.
    flag = "SCHRODINGER_LICENSE_MANAGER"
    prev = os.environ.get("SCHRODINGER_FEATURE_FLAGS", "")
    toks = [tok for tok in re.split(r"[\s,]+", prev) if tok and tok.lstrip("+-") != flag]
    toks.append("+" + flag)
    new_val = " ".join(toks)
    os.environ["SCHRODINGER_FEATURE_FLAGS"] = new_val
    result["feature_flag"] = "+" + flag
    result["feature_flags_env_prev"] = prev or None
    result["feature_flags_env"] = new_val

    # optional self-validation (vault: `licadmin debug-sources` -> err=None). Best-effort; never fatal.
    # Runs with the just-set env var inherited, so it exercises the SLM path the cure enables.
    try:
        lc = _exec([_driver("licadmin"), "debug-sources"], timeout=timeout_s)
        result["licadmin_rc"] = lc.returncode
        result["license_check_tail"] = ((lc.stdout or "") + (lc.stderr or ""))[-800:]
    except subprocess.TimeoutExpired:
        result["license_check_error"] = "licadmin debug-sources timeout after %ss" % timeout_s
    except OSError as e:
        result["license_check_error"] = "licadmin not runnable: %s" % e

    if not targets:
        result["note"] = ("no libmmfileshared.so under $SCHRODINGER - the .so cure is Linux-only "
                          "(Windows uses libmmfileshared.dll); .lic + feature flag still applied")
    return result


# ============================================================================
# ==== APPENDED TOOL GROUP: g08_bpmd ====
# ============================================================================

# IMPORTS: (none new) — uses os / re / _run / _jobname / _safe_path / _submit_async,
#          all already defined in server.py (re at module top; _jobname at ~L705).
#
# GROUP g08_bpmd — Binding Pose Metadynamics (the pose-stability tier between Glide and FEP+).
#
# All flags below were INDEPENDENTLY re-verified by the reviewer against the on-disk 2026-2 driver
# argparse (NOT trusted from the generator note): the psp product IS installed even though the
# Desmond compute engine is not.
#   Driver:  $SCHRODINGER/psp-v8.4/lib/Windows-x64/python_packages/schrodinger_psp/
#            binding_pose_metadynamics.py
#   - positional `struct_file`, nargs="+" (complex .mae / pre-equilibrated .cms)   (L463-465)
#   - `-ligand_asl` is REQUIRED (required=True)                                     (L476-478)
#   - trials flag is `-ntrial` (default 10, min 1), NOT `-NUM_TRIALS`               (L519-522)
#   - `-md_host` / `-md_nproc` were REMOVED → use `-SUBHOST HOST:NPROC` for GPU     (L482-493)
#   - the driver's OWN usage string is the launch contract:                         (L52)
#       `$SCHRODINGER/run -FROM psp <script> <input complexes> -HOST <CPU> -SUBHOST <GPU>`
#   - entry point is an ExecuteParallel jobcontrol launcher: `.launch(sys.argv[1:])`(L2732-33)
#       → submitting WITHOUT -WAIT prints "JobId: <id>" and returns → _submit_async is correct.
#   - output `<jobname>-out.maegz` (L1347) + `<jobname>-out.csv` (L1197)
#   - ct properties written: r_psp_MetadynamicsBinding_PoseScore (L1323),
#       _Persistence (L1513, base name), _CompScore (L1331) — all real.
#   - CompScore documented as `PoseScore - 5 * Persistence`, lower=more stable      (L62-65).
#       (Impl note: the code weights _HBond_Persistence specifically (L1328-1330); the tool
#        surfaces the vendor's DOCUMENTED formula string + the real property names, so this is
#        faithful — the driver computes CompScore, not this tool.)
# There is NO top-level `binding_pose_metadynamics(.exe)` launcher (checked root + utilities/),
# so `_driver()` would NOT resolve it — `_run() -FROM psp <script>.py` is the ONLY correct call.
# Desmond engine: `desmond-v8.6/` is a compatibility STUB (COPYRIGHT + compatibility/ only, no
# mdgpu/multisim binaries) → GPU subjobs cannot actually run here → argv/submit-verified only.
# NOTE: bpmd() calls _submit_async(..., env=...); see g08_bpmd.mods.md for the one-line
# `_submit_async` change that threads `env` through to the (already env-aware) `_exec`.


# ---------- Binding Pose Metadynamics (pose stability: Glide < BPMD < FEP+; GPU/Desmond) ----------

@mcp.tool()
def bpmd(pose_viewer_maegz: str, out_dir: str, ligand_asl: str, num_trials: int = 8,
         gpu: int = -1, timeout_s: int = 300) -> dict:
    """Binding Pose Metadynamics (BPMD): score docked-pose STABILITY by pushing the ligand along
    an RMSD collective variable with metadynamics - the tier BETWEEN Glide (fast static score) and
    FEP+ (rigorous, expensive). Input is a receptor+ligand complex / Glide pose-viewer (`*_pv.maegz`
    or `.mae`; a pre-equilibrated `.cms` is also accepted). `ligand_asl` is REQUIRED by the driver
    and selects the ligand atoms (e.g. 'res.ptype UNK'). ASYNC (GPU Desmond) -> {jobid}; poll
    job_status. `num_trials` (driver `-ntrial`) independent metadynamics trials run SERIALLY on one
    GPU. `gpu` >= 0 pins CUDA_VISIBLE_DEVICES for the 1-GPU-per-ligand fan-out (bpmd_ladder). On
    completion, proplister the `-out.maegz`/`-out.csv` for r_psp_MetadynamicsBinding_PoseScore
    (RMSD drift, lower=better), _Persistence (contact retention, higher=better) and _CompScore
    (= PoseScore - 5*Persistence, lower=more stable). Consumes Prime + Desmond tokens. NOTE: the
    Desmond MD engine is a compatibility stub on this host -> argv/submit-verified only."""
    try:
        pose_viewer_maegz = _safe_path(pose_viewer_maegz, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not isinstance(ligand_asl, str) or not ligand_asl.strip():
        return {"error": "ligand_asl is required (driver -ligand_asl), e.g. 'res.ptype UNK'"}
    if any(c in ligand_asl for c in "\r\n\x00"):
        return {"error": "unsafe ligand_asl (control char)"}
    if ligand_asl.strip().startswith("-"):
        # An ASL never begins with '-'; reject it so the value cannot be mistaken for a driver
        # flag when placed after -ligand_asl (defense-in-depth; there is no shell here anyway).
        return {"error": "unsafe ligand_asl (leading '-' could be parsed as a flag)"}
    nt = int(num_trials)
    if not (1 <= nt <= 100):
        return {"error": "num_trials must be between 1 and 100"}
    os.makedirs(out_dir, exist_ok=True)
    job = _jobname(pose_viewer_maegz, "_bpmd")  # regex-sanitized, <=60 chars (no raw client string)
    # positional complex FIRST (nargs="+"), then flags; -HOST = CPU launcher, -SUBHOST = GPU Desmond.
    argv = [_run(), "-FROM", "psp", "binding_pose_metadynamics.py", pose_viewer_maegz,
            "-ligand_asl", ligand_asl, "-ntrial", str(nt), "-JOBNAME", job,
            "-HOST", "localhost", "-SUBHOST", "localhost"]
    # env is SERVER-built (never a client string): the key is a constant and the value is an
    # int-cast device index. _exec allowlist-filters it via _ENV_OVERLAY_ALLOW (CUDA_VISIBLE_DEVICES).
    env = {"CUDA_VISIBLE_DEVICES": str(int(gpu))} if int(gpu) >= 0 else None
    res = _submit_async(argv, cwd=out_dir, timeout=timeout_s, env=env)
    res["jobname"] = job
    res["expected_out_maegz"] = os.path.join(out_dir, job + "-out.maegz")
    res["expected_out_csv"] = os.path.join(out_dir, job + "-out.csv")
    res["score_properties"] = ["r_psp_MetadynamicsBinding_PoseScore",
                               "r_psp_MetadynamicsBinding_Persistence",
                               "r_psp_MetadynamicsBinding_CompScore"]
    res["compscore_formula"] = "CompScore = PoseScore - 5 * Persistence (lower = more stable)"
    return res


@mcp.tool()
def bpmd_ladder(complexes: list, out_dir: str, ligand_asl: str, num_trials: int = 8,
                gpus: list = None) -> dict:
    """BPMD pose-stability ladder: fan a LIST of complexes across the GPU pool at 1 GPU per ligand.
    BPMD's `num_trials` run SERIALLY inside each job, so parallelism is at the LIGAND level - this
    submits one bpmd() job per complex and returns the per-ligand jobids; poll each with job_status
    and rank by r_psp_MetadynamicsBinding_CompScore on completion. `ligand_asl` (REQUIRED) selects
    the ligand atoms in every complex (e.g. 'res.ptype UNK'). `gpus` is an optional list of
    NON-NEGATIVE device indices (e.g. [0,1,2,3]) pinned round-robin, one per ligand; omit to let the
    local job server schedule GPUs. A bad path (or a duplicate jobname that would clobber another
    ligand's output) is captured per-ligand and does not abort the rest. Consumes Prime + Desmond
    tokens per ligand. NOTE: needs psp/Prime + a runnable Desmond engine on the GPU box (a
    compatibility stub here) -> argv/submit-verified only."""
    if not isinstance(complexes, list) or not complexes:
        return {"error": "complexes must be a non-empty list of complex/pose-viewer paths"}
    if gpus is not None and (not isinstance(gpus, list)
                             or not all(isinstance(g, int) and not isinstance(g, bool) and g >= 0
                                        for g in gpus)):
        return {"error": "gpus must be a list of non-negative integer device indices, or omitted"}
    results = []
    seen_jobnames = set()  # bpmd derives its jobname (and ALL output files) from the input basename;
    #                        two complexes sharing a basename would clobber each other's -out.maegz /
    #                        metadir when run concurrently. Refuse the duplicate instead of silently
    #                        overwriting (predictable, distinct-basename batches are unaffected).
    for i, cx in enumerate(complexes):
        gpu = gpus[i % len(gpus)] if gpus else -1
        jn = _jobname(cx, "_bpmd") if isinstance(cx, str) and cx.strip() else None
        if jn is not None and jn in seen_jobnames:
            results.append({"complex": cx, "gpu": (gpu if gpus else None), "jobid": None,
                            "jobname": jn,
                            "error": "duplicate jobname in this batch (same input basename) - would "
                                     "clobber another ligand's -out files; give it a distinct name"})
            continue
        r = bpmd(cx, out_dir, ligand_asl, num_trials=num_trials, gpu=gpu)
        if r.get("jobid") and r.get("jobname"):
            seen_jobnames.add(r["jobname"])
        results.append({"complex": cx, "gpu": (gpu if gpus else None),
                        "jobid": r.get("jobid"), "jobname": r.get("jobname"),
                        "error": r.get("error")})
    submitted = [r for r in results if r.get("jobid")]
    return {"n_complexes": len(complexes), "n_submitted": len(submitted),
            "jobids": [r["jobid"] for r in submitted], "ligands": results}


# ============================================================================
# ==== APPENDED TOOL GROUP: g09_fepup ====
# ============================================================================

# g09_fepup - FEP+ upgrade group.
# NEW @mcp.tool() for server.py: fep_absolute_binding (ABFE, DEFER-tier).
# (fep_plus is a MODIFY of the existing function -> see g09_fepup.mods.md for its replacement block;
#  do NOT append a second fep_plus here.)
#
# IMPORTS: (none new) - uses os, _driver, _safe_path, _jobname, _submit_async already in server.py.
#
# HARDENING (adversarial review 2026-07-13): driver name + every flag below RE-VERIFIED against the
# live `D:\Program Files\Schrodinger 2026-2\fep_absolute_binding.exe -h` (positional accepts a pv .mae
# OR a fmp; -HOST/-SUBHOST/-JOBNAME; -ppj default 4; -equilibration-time / -fep-sim-time exist). The
# GPU knob was switched from `-SUBHOST localhost:N` to the PROVEN `-SUBHOST localhost -ppj N` for parity
# with the hardened fep_plus: same Desmond backend, and `-SUBHOST localhost:N` pins concurrent subjobs
# to GPU 0 unless per-subjob CUDA_VISIBLE_DEVICES is set (which this wrapper's env allowlist cannot do)
# -> see the multi-GPU evidence in g09_fepup.mods.md. Default subhost_gpus=1 -> `-ppj 1`, the proven
# single-GPU form (fep_sar.py:85-86,198-199).


@mcp.tool()
def fep_absolute_binding(complex_mae: str, out_dir: str = "", subhost_gpus: int = 1,
                         timeout_s: int = 300) -> dict:
    """FEP+ ABSOLUTE binding free energy (ABFE) for a prepared receptor-ligand complex - the fallback
    when ligands cannot be joined into a relative-FEP (LOMAP) map (no shared scaffold, net-charge
    change, scaffold hop). ASYNC (GPU, long) via the P0 job-control layer -> {jobid}; poll job_status.
    `complex_mae` = a prepared pose-viewer .mae/.maegz (receptor + one or more docked ligands) OR a
    .fmp built for absolute binding. Wraps `$SCHRODINGER/fep_absolute_binding <pv> -HOST localhost
    -SUBHOST localhost -ppj N`; subhost_gpus -> -ppj (GPUs per job leg; the proven GPU knob - the
    driver default is 4, this wrapper defaults to 1 for single-GPU hosts). DEFER-tier: ABFE is
    convergence-FRAGILE - it needs a RESTRAINED, well-equilibrated complex and a long protocol (the
    driver exposes -equilibration-time and -fep-sim-time for exactly this); a raw docked pose yields a
    meaningless dG. QC the equilibration + per-window overlap BEFORE trusting any dG. NOTE: requires the
    Desmond MD engine, NOT installed on this host (see desmond_md) -> argv/submit-verified only here.
    License: each ABFE run consumes FEP+ (Desmond GPU) tokens."""
    try:
        complex_mae = _safe_path(complex_mae, must_exist=True)
        wd = _safe_path(out_dir) if out_dir else (os.path.dirname(complex_mae) or ".")
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(wd, exist_ok=True)
    job = _jobname(complex_mae, "_abfe")
    nj = max(1, int(subhost_gpus))
    argv = [_driver("fep_absolute_binding"), complex_mae, "-JOBNAME", job, "-HOST", "localhost",
            "-SUBHOST", "localhost", "-ppj", str(nj)]
    res = _submit_async(argv, cwd=wd, timeout=timeout_s)
    res["expected_out_fmp"] = os.path.join(wd, job + "_out.fmp")
    res["warning"] = ("ABFE is convergence-fragile: needs a restrained, equilibrated complex + long "
                      "protocol; QC equilibration/overlap before trusting any dG")
    return res


# ============================================================================
# ==== APPENDED TOOL GROUP: g10_composites ====
# ============================================================================

# IMPORTS: import math
#
# g10 Composites: COMPOSE tools that orchestrate the existing @mcp.tool() functions
# (glide_dock / prime_mmgbsa / qikprop_admet / ligprep / prepwizard / glide_grid / sitemap /
# pdb_fetch / run_schrodinger_python) + the g10 _sch_helper commands (cns_mpo / pv_scores /
# write_subset / enumerate_analogs / cluster_frames), plus a shared pure-Python
# desirability + Pareto layer. They re-USE the existing tools; they do NOT re-implement drivers.


# ---------- composite decision helpers (pure-Python; shared by the g10 composite tools) ----------

def _desir_one(x, low, high, goal="max"):
    """Derringer one-sided desirability in [0,1]. goal='max' -> higher better (0 at <=low,
    1 at >=high); goal='min' -> lower better (1 at <=low, 0 at >=high). Clamped outside the band.
    Returns None for a missing/non-numeric value."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    lo, hi = float(low), float(high)
    if lo == hi:
        good = (x <= lo) if goal == "min" else (x >= hi)
        return 1.0 if good else 0.0
    frac = max(0.0, min(1.0, (x - lo) / (hi - lo)))
    return frac if goal == "max" else (1.0 - frac)


def _desirability(row, specs):
    """Overall Derringer desirability (weighted geometric mean) for one row over
    `specs` = [(key, low, high, goal, weight), ...]. Missing values are skipped; a single 0
    desirability (a hard-failed objective) forces the overall to 0. Returns (overall, per_key)."""
    per, wsum, logsum, hard_zero = {}, 0.0, 0.0, False
    for key, low, high, goal, weight in specs:
        d = _desir_one(row.get(key), low, high, goal)
        if d is None:
            continue
        per[key] = round(d, 4)
        if d <= 0.0:
            hard_zero = True
        w = float(weight)
        wsum += w
        logsum += w * math.log(max(d, 1e-9))
    if wsum == 0.0:
        return None, per
    return (0.0 if hard_zero else round(math.exp(logsum / wsum), 4)), per


def _pareto_ranks(rows, objectives):
    """Pareto front rank per row over `objectives` = [(key, goal), ...] (goal in {'max','min'}).
    A dominates B iff A is no worse on every objective and strictly better on >=1. Rows missing any
    objective get rank None. Returns a list of ranks aligned with `rows` (1 = non-dominated)."""
    def _vec(r):
        v = []
        for key, goal in objectives:
            try:
                x = float(r.get(key))
            except (TypeError, ValueError):
                return None
            v.append(x if goal == "max" else -x)  # normalize to 'maximize'
        return v

    vecs = [_vec(r) for r in rows]
    ranks = [None] * len(rows)
    remaining = {i for i, v in enumerate(vecs) if v is not None}

    def _dom(a, b):
        return all(a[k] >= b[k] for k in range(len(a))) and any(a[k] > b[k] for k in range(len(a)))

    front = 1
    while remaining:
        cur = [i for i in remaining if not any(_dom(vecs[j], vecs[i]) for j in remaining if j != i)]
        if not cur:  # numeric-tie cycle guard
            cur = list(remaining)
        for i in cur:
            ranks[i] = front
        remaining -= set(cur)
        front += 1
    return ranks


def _present(rows, key):
    """True if any row carries a non-None value for `key` (used to drop dead objectives)."""
    return any(r.get(key) is not None for r in rows)


# ---------- result-CSV parsing (pure stdlib; no license token) ----------

def _read_csv_rows(path):
    """Read a Schrodinger result CSV into dict rows (stdlib csv). [] if missing/empty."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, newline="") as fh:
            return list(_csv.DictReader(fh))
    except OSError:
        return []


def _row_id(row):
    """The molecule identifier from a result-CSV row (title/molecule/name/s_m_title), stripped."""
    for k in row:
        if k and k.strip().lower() in ("title", "molecule", "name", "s_m_title", "entry name"):
            v = (row.get(k) or "").strip()
            if v:
                return v
    return ""


def _get_num(row, *names):
    """First numeric value whose column name matches ANY of `names` (exact case-insensitive
    preferred, then substring). None if unmatched/non-numeric."""
    low = {k.lower(): k for k in row}
    for nm in names:  # exact first
        if nm.lower() in low:
            try:
                return float(row[low[nm.lower()]])
            except (TypeError, ValueError):
                pass
    for nm in names:  # then substring
        for lk, k in low.items():
            if nm.lower() in lk:
                try:
                    return float(row[k])
                except (TypeError, ValueError):
                    continue
    return None


def _mmgbsa_dg(row):
    """Prime MM-GBSA total dG_Bind from a Prime -out.csv row (avoids the *_dG_Bind_<component>
    columns by requiring an exact or 'ends-with dg_bind' match)."""
    low = {k.lower(): k for k in row}
    for exact in ("r_psp_mmgbsa_dg_bind", "mmgbsa_dg_bind"):
        if exact in low:
            try:
                return float(row[low[exact]])
            except (TypeError, ValueError):
                pass
    for lk, k in low.items():
        if lk.endswith("dg_bind"):
            try:
                return float(row[k])
            except (TypeError, ValueError):
                continue
    return None


# ---------- run_schrodinger_python JSON bridge (SiteMap parse / ASL centroid) ----------

def _rsp_json(code):
    """Run a snippet via run_schrodinger_python and return the last JSON object it printed."""
    res = run_schrodinger_python(code, timeout_s=300)
    if res.get("error"):
        return {"error": res["error"]}
    for line in reversed((res.get("stdout") or "").splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {"error": "no JSON from snippet", "stdout_tail": (res.get("stdout") or "")[-800:],
            "stderr_tail": (res.get("stderr") or "")[-800:]}


def _centroid_from_asl(structure_file, asl):
    """Centroid [x,y,z] of the atoms matched by `asl` in `structure_file` (via the suite)."""
    code = (
        "import json\n"
        "from schrodinger import structure\n"
        "from schrodinger.structutils.analyze import evaluate_asl\n"
        "st = next(structure.StructureReader(%r))\n"
        "idx = evaluate_asl(st, %r)\n"
        "if not idx:\n"
        "    print(json.dumps({'error': 'asl matched 0 atoms'}))\n"
        "else:\n"
        "    xs=[st.atom[i].x for i in idx]; ys=[st.atom[i].y for i in idx]; zs=[st.atom[i].z for i in idx]\n"
        "    c=[sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs)]\n"
        "    print(json.dumps({'center':[round(v,4) for v in c],'n_atoms':len(idx)}))\n"
    ) % (structure_file, asl)
    return _rsp_json(code)


def _sitemap_pockets(site_out_maegz):
    """Rank SiteMap pockets from its *_out.maegz: SiteScore, Dscore, volume + site-point centroid
    (the grid-box centre). Reads structure properties via the suite interpreter."""
    code = (
        "import json\n"
        "from schrodinger import structure\n"
        "pk=[]\n"
        "for i, st in enumerate(structure.StructureReader(%r)):\n"
        "    ss = st.property.get('r_sitemap_SiteScore')\n"
        "    if ss is None:\n"
        "        continue\n"
        "    xs=[a.x for a in st.atom]; ys=[a.y for a in st.atom]; zs=[a.z for a in st.atom]\n"
        "    c=[sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs)] if xs else None\n"
        "    ds=st.property.get('r_sitemap_Dscore'); vol=st.property.get('r_sitemap_volume')\n"
        "    pk.append({'site': i+1, 'site_score': round(float(ss),3),\n"
        "               'dscore': (round(float(ds),3) if ds is not None else None),\n"
        "               'volume': (round(float(vol),2) if vol is not None else None),\n"
        "               'center': [round(v,4) for v in c] if c else None})\n"
        "pk.sort(key=lambda d: d['site_score'], reverse=True)\n"
        "print(json.dumps({'pockets': pk}))\n"
    ) % (site_out_maegz,)
    return _rsp_json(code)


# ---------- g10 composite tools ----------

@mcp.tool()
def dock_triage(grid_file: str, ligands_mae: str, out_dir: str = "", funnel: list = None,
                keep_frac: list = None, admet: bool = True, timeout_s: int = 3600) -> dict:
    """COMPOSE funnel-docking + multi-objective triage. Docks a PREPARED ligand set (.mae, unique
    titles) through HTVS->SP->XP, keeping the top `keep_frac` by Glide gscore between tiers (writing
    the reduced set forward), then Prime MM-GBSA (dG_Bind) + QikProp ADMET on the survivors, and
    ranks by a Derringer desirability AND a Pareto non-dominated set over {dG_Bind(min),
    CNS-MPO(max), QED(max), QPlogHERG(max), QPPMDCK|QPlogBB(max)}. Calls glide_dock/prime_mmgbsa/
    qikprop_admet (each consumes a license token). `funnel` default ['HTVS','SP','XP']; `keep_frac`
    default [0.3,0.5] (one per non-final tier; reused/truncated to fit). Returns ranked hits +
    Pareto ranks + per-tier survivor counts + artifact paths. NOTE: orchestration + parsing +
    ranking are self-contained; end-to-end needs a Glide grid and Prime/QikProp tokens."""
    funnel = [str(f) for f in (funnel or ["HTVS", "SP", "XP"])]
    try:  # coerce here so a bad/empty keep_frac fails cleanly, never IndexErrors on keep_frac[-1]
        keep_frac = [float(x) for x in (keep_frac if keep_frac else [0.3, 0.5])]
    except (TypeError, ValueError):
        return {"error": "keep_frac must be a list of numbers in [0,1]"}
    for pr in funnel:
        if pr not in ("HTVS", "SP", "XP"):
            return {"error": "funnel tiers must be HTVS|SP|XP, got %r" % pr}
    try:
        grid_file = _safe_path(grid_file, must_exist=True)
        ligands_mae = _safe_path(ligands_mae, must_exist=True)
        wd = _safe_path(out_dir) if out_dir else (os.path.dirname(ligands_mae) or ".")
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(wd, exist_ok=True)

    tiers, warnings = [], []
    current, last_poses, n_input = ligands_mae, None, None
    for ti, precision in enumerate(funnel):
        dk = glide_dock(grid_file, current, precision=precision, timeout_s=timeout_s)
        poses = dk.get("poses")
        if not poses:
            tiers.append({"precision": precision, "input": current, "error": "no poses from glide_dock",
                          "returncode": dk.get("returncode"), "docking_status": dk.get("docking_status"),
                          "stderr_tail": dk.get("stderr_tail")})
            return {"error": "glide_dock produced no poses at tier %s" % precision, "tiers": tiers}
        sc = _helper("pv_scores", {"pose_file": poses})
        scores = sc.get("scores", {})
        last_poses = poses
        if n_input is None:
            n_input = len(scores)
        tier = {"precision": precision, "input": current, "poses": poses, "n_docked": len(scores)}
        if ti == len(funnel) - 1:  # final tier - no reduction
            tier["survivors"], tier["n_survivors"] = list(scores.keys()), len(scores)
            tiers.append(tier)
            break
        frac = min(1.0, max(0.0, keep_frac[ti] if ti < len(keep_frac) else keep_frac[-1]))
        ordered = sorted(scores.items(), key=lambda kv: kv[1])  # ascending gscore = better first
        k = max(1, int(round(len(ordered) * frac))) if ordered else 0
        keep_titles = [t for t, _ in ordered[:k]]
        reduced = os.path.join(wd, "triage_tier%d_%s_survivors.mae" % (ti + 1, precision))
        ws = _helper("write_subset", {"src": ligands_mae, "titles": keep_titles, "dst": reduced})
        tier.update({"keep_frac": frac, "n_survivors": len(keep_titles),
                     "survivors": keep_titles[:50], "survivor_file": ws.get("dst")})
        tiers.append(tier)
        if not ws.get("n_written"):
            return {"error": "failed to write survivor set after tier %s" % precision,
                    "tiers": tiers, "write_subset": ws}
        current = reduced

    survivor_titles = tiers[-1].get("survivors") or []
    survivor_file = current  # small-molecule ligand file fed to the final tier

    dG = {}
    mm = prime_mmgbsa(last_poses, timeout_s=timeout_s)
    for row in _read_csv_rows(mm.get("csv")):
        tid = _row_id(row)
        if tid:
            dG[tid] = _mmgbsa_dg(row)
    if not dG:
        warnings.append("Prime MM-GBSA returned no dG rows (csv=%r)" % mm.get("csv"))

    mpo = _helper("cns_mpo", {"structure_file": survivor_file})
    mpo_by = {m.get("title"): m for m in mpo.get("molecules", []) if m.get("title")}
    if mpo.get("error"):
        warnings.append("cns_mpo helper: %s" % mpo["error"])

    admet_by, admet_csv = {}, None
    if admet:
        qp = qikprop_admet(survivor_file, timeout_s=timeout_s)
        admet_csv = qp.get("csv")
        for row in _read_csv_rows(admet_csv):
            tid = _row_id(row)
            if tid:
                admet_by[tid] = row
        if not admet_by:
            warnings.append("QikProp returned no rows (csv=%r)" % admet_csv)

    rows = []
    for t in survivor_titles:
        m, ar = mpo_by.get(t, {}), admet_by.get(t, {})
        cmax = m.get("cns_mpo_max") or 5.0
        row = {"title": t, "dG_Bind": dG.get(t), "cns_mpo": m.get("cns_mpo"),
               "cns_mpo_norm": round(m["cns_mpo"] / cmax, 3) if m.get("cns_mpo") is not None else None,
               "qed": m.get("qed"), "smiles": m.get("smiles"),
               "QPlogHERG": _get_num(ar, "QPlogHERG") if ar else None,
               "QPPMDCK": _get_num(ar, "QPPMDCK") if ar else None,
               "QPlogBB": _get_num(ar, "QPlogBB") if ar else None}
        row["permeability"] = row["QPPMDCK"] if row["QPPMDCK"] is not None else row["QPlogBB"]
        rows.append(row)

    dvals = [r["dG_Bind"] for r in rows if r["dG_Bind"] is not None]
    if len(dvals) >= 2:
        dlo, dhi = min(dvals), max(dvals)
        dhi = dhi + 0.05 * max(1e-6, dhi - dlo)  # keep the worst row off an exact hard-zero
    else:
        dlo, dhi = -60.0, -10.0
    perm_mdck = any(r["QPPMDCK"] is not None for r in rows)
    perm_spec = ("permeability", 25.0, 500.0, "max", 1.0) if perm_mdck else \
                ("permeability", -3.0, 1.0, "max", 1.0)
    specs = [("dG_Bind", dlo, dhi, "min", 2.0), ("cns_mpo_norm", 0.4, 1.0, "max", 1.0),
             ("qed", 0.3, 0.9, "max", 1.0)]
    pobjs = [("dG_Bind", "min"), ("cns_mpo_norm", "max"), ("qed", "max")]
    if admet:
        specs += [("QPlogHERG", -7.0, -5.0, "max", 1.0), perm_spec]
        pobjs += [("QPlogHERG", "max"), ("permeability", "max")]
    specs = [s for s in specs if _present(rows, s[0])]
    pobjs = [o for o in pobjs if _present(rows, o[0])]

    for r in rows:
        overall, per = _desirability(r, specs)
        r["desirability"], r["desirability_components"] = overall, per
    if pobjs:
        for r, pr in zip(rows, _pareto_ranks(rows, pobjs)):
            r["pareto_rank"] = pr
    rows.sort(key=lambda r: (r.get("desirability") is None, -(r.get("desirability") or 0.0)))

    return {"funnel": funnel, "keep_frac": keep_frac, "n_input": n_input,
            "tiers": [{k: v for k, v in t.items() if k != "survivors"} for t in tiers],
            "final_poses": last_poses, "mmgbsa_csv": mm.get("csv"), "qikprop_csv": admet_csv,
            "survivor_file": survivor_file, "n_ranked": len(rows),
            "pareto_objectives": [o[0] for o in pobjs],
            "pareto_front": [r["title"] for r in rows if r.get("pareto_rank") == 1],
            "cns_mpo_note": mpo.get("note"), "warnings": warnings, "ranked_hits": rows}


@mcp.tool()
def prep_target(pdb_or_file: str, out_dir: str, ref_ligand: str = "", ph: float = 7.0,
                pocket: int = 0, inner_box: int = 10, outer_box: int = 30,
                timeout_s: int = 1800) -> dict:
    """COMPOSE receptor prep -> ready-to-dock Glide grid. pdb_fetch (if `pdb_or_file` is a 4-char
    PDB id, else a local .pdb/.mae) -> prepwizard (@ pH, QC from returncode/log) -> pocket centring:
    if `ref_ligand` (an ASL, e.g. 'res.num 501' or 'chain.name A and res.num 145') is given the grid
    centres on it (centroid via run_schrodinger_python); otherwise sitemap ranks druggable pockets
    and the top one (or 1-based `pocket`) is auto-selected and its site-point centroid used ->
    glide_grid at that centre. Returns {prepared_mae, grid_zip, chosen_center, pocket_ranking,
    prep_qc}. Consumes prepwizard/SiteMap/Glide tokens. NOTE: the SiteMap parse uses the shipped
    r_sitemap_SiteScore/Dscore property names but the sitemap tool is itself untested here -
    validate the first pocket pick."""
    try:
        out_dir = _safe_path(out_dir)
    except ValueError as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)

    pid = (pdb_or_file or "").strip()
    if len(pid) == 4 and pid.isalnum():
        fetched = pdb_fetch(pid, out_dir, fmt="pdb")
        if fetched.get("error"):
            return {"error": "pdb_fetch failed: %s" % fetched["error"], "url": fetched.get("url")}
        raw = fetched.get("pdb_path")
    else:
        try:
            raw = _safe_path(pdb_or_file, must_exist=True)
        except (ValueError, FileNotFoundError) as e:
            return {"error": str(e)}

    prepared = os.path.join(out_dir, "prepared_receptor.mae")
    pw = prepwizard(raw, prepared, ph=ph, timeout_s=timeout_s)
    if not pw.get("output"):
        return {"error": "prepwizard produced no output", "prepwizard": pw, "raw_structure": raw}
    prep_qc = {"returncode": pw.get("returncode"), "stdout_tail": (pw.get("stdout_tail") or "")[-800:]}

    chosen_center, pocket_ranking, site_out = None, [], None
    if ref_ligand:
        if any(c in ref_ligand for c in "\r\n\x00"):
            return {"error": "unsafe ref_ligand ASL (control char)"}
        cen = _centroid_from_asl(prepared, ref_ligand)
        if cen.get("error"):
            return {"error": "ref_ligand centroid failed: %s" % cen["error"], "prepared_mae": prepared}
        chosen_center = cen.get("center")
    else:
        sm = sitemap(prepared, out_dir, timeout_s=timeout_s)
        site_out = sm.get("out_maegz")
        if not site_out:
            return {"error": "sitemap produced no output", "sitemap": sm, "prepared_mae": prepared}
        ranked = _sitemap_pockets(site_out)
        if ranked.get("error"):
            return {"error": "sitemap parse failed: %s" % ranked["error"],
                    "prepared_mae": prepared, "sitemap_out": site_out}
        pocket_ranking = ranked.get("pockets", [])
        if not pocket_ranking:
            return {"error": "no pockets detected by sitemap", "prepared_mae": prepared,
                    "sitemap_out": site_out}
        pick = max(0, min((int(pocket) - 1) if pocket else 0, len(pocket_ranking) - 1))
        chosen_center = pocket_ranking[pick].get("center")

    if not chosen_center:
        return {"error": "could not determine a grid center", "prepared_mae": prepared,
                "pocket_ranking": pocket_ranking}

    center_str = ",".join("%.4f" % c for c in chosen_center)
    grid_zip = os.path.join(out_dir, "receptor_grid.zip")
    gg = glide_grid(prepared, grid_zip, center=center_str, inner_box=inner_box,
                    outer_box=outer_box, timeout_s=timeout_s)
    if not gg.get("grid"):
        return {"error": "glide_grid failed", "glide_grid": gg, "prepared_mae": prepared,
                "chosen_center": chosen_center}
    return {"prepared_mae": prepared, "grid_zip": gg.get("grid"), "chosen_center": chosen_center,
            "chosen_center_str": center_str, "pocket_ranking": pocket_ranking,
            "sitemap_out": site_out, "prep_qc": prep_qc, "raw_structure": raw}


@mcp.tool()
def analog_scan(hit_mae_or_smiles: str, grid_file: str, rgroups: dict, out_dir: str,
                mpo_norm_min: float = 0.7, precision: str = "SP", pkas: dict = None,
                timeout_s: int = 3600) -> dict:
    """COMPOSE R-group SAR scan. `hit_mae_or_smiles` must be a CORE SMILES carrying attachment
    dummies [*:1],[*:2],... (a bare hit has no defined R-group positions). Enumerates analogs across
    `rgroups` (map-number str -> [substituent SMILES]) via RDKit, applies a CNS-MPO filter
    (normalized 0-1 >= `mpo_norm_min`; the all-H parent is always kept as the ddG reference), then
    ligprep -> glide_dock -> prime_mmgbsa, ranks ddG_Bind vs the parent, and summarizes each
    substituent's mean/best effect per position. `pkas` (title->pKa) refines CNS-MPO ClogD. Calls
    ligprep/glide_dock/prime_mmgbsa (token cost). Returns {ranked_analogs, rgroup_sar, parent_dG,
    n_enumerated, n_passed_mpo, artifacts}. NOTE: enumeration + parsing are self-contained;
    end-to-end needs a Glide grid + tokens."""
    if precision not in ("HTVS", "SP", "XP"):
        return {"error": "precision must be HTVS, SP, or XP"}
    if not isinstance(rgroups, dict) or not rgroups:
        return {"error": "rgroups must be a non-empty dict {mapnum: [substituent SMILES]}"}
    core = (hit_mae_or_smiles or "").strip()
    if "[*:" not in core:
        return {"error": "provide a CORE SMILES with attachment dummies [*:1],[*:2],... "
                         "(a bare hit structure has no defined R-group positions)"}
    try:
        grid_file = _safe_path(grid_file, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)

    enum = _helper("enumerate_analogs", {"core_smiles": core, "rgroups": rgroups})
    if enum.get("error"):
        return {"error": "enumeration failed: %s" % enum["error"]}
    mols = enum.get("molecules", [])
    if not mols:
        return {"error": "enumeration produced no molecules"}

    mpo = _helper("cns_mpo", {"smiles_list": [m["smiles"] for m in mols],
                              "titles": [m["title"] for m in mols],
                              "pkas": pkas or {}, "mpo_norm_min": float(mpo_norm_min)})
    mpo_by = {m.get("title"): m for m in mpo.get("molecules", []) if m.get("title")}
    passed = []
    for m in mols:
        info = mpo_by.get(m["title"], {})
        norm = None
        if info.get("cns_mpo") is not None and info.get("cns_mpo_max"):
            norm = info["cns_mpo"] / info["cns_mpo_max"]
        m["cns_mpo"] = info.get("cns_mpo")
        m["cns_mpo_norm"] = round(norm, 3) if norm is not None else None
        if m.get("is_parent") or (norm is not None and norm >= float(mpo_norm_min)):
            passed.append(m)
    if not any(p.get("is_parent") for p in passed):
        return {"error": "parent molecule was not enumerated - cannot compute ddG reference",
                "n_enumerated": len(mols)}
    if len(passed) < 2:
        return {"error": "no analogs passed the CNS-MPO filter (only the parent survived)",
                "n_enumerated": len(mols), "cns_mpo_note": mpo.get("note")}

    smi_path = os.path.join(out_dir, "analogs.smi")
    with open(smi_path, "w") as fh:
        for m in passed:
            fh.write("%s %s\n" % (m["smiles"], m["title"]))
    prepared = os.path.join(out_dir, "analogs_prepared.mae")
    lp = ligprep(smi_path, prepared, timeout_s=timeout_s)
    if not lp.get("output"):
        return {"error": "ligprep failed", "ligprep": lp, "smi": smi_path}

    dk = glide_dock(grid_file, lp["output"], precision=precision, timeout_s=timeout_s)
    poses = dk.get("poses")
    if not poses:
        return {"error": "glide_dock produced no poses", "glide_dock": dk, "prepared": lp["output"]}

    mm = prime_mmgbsa(poses, timeout_s=timeout_s)
    dG = {}
    for row in _read_csv_rows(mm.get("csv")):
        tid = _row_id(row)
        if tid:
            dG[tid] = _mmgbsa_dg(row)
    parent_dG = dG.get("parent")

    analogs = []
    for m in passed:
        d = dG.get(m["title"])
        ddg = (d - parent_dG) if (d is not None and parent_dG is not None) else None
        analogs.append({"title": m["title"], "smiles": m["smiles"], "rgroups": m.get("rgroups", {}),
                        "is_parent": m.get("is_parent", False), "dG_Bind": d, "ddG_Bind": ddg,
                        "cns_mpo_norm": m.get("cns_mpo_norm")})

    ddgs = [r["ddG_Bind"] for r in analogs if r["ddG_Bind"] is not None]
    if len(ddgs) >= 2:
        lo, hi = min(ddgs), max(ddgs)
        hi = hi + 0.05 * max(1e-6, hi - lo)
        aspecs = [("ddG_Bind", lo, hi, "min", 2.0), ("cns_mpo_norm", 0.4, 1.0, "max", 1.0)]
        aspecs = [s for s in aspecs if _present(analogs, s[0])]
        for r in analogs:
            r["desirability"], _ = _desirability(r, aspecs)
    analogs.sort(key=lambda r: (r["ddG_Bind"] is None, r["ddG_Bind"] if r["ddG_Bind"] is not None else 0.0))

    sar = {}
    for r in analogs:
        if r["is_parent"] or r["ddG_Bind"] is None:
            continue
        for pos, sub in (r["rgroups"] or {}).items():
            sar.setdefault(pos, {}).setdefault(sub, []).append(r["ddG_Bind"])
    rgroup_sar = {}
    for pos, subs in sar.items():
        rs = [{"substituent": sub, "n": len(v), "mean_ddG": round(sum(v) / len(v), 3),
               "best_ddG": round(min(v), 3)} for sub, v in subs.items()]
        rs.sort(key=lambda d: d["mean_ddG"])
        rgroup_sar[pos] = rs

    return {"n_enumerated": len(mols), "n_passed_mpo": len(passed), "parent_dG": parent_dG,
            "attachment_points": enum.get("attachment_points"), "enum_truncated": enum.get("truncated"),
            "artifacts": {"smi": smi_path, "prepared_mae": lp.get("output"), "poses": poses,
                          "mmgbsa_csv": mm.get("csv")},
            "cns_mpo_note": mpo.get("note"), "ranked_analogs": analogs, "rgroup_sar": rgroup_sar}


@mcp.tool()
def ensemble_dock(md_cms_or_states: str, ligands_mae: str, out_dir: str, n_snapshots: int = 5,
                  site_asl: str = "", precision: str = "SP", inner_box: int = 10,
                  outer_box: int = 30, timeout_s: int = 3600) -> dict:
    """COMPOSE ensemble docking. Clusters a Desmond MD trajectory (its -out.cms; its _trj is
    auto-found) by protein Ca-RMSD into `n_snapshots` representative receptor conformations, builds
    a Glide grid on each (centred on `site_asl`, default the bound non-protein ligand), docks the
    PREPARED `ligands_mae` into all snapshots, and ranks by cross-ensemble CONSENSUS (best & mean
    gscore + ensemble hit-rate, with a Pareto front over {best_gscore(min), mean_gscore(min),
    hit_rate(max)}). Calls glide_grid + glide_dock per snapshot (token cost ~ n_snapshots). Returns
    {consensus_ranking, pareto_front, snapshots, artifacts}. NOTE: the trajectory clustering uses
    the Desmond analysis packages and is API-verified only - needs a completed MD .cms + _trj to
    exercise; validate the first run."""
    if precision not in ("HTVS", "SP", "XP"):
        return {"error": "precision must be HTVS, SP, or XP"}
    try:
        md_cms = _safe_path(md_cms_or_states, must_exist=True)
        ligands_mae = _safe_path(ligands_mae, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if site_asl and any(c in site_asl for c in "\r\n\x00"):
        return {"error": "unsafe site_asl (control char)"}
    os.makedirs(out_dir, exist_ok=True)

    cargs = {"cms_file": md_cms, "n_snapshots": max(1, int(n_snapshots)), "out_dir": out_dir}
    if site_asl:
        cargs["site_asl"] = site_asl
    cl = _helper("cluster_frames", cargs, timeout=timeout_s)
    if cl.get("error"):
        return {"error": "trajectory clustering failed: %s" % cl["error"]}
    snaps = cl.get("snapshots", [])
    if not snaps:
        return {"error": "clustering produced no snapshots", "cluster": cl}

    all_scores, per_snapshot = {}, []
    for k, sn in enumerate(snaps):
        rec, center = sn.get("snapshot_mae"), sn.get("grid_center")
        entry = {"snapshot": rec, "frame_index": sn.get("frame_index"),
                 "cluster_size": sn.get("cluster_size")}
        if not rec or not center:
            entry["error"] = "missing snapshot receptor or grid center"
            per_snapshot.append(entry)
            continue
        grid_zip = os.path.join(out_dir, "ensemble_grid_%d.zip" % (k + 1))
        gg = glide_grid(rec, grid_zip, center=",".join("%.4f" % c for c in center),
                        inner_box=inner_box, outer_box=outer_box, timeout_s=timeout_s)
        if not gg.get("grid"):
            entry["error"] = "glide_grid failed"
            entry["stderr_tail"] = gg.get("stderr_tail")
            per_snapshot.append(entry)
            continue
        entry["grid"] = gg["grid"]
        dk = glide_dock(gg["grid"], ligands_mae, precision=precision, timeout_s=timeout_s)
        poses = dk.get("poses")
        entry["poses"] = poses
        if not poses:
            entry["error"] = "no poses"
            per_snapshot.append(entry)
            continue
        scores = _helper("pv_scores", {"pose_file": poses}).get("scores", {})
        entry["n_docked"] = len(scores)
        for t, s in scores.items():
            all_scores.setdefault(t, []).append(s)
        per_snapshot.append(entry)

    n_valid = sum(1 for e in per_snapshot if e.get("poses"))
    if not all_scores:
        return {"error": "no ligand scored in any snapshot", "snapshots": per_snapshot}

    rows = [{"title": t, "best_gscore": round(min(v), 4), "mean_gscore": round(sum(v) / len(v), 4),
             "n_snapshots_hit": len(v), "hit_rate": round(len(v) / max(1, n_valid), 3)}
            for t, v in all_scores.items()]
    objs = [("best_gscore", "min"), ("mean_gscore", "min"), ("hit_rate", "max")]
    for r, pr in zip(rows, _pareto_ranks(rows, objs)):
        r["pareto_rank"] = pr
    rows.sort(key=lambda r: (r["mean_gscore"], -r["hit_rate"]))

    return {"n_snapshots": len(snaps), "n_valid_snapshots": n_valid, "centers": cl.get("centers"),
            "snapshots": per_snapshot,
            "pareto_front": [r["title"] for r in rows if r.get("pareto_rank") == 1],
            "consensus_ranking": rows}


# ============================================================================
# ==== APPENDED TOOL GROUP: g11_monitor ====
# ============================================================================

# IMPORTS: import time
#
# g11_monitor — Monitor + restart.
# Append this whole block to server.py (module-level helpers + the job_restart tool).
# The modified _submit_async lives in g11_monitor.mods.md and calls _emit_progress /
# _derive_total / _predict_log defined here (resolved at call time, so append order is fine).
# The FEP edge-count helper (_fep_edges) lives in g11_monitor.helper.py (_sch_helper.py).

# ---------- taskwatch integration (progress.json heartbeat + auto-register) ----------
# taskwatch_monitor (tools/taskwatch_monitor) is the general long-task monitor. It reads a
# per-job progress.json {schema,done,total|null,phase,ts,seq} (the "progress plane") and a
# declarative [[task]] TOML registry it polls (the "liveness plane"). We EMIT the heartbeat
# and best-effort REGISTER the run so an already-running monitor picks it up. We never import
# taskwatch (it runs under its own uv venv) and never rebuild a dashboard — everything here is
# fail-open: a monitor hiccup must never break a real Schrodinger job submission.

_TASKWATCH_PROGRESS_SCHEMA = "taskwatch.progress/1"  # taskwatch core.planes.PROGRESS_SCHEMA
_TASKWATCH_STALL_S = 900  # a GPU MD/FEP leg can be quiet a while; don't cry "stalled" early
# Drivers whose Job Control log is the multisim harness log `<job>_multisim.log` (rich per-leg
# / per-window / per-trial parsing by taskwatch's fep/bpmd probes). Others log to `<job>.log`.
_MULTISIM_DRIVERS = frozenset({"fep_plus", "multisim", "watermap"})
# driver -> (taskwatch parser, eta model, task_type/history-key)
_DRIVER_WATCH = {
    "fep_plus": ("fep-databricks", "per-phase-weighted", "fep-databricks"),
    "multisim": ("generic-logfile", "ewma-throughput", "md-desmond"),
    "watermap": ("generic-logfile", "ewma-throughput", "watermap"),
    "ifd": ("generic-logfile", "linear-frac", "ifd"),
    "covalent_docking": ("generic-logfile", "linear-frac", "covdock"),
}
_DEFAULT_WATCH = ("generic-logfile", "linear-frac", "job")


def _taskwatch_registry_path() -> str:
    """Resolve the taskwatch registry TOML, or '' when taskwatch is not configured.
    Honors $TASKWATCH_REGISTRY (taskwatch's own operator knob) first, else the home
    registry when ~/.taskwatch exists. Returns '' -> auto-register is skipped (fail-open)."""
    env = os.environ.get("TASKWATCH_REGISTRY", "").strip()
    if env:
        return env
    home = os.path.join(os.path.expanduser("~"), ".taskwatch")
    if os.path.isdir(home):
        return os.path.join(home, "taskwatch.toml")
    return ""


def _toml_str(s) -> str:
    """A TOML basic string with backslashes/quotes/control-chars escaped (Windows paths safe).
    TOML basic strings forbid a literal newline/CR/tab, so escape those too: a stray control
    char in a derived path would otherwise emit invalid TOML and corrupt the whole registry."""
    return '"' + (str(s).replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")) + '"'


def _predict_log(driver: str, argv, cwd) -> str:
    """Predict the run's Job Control log path from the submit argv (no run needed).
    multisim-family drivers write `<jobname>_multisim.log`; others write `<jobname>.log`.
    Job name comes from -JOBNAME/-JOB/-j, else the first positional's stem. '' if unknown."""
    try:
        job = ""
        for flag in ("-JOBNAME", "-JOB", "-j"):
            if flag in argv:
                i = argv.index(flag)
                if i + 1 < len(argv):
                    job = str(argv[i + 1])
                    break
        if not job:
            for a in argv[1:]:  # skip the driver itself
                s = str(a)
                if not s.startswith("-"):
                    job = os.path.splitext(os.path.basename(s))[0]
                    break
        if not job:
            return ""
        suffix = "_multisim.log" if driver in _MULTISIM_DRIVERS else ".log"
        return os.path.join(cwd or ".", job + suffix)
    except Exception:
        return ""


def _derive_total(driver: str, argv, cwd):
    """Best-effort per-driver progress denominator, else None (honest: no fake %).
    FEP+ -> perturbation-edge count from the input .fmp (scisol graph API, one-shot helper).
    multisim/watermap MD -> production length in ns parsed from the -m .msj. None otherwise."""
    try:
        if driver == "fep_plus":
            fmp = next((a for a in argv[1:] if str(a).lower().endswith(".fmp")), "")
            if not fmp:
                return None  # e.g. a -RESTART resubmission carries no .fmp positional
            r = _helper("fep_edges", {"fmp": _safe_path(fmp, must_exist=True)}, timeout=90)
            e = r.get("edges")
            return float(e) if isinstance(e, int) and e > 0 else None
        if "-m" in argv:  # multisim / watermap: production time (ps) -> ns
            i = argv.index("-m")
            if i + 1 < len(argv):
                msj = os.path.join(cwd or ".", str(argv[i + 1]))
                if os.path.exists(msj):
                    with open(msj, encoding="utf-8", errors="replace") as fh:
                        txt = fh.read()
                    times = [float(x) for x in re.findall(r"\btime\s*=\s*([0-9.]+)", txt)]
                    if times:
                        return round(max(times) / 1000.0, 4)  # longest stage = production
        return None
    except Exception:
        return None


def _taskwatch_register(job_dir: str, driver: str, log_path: str) -> bool:
    """Append an observe-only [[task]] entry for this run to the taskwatch registry (idempotent).
    Rich local-file-tail on the concrete multisim log for FEP/MD/WaterMap (taskwatch's fep/bpmd
    probes parse it); robust file-exists-glob liveness for the rest. remediate stays False —
    tier-2 (auto-restart via job_restart) is opt-in via taskwatch's attach_watch, not armed here.
    Returns True when a row was written or already present; False when taskwatch is absent."""
    reg = _taskwatch_registry_path()
    if not reg:
        return False
    parser, eta, ttype = _DRIVER_WATCH.get(driver, _DEFAULT_WATCH)
    # Resolve the liveness source. For multisim-family drivers prefer a concrete log: the
    # predicted `<job>_multisim.log` on a fresh submit (appears within seconds), or the real
    # existing one on a -RESTART (where the predicted name is derived from the checkpoint).
    chosen_log = log_path if (log_path and driver in _MULTISIM_DRIVERS) else ""
    if driver in _MULTISIM_DRIVERS and (not chosen_log or not os.path.exists(chosen_log)):
        existing = sorted(glob.glob(os.path.join(job_dir, "*multisim.log")), key=os.path.getmtime)
        if existing:
            chosen_log = existing[-1]
    if driver in _MULTISIM_DRIVERS and chosen_log:
        adapter = "local-file-tail"
        cfg = "{ path = %s, stall_after_s = %d }" % (_toml_str(chosen_log), _TASKWATCH_STALL_S)
    else:
        adapter = "file-exists-glob"
        pat = "*multisim.log" if driver in _MULTISIM_DRIVERS else "*.log"
        cfg = "{ pattern = %s, stall_after_s = %d }" % (
            _toml_str(os.path.join(job_dir, pat)), _TASKWATCH_STALL_S)
    # A stable id keyed on the clean job name so a re-run / -RESTART is a dedup no-op.
    src = chosen_log or log_path
    stem = re.sub(r"[_-]multisim(_checkpoint.*)?$", "",
                  os.path.splitext(os.path.basename(src))[0]) if src else ""
    if not stem:
        stem = os.path.basename(os.path.abspath(job_dir)) or "job"
    task_id = re.sub(r"[^A-Za-z0-9_.-]", "_", "sch-%s-%s" % (driver, stem))[:80]
    try:  # idempotent: never duplicate an existing watch
        if os.path.exists(reg):
            with open(reg, encoding="utf-8") as fh:
                if "id = %s" % _toml_str(task_id) in fh.read():
                    return True
    except Exception:
        pass
    parent = os.path.dirname(reg)
    if parent:
        os.makedirs(parent, exist_ok=True)
    block = (
        "\n[[task]]\n"
        "id = %s\n" % _toml_str(task_id) +
        "adapter = %s\n" % _toml_str(adapter) +
        "parser = %s\n" % _toml_str(parser) +
        "eta_model = %s\n" % _toml_str(eta) +
        'notify = ["terminal", "first-progress", "stall"]\n'
        "task_type = %s\n" % _toml_str(ttype) +
        "config = %s\n" % cfg
    )
    with open(reg, "a", encoding="utf-8") as fh:  # single write ~ atomic for a small block
        fh.write(block)
    return True


def _emit_progress(job_dir: str, driver: str, total, log_path: str = "") -> dict:
    """Write taskwatch's progress.json heartbeat into `job_dir` and best-effort auto-register
    the run in taskwatch's registry. `total` is the driver-derived denominator (None -> the
    monitor shows liveness + elapsed, never a fabricated %). Monotonic `seq` is read back from
    any prior heartbeat and bumped so a re-emit (e.g. a -RESTART) is accepted, not rejected as
    stale. NEVER raises — a monitor error must not break a real job submission."""
    result = {"progress_json": None, "registered": False}
    try:
        job_dir = os.path.abspath(job_dir or ".")
        os.makedirs(job_dir, exist_ok=True)
        pj = os.path.join(job_dir, "progress.json")
        seq = 0
        try:
            with open(pj, encoding="utf-8") as fh:
                seq = int(json.load(fh).get("seq", -1)) + 1
        except Exception:
            seq = 0
        tot = (float(total) if isinstance(total, (int, float))
               and not isinstance(total, bool) and total > 0 else None)
        rec = {"schema": _TASKWATCH_PROGRESS_SCHEMA, "done": 0.0, "total": tot,
               "phase": "submitted", "ts": time.time(), "seq": seq}
        with open(pj, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        result["progress_json"] = pj
    except Exception:
        return result  # even the heartbeat failed -> give up quietly (fail-open)
    try:
        result["registered"] = _taskwatch_register(job_dir, driver, log_path)
    except Exception:
        pass
    return result


# ---------- job restart (taskwatch tier-2 remediation primitive) ----------

@mcp.tool()
def job_restart(jobid_or_dir: str, driver: str = "", subhost_gpus: int = 1,
                timeout_s: int = 300) -> dict:
    """Resume a died/preempted multisim-based job (fep_plus / Desmond multisim) from its
    checkpoint with -RESTART, which re-runs ONLY the incomplete stages (at most the single
    in-flight edge/leg is repeated). Pass a JobId (its run dir is resolved via job_status) OR
    the run directory directly. `driver` (fep_plus|multisim) is auto-detected from the dir/
    program when blank. ASYNC -> returns the NEW {jobid}; poll job_status. Requires a
    `*multisim_checkpoint*` in the run dir (written by the original run). This is taskwatch's
    tier-2 remediation primitive (a one-shot restart, NOT a new poll loop). NOTE: the argv
    mirrors the proven schrodinger_modal.py resume path (fep_plus -RESTART <ckpt> -HOST
    localhost -SUBHOST localhost -JOBNAME <job>); live -RESTART is checkpoint-dependent ->
    verify the first restart. FEP/MD restarts need the Desmond engine (see fep_plus/desmond_md)."""
    raw = (jobid_or_dir or "").strip()
    if not raw or raw.startswith("-"):
        return {"error": f"invalid jobid_or_dir: {jobid_or_dir!r}"}
    if driver and driver not in ("fep_plus", "multisim"):
        return {"error": "driver must be '' (auto), 'fep_plus', or 'multisim'"}
    # Resolve the run directory: a real path is used as-is; otherwise treat it as a JobId.
    job_dir = ""
    resolved_from = "dir"
    try:
        if os.path.isdir(raw):
            job_dir = _safe_path(raw, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not job_dir:
        st = _helper("job_status", {"jobid": raw}, timeout=120)
        d = st.get("dir")
        if not d or not os.path.isdir(d):
            return {"error": f"could not resolve a run directory for {raw!r}",
                    "job_status": st}
        job_dir = os.path.abspath(d)
        resolved_from = "jobid"
        if not driver and "fep" in str(st.get("program") or "").lower():
            driver = "fep_plus"
    # Find the newest multisim checkpoint (rotated `_N` copies sort by mtime).
    ckpts = sorted(glob.glob(os.path.join(job_dir, "*multisim_checkpoint*")),
                   key=os.path.getmtime)
    if not ckpts:
        return {"error": "no *multisim_checkpoint* in run dir - nothing to restart",
                "dir": job_dir}
    ckpt = ckpts[-1]
    if driver not in ("fep_plus", "multisim"):  # last-resort autodetect from the dir contents
        driver = "fep_plus" if glob.glob(os.path.join(job_dir, "*.fmp")) else "multisim"
    # Recover the original jobname from the checkpoint stem (<jobname>-multisim_checkpoint) and
    # route it through _jobname() -> sanitized -JOBNAME. Mirrors the proven schrodinger_modal.py
    # restart (which passes -JOBNAME <jobname>) and lets _predict_log name the multisim log; the
    # job name only ever reaches argv as a server-sanitized token (alnum/_/-, <=60).
    job = _jobname(re.sub(r"[_-]multisim(_checkpoint)?.*$", "", os.path.basename(ckpt)))
    # Restart re-runs only incomplete stages; run in the job dir, pass the checkpoint basename.
    argv = [_driver(driver), "-RESTART", os.path.basename(ckpt), "-HOST", "localhost"]
    if driver == "fep_plus":
        argv += ["-SUBHOST", f"localhost:{max(1, int(subhost_gpus))}"]
    argv += ["-JOBNAME", job]
    res = _submit_async(argv, cwd=job_dir, timeout=timeout_s)  # re-arms progress.json + watch
    res["restarted"] = True
    res["driver"] = driver
    res["jobname"] = job
    res["checkpoint"] = ckpt
    res["dir"] = job_dir
    res["resolved_from"] = resolved_from
    return res


# ============================================================================
# ==== APPENDED TOOL GROUP: g12_filters ====
# ============================================================================

# IMPORTS: (none new — os, re, subprocess already imported at the top of server.py; these tools
#           call the existing _safe_path/_driver/_exec/_run/_helper/_jobname/_ensure_job_server)
#
# GROUP g12_filters — library/property filters + two DEFERred license drivers.
#   ligfilter        (local, bundled mmshare utility; typically NO license token) -> both
#   propfilter       (local, pure schrodinger.structutils.filter; NO token)       -> both
#   residue_scanning (local-token, DEFER; BioLuminate/Prime; async, argv-verified) -> server.py
#   qsite_qmmm       (local-token, DEFER; QSite QM/MM; argv/template-verified)      -> server.py
#
# Adversarially reviewed + VERIFIED against the live 2026-2 install (D:\Program Files\Schrodinger
# 2026-2): ligfilter/propfilter/qsite/residue_scanning_backend flags checked against the shipped
# program_utility_usage docs + argparser source; the QSite .in template matches the shipped
# impact-v11.1/samples/qsite/{qsite.in,qsite-1tpb.in}; the -muts_file line format + -calc vocab +
# r_bioluminate_delta_* datanames match residue_scanning_backend.py / bioluminate/protein/protein.py.
#
# ligfilter/propfilter reuse the g12_filters helper `count_structures` (see g12_filters.helper.py)
# to report REAL pass/total counts without importing schrodinger in the server venv.


# ---------- ligand/structure filtering (local, CPU; bundled utilities) ----------

@mcp.tool()
def ligfilter(input_file: str, output_file: str, criteria: list, definitions: list = None,
              match_any: bool = False, invert: bool = False, nomatch_file: str = "",
              timeout_s: int = 900) -> dict:
    """Ligfilter: filter a ligand file by property / predefined / SMARTS criteria authored into a
    server-written .lff (fits no-shell — the criteria are file content, never argv). `criteria` =
    ligfilter condition lines, e.g. 'Molecular_weight 150-500', 'Num_rotatable_bonds <= 7',
    'r_i_docking_score < -8', 'Num_aromatic_rings >= 1', or a NAMED SMARTS definition + count
    ('Reactive_groups == 0'). Predefined keys: Molecular_weight, Num_atoms, Num_heavy_atoms,
    Num_rings, Num_aromatic_rings, Num_rotatable_bonds, Num_chiral_centers, Total_charge, ...
    Define custom SMARTS in `definitions` as full single-line 'DEFINE <Name> <SMARTS>' entries and
    reference <Name> in a criterion (a bare SMARTS is NOT itself a valid criterion). match_any ->
    pass if ANY criterion matches (default: ALL must match); invert -> keep the NON-matches.
    Local/CPU with -NOJOBID (no job server); bundled mmshare utility (typically no license token).
    Returns {output_file, passed, total, rejected}."""
    try:
        input_file = _safe_path(input_file, must_exist=True)
        output_file = _safe_path(output_file)
        nm = _safe_path(nomatch_file) if nomatch_file else ""
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not isinstance(criteria, list) or not criteria:
        return {"error": "criteria must be a non-empty list of ligfilter condition lines"}
    lff_lines = list(definitions or []) + list(criteria)
    for ln in lff_lines:
        # These become .lff FILE content (passed via -f), so only control chars are a hazard;
        # a leading '-' is legal .lff syntax (an exclude line inside a DEFINE) and safe here.
        if not isinstance(ln, str) or not ln.strip():
            return {"error": f"empty/invalid criteria or definitions line: {ln!r}"}
        if any(c in ln for c in "\r\n\x00"):
            return {"error": f"unsafe newline/null in .lff line: {ln!r}"}
    wd = os.path.dirname(output_file) or "."
    os.makedirs(wd, exist_ok=True)
    lff = os.path.join(wd, os.path.splitext(os.path.basename(output_file))[0] + "_ligfilter.lff")
    with open(lff, "w") as fh:
        fh.write("\n".join(lff_lines) + "\n")
    # Output resolves UNDER cwd (mirror ligprep's 8.3/short-name gotcha): run in wd, pass basenames.
    # Verified argv (2026-2 utilities/ligfilter usage): positional input_file, -f CRITERIA_FILE,
    # -o OUTPUT_FILE, -NOJOBID (run without Job Control), -any, -remove (invert), -n NOMATCH_FILE.
    argv = [_driver("ligfilter"), input_file, "-f", os.path.basename(lff),
            "-o", os.path.basename(output_file), "-NOJOBID"]
    if match_any:
        argv.append("-any")
    if invert:
        argv.append("-remove")
    nm_out = ""
    if nm:
        nm_out = os.path.join(wd, os.path.basename(nm))
        argv += ["-n", os.path.basename(nm)]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    res = {"returncode": p.returncode, "lff": lff,
           "output_file": output_file if os.path.exists(output_file) else None,
           "nomatch_file": nm_out if (nm_out and os.path.exists(nm_out)) else None,
           "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    # Real pass/total counts via the suite interpreter (StructureReader) — best-effort.
    paths = [q for q in (input_file, output_file) if os.path.exists(q)]
    if paths:
        counts = _helper("count_structures", {"paths": paths}).get("counts", {})
        res["total"] = counts.get(input_file)
        res["passed"] = counts.get(output_file)
        if isinstance(res.get("total"), int) and isinstance(res.get("passed"), int):
            res["rejected"] = res["total"] - res["passed"]
    return res


@mcp.tool()
def propfilter(input_file: str, output_file: str, expressions: list, timeout_s: int = 600) -> dict:
    """Propfilter: filter a structure file by numeric/string PROPERTY expressions (pure
    schrodinger.structutils.filter — local, CPU, NO license token). `expressions` = one or more
    filter conditions, each handed to its own -e (its own argv element, so operators/spaces are
    inert — no shell), e.g. 'r_i_glide_gscore < -8', 'MW < 500', 'MW > 300 AND < 500',
    'title ~ phenibut'. The property name is the first word (short alias MW / mol_MW, or the full
    m2io dataname r_qp_*). ALL expressions must pass (AND across the list). Returns
    {output_file, passed, total}."""
    try:
        input_file = _safe_path(input_file, must_exist=True)
        output_file = _safe_path(output_file)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not isinstance(expressions, list) or not expressions:
        return {"error": "expressions must be a non-empty list of propfilter conditions"}
    for ex in expressions:
        # -e VALUES are argv elements: reject control chars AND a flag-like leading '-'
        # (a valid expression starts with the property name, never '-').
        if not isinstance(ex, str) or not ex.strip():
            return {"error": f"empty/invalid expression: {ex!r}"}
        if ex.strip().startswith("-") or any(c in ex for c in "\r\n\x00"):
            return {"error": f"unsafe/flag-like expression: {ex!r}"}
    wd = os.path.dirname(output_file) or "."
    os.makedirs(wd, exist_ok=True)
    # Verified argv (2026-2 scripts/propfilter.py argparser): -e (append, repeatable), -o
    # OUTPUT, positional struct_file. main() filters in-process (StructureReader->Writer), so it
    # runs synchronously with no Job Control layer — no -NOJOBID/-WAIT needed.
    argv = [_driver("propfilter")]
    for ex in expressions:
        argv += ["-e", ex]
    argv += ["-o", os.path.basename(output_file), input_file]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    res = {"returncode": p.returncode,
           "output_file": output_file if os.path.exists(output_file) else None,
           "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    paths = [q for q in (input_file, output_file) if os.path.exists(q)]
    if paths:
        counts = _helper("count_structures", {"paths": paths}).get("counts", {})
        res["total"] = counts.get(input_file)
        res["passed"] = counts.get(output_file)
    return res


# ---------- BioLuminate residue scanning (DEFER; async; consumes a BioLuminate/Prime token) ----------

# One mutation token: [<chain>|_]:<resnum>[<inscode>]-><1|3-letter resname> (loop +/- prefixes ok).
# Format verified against residue_scanning_backend.py -muts_file help: e.g. 'A:24->SER A:25->R'.
_RESSCAN_MUT_RE = re.compile(r"^[A-Za-z_]?:-?\d+[A-Za-z]?->[+-]?[A-Za-z0-9]+$")
# Extra per-structure props valid for -calc, verified against the shipped 2026-2 source
# schrodinger/application/bioluminate/protein/protein.py (calculations list, ~L678/L710) plus the
# usage-doc example '-calc pka,rotatable'.
_RESSCAN_CALCS = {"e_pot", "e_internal", "e_interaction", "prime_energy", "pka",
                  "sasa_polar", "sasa_nonpolar", "sasa_total", "hydropathy",
                  "rotatable", "vdw_surf_comp"}


@mcp.tool()
def residue_scanning(complex_file: str, mutations: list, out_dir: str, calc: str = "",
                     ligand_asl: str = "", job_name: str = "resscan_job", njobs: int = 1,
                     timeout_s: int = 300) -> dict:
    """BioLuminate Residue Scanning: mutate protein residues and score the effect on STABILITY
    (delta_Stability) and, when a binding partner is defined, AFFINITY (delta_Affinity). Runs
    `$SCHRODINGER/run residue_scanning_backend.py <complex> -muts_file <server-authored list>
    -jobname <j> -HOST localhost:NJOBS [-calc ...] [-ligand_asl ...]`. Each `mutations` entry is
    ONE mutation LINE — space-separate several 'CHAIN:RESNUM->RES' tokens for a concurrent
    multi-residue mutant, e.g. 'A:24->SER A:25->R'; use '_' for a blank chain (':3'->'_:3').
    Provide `ligand_asl` (an ASL splitting receptor vs. ligand) to trigger the binding-affinity
    (dG bind) delta; omit it for stability-only. `calc` = extra per-structure props, comma-sep from
    {e_pot,e_internal,e_interaction,prime_energy,pka,sasa_polar,sasa_nonpolar,sasa_total,hydropathy,
    rotatable,vdw_surf_comp}. ASYNC -> {jobid}; poll job_status, then proplister the out .maegz for
    r_bioluminate_delta_Stability / r_bioluminate_delta_Affinity.
    NOTE: requires a BioLuminate/Prime license. The task's literal '-calc affinity,stability' is
    NOT the real interface (those deltas are computed automatically from structure type + asl);
    this uses the verified backend flags. Flags/format verified against the 2026-2 shipped backend
    — NOT runtime-tested here, so confirm the exact output filename on first run."""
    try:
        complex_file = _safe_path(complex_file, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not job_name.replace("_", "").replace("-", "").isalnum():
        return {"error": f"invalid job_name: {job_name!r}"}
    if not isinstance(mutations, list) or not mutations:
        return {"error": "mutations must be a non-empty list of 'CHAIN:RESNUM->RES' lines"}
    mut_lines = []
    for entry in mutations:
        if not isinstance(entry, str) or not entry.strip():
            return {"error": f"empty/invalid mutation entry: {entry!r}"}
        if any(c in entry for c in "\r\n\x00"):
            return {"error": f"unsafe newline/null in mutation: {entry!r}"}
        toks = entry.split()
        for t in toks:
            if not _RESSCAN_MUT_RE.match(t):
                return {"error": f"bad mutation token {t!r} (expect 'CHAIN:RESNUM->RES', e.g. 'A:24->SER')"}
        mut_lines.append(" ".join(toks))
    calc = (calc or "").strip()
    if calc:
        bad = [c for c in calc.split(",") if c.strip() not in _RESSCAN_CALCS]
        if bad:
            return {"error": f"invalid -calc token(s) {bad}; allowed: {sorted(_RESSCAN_CALCS)}"}
    if ligand_asl and any(c in ligand_asl for c in "\r\n\x00"):
        return {"error": "unsafe newline/null in ligand_asl"}
    if ligand_asl and ligand_asl.strip().startswith("-"):
        return {"error": "unsafe ligand_asl (leading '-' could be parsed as a flag)"}
    os.makedirs(out_dir, exist_ok=True)
    job = _jobname(job_name)
    muts = os.path.join(out_dir, job + "_muts.txt")
    with open(muts, "w") as fh:
        fh.write("\n".join(mut_lines) + "\n")
    nj = max(1, int(njobs))
    argv = [_run(), "residue_scanning_backend.py", complex_file, "-muts_file", muts,
            "-jobname", job, "-HOST", f"localhost:{nj}"]
    if calc:
        argv += ["-calc", calc]
    if ligand_asl:
        argv += ["-ligand_asl", ligand_asl]
    srv = _ensure_job_server()
    # residue_scanning_backend.py is a JobDJ manager script (like thermal_mmgbsa.py): launch it
    # under Job Control via the helper (async) rather than a self-submitting -WAIT driver.
    res = _helper("launch", {"argv": argv, "launch_dir": out_dir}, timeout=180)
    res["job_server"] = srv
    res["muts_file"] = muts
    res["expected_out_maegz"] = os.path.join(out_dir, job + "-out.maegz")
    res["note"] = "output name may be <job>.maegz or <job>-out.maegz — verify on first run"
    return res


# ---------- QSite QM/MM (DEFER; CAVEATED offline fallback; consumes a QSite/Jaguar token) ----------

# A cut-bond spec: MOLID:CHAIN:RESNUM:QMATOM:MMATOM  (QMATOM in the QM layer, MMATOM in the MM layer).
_QSITE_CUT_RE = re.compile(r"^\d+:[A-Za-z_]?:-?\d+:[A-Za-z0-9']+:[A-Za-z0-9']+$")


@mcp.tool()
def qsite_qmmm(structure_file: str, out_dir: str, qm_molids: list = None, cut_bonds: list = None,
               dft_functional: str = "b3lyp", basis: str = "lacvp*", optimize: bool = False,
               mm_ff: str = "opls2005", job_name: str = "qsite_job", timeout_s: int = 7200) -> dict:
    """QSite QM/MM single-point (or optimization) on a PREPARED complex (.mae). Writes an IMPACT
    QSite .in (MAEFILE + &gen basis/dftname/igeopt/mmqm + &mmkey qsite_ff + &qmregion) and runs
    `_exec [_driver('qsite'), <job>.in -WAIT]`. Define the QM region EITHER by whole molecules
    (`qm_molids=[2]`, e.g. the ligand — NO covalent boundary, SAFEST) OR by residue cut bonds
    (`cut_bonds=['MOLID:CHAIN:RESNUM:QMATOM:MMATOM', ...]`, cut between QMATOM(kept in QM) and
    MMATOM(kept in MM), e.g. '1:A:3:CB:CA'); the two are mutually exclusive. dft_functional/basis
    pick the QM level; optimize=True sets igeopt=1 (else a single point). Returns
    {returncode, in_file, qsite_out}.

    WARNING — read before trusting any number:
      * Overlaps qdx-rush `exess_qmmm` (GPU cloud). Prefer that, or the local `jaguar_qm`
        single-point on a `qm_cluster_extract` cluster, as the PRIMARY local QM fallback.
      * The QM/MM BOUNDARY is the single highest setup-error risk — a mis-placed cut bond
        silently corrupts the energy. A whole-molecule `qm_molids` region avoids it entirely.
      * Sized for a single ~6GB local GPU — keep the QM region SMALL.
      * NEVER trust a QSite energy without independent validation.
      * The .in template matches the shipped 2026-2 impact-v11.1/samples/qsite/{qsite.in,
        qsite-1tpb.in} (driver `qsite <infile> -WAIT` verified) — but NOT runtime-tested here.
      * structure_file is written verbatim into the MAEFILE line; keep its path space-free."""
    try:
        structure_file = _safe_path(structure_file, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not job_name.replace("_", "").replace("-", "").isalnum():
        return {"error": f"invalid job_name: {job_name!r}"}
    if bool(qm_molids) == bool(cut_bonds):
        return {"error": "define the QM region with EITHER qm_molids OR cut_bonds (exactly one)"}
    for tok in (dft_functional, basis, mm_ff):
        if not isinstance(tok, str) or not tok.strip() or any(c in tok for c in "\r\n\x00 \t"):
            return {"error": f"invalid QM/MM keyword (no spaces/control chars): {tok!r}"}
    # Build the &qmregion block from exactly one schema.
    if qm_molids:
        try:
            mids = [int(m) for m in qm_molids]
        except (TypeError, ValueError):
            return {"error": "qm_molids must be a list of integer molecule numbers"}
        if any(m < 1 for m in mids):
            return {"error": "qm_molids are 1-based molecule numbers (>= 1)"}
        region = [" molid"] + [f"     {m}" for m in mids]
    else:
        rows = [" molid chain  resnum   qmatom   mmatom"]
        for cb in cut_bonds:
            if not isinstance(cb, str) or not _QSITE_CUT_RE.match(cb.strip()):
                return {"error": f"bad cut_bond {cb!r} (expect 'MOLID:CHAIN:RESNUM:QMATOM:MMATOM', e.g. '1:A:3:CB:CA')"}
            molid, chain, resnum, qmatom, mmatom = cb.strip().split(":")
            rows.append(f"     {molid}     {chain}       {resnum}       {qmatom}       {mmatom}")
        region = rows
    os.makedirs(out_dir, exist_ok=True)
    igeopt = 1 if optimize else 0
    lines = [f"MAEFILE: {structure_file}", "&gen", "vshift=1.0", f"basis={basis}", "maxit=100",
             f"igeopt={igeopt}", f"dftname={dft_functional}", "mmqm=1", "iacc=1", "&",
             "&mmkey", f"qsite_ff={mm_ff}", "maxcycles=1000", "use_nb_cutoff=0", "&",
             "&qmregion"] + region + ["&"]
    job = _jobname(job_name)
    inp = os.path.join(out_dir, job + ".in")
    with open(inp, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    argv = [_driver("qsite"), os.path.basename(inp), "-WAIT"]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    out = os.path.join(out_dir, job + ".out")
    return {"returncode": p.returncode, "in_file": inp,
            "qsite_out": out if os.path.exists(out) else None,
            "stdout_tail": p.stdout[-1800:], "stderr_tail": p.stderr[-1800:]}


# ============================================================================
# ==== APPENDED TOOL GROUP: g13_mlcompose ====
# ============================================================================

# IMPORTS: (none new — reuses os, subprocess, json, csv-as-_csv already imported in server.py;
#           calls existing tool fns ligprep(), glide_dock(), convert_structure() in-module and the
#           existing internals _driver, _exec, _helper, _safe_path, _ensure_job_server)

# ---------- AutoQSAR: automated ML QSAR (synchronous -WAIT; consumes a QSAR token) ----------
# CLI verified against the INSTALLED 2026-2 sources (authoritative, not web docs):
#   internal/lib/site-packages/schrodinger/application/canvas/packages/autoqsar_arg_utils.py
#   internal/lib/site-packages/schrodinger/application/canvas/packages/autoqsar_job_utils.py
#   canvas-v6.8/bin/Windows-x64/autoqsar_driver.py
# Confirmed facts:
#   * launcher is `$SCHRODINGER/utilities/autoqsar`; the model archive is a POSITIONAL that MUST
#     end in `.qzip` (prepare_for_parsing keys off the .qzip suffix) and precedes the task ->
#     `autoqsar <model>.qzip <build|test|report> ...`.
#   * TASK enum is exactly {build, test, report, rebuild}: prediction IS the `test` task; there is
#     NO `pred` task (autoqsar_arg_utils.TASK = ('build','test','report','rebuild')).
#   * success sentinel is `<jobname>.okay`, jobname = <model-stem>_<task> (job_utils.get_jobname +
#     the parser epilog) -> build writes `<stem>_build.okay`.
#   * `-pred <file>` leading path is ignored (basename written to the job dir) -> run in the job
#     dir, pass a basename (job_utils.set_input_and_output_files uses os.path.basename(args.pred)).
#   * `-unknown` MUST be supplied when any input structure lacks the activity value (i.e. real
#     prediction on NEW molecules) or the test job errors -> autoqsar_predict passes it by default.
#   * build/test run under Job Control (JobDJ subjobs); report/rebuild are synchronous foreground
#     (job_utils.is_synchronous_job) -> -WAIT + _ensure_job_server for build/test, neither for report.

@mcp.tool()
def autoqsar_build(train: str, y_prop: str, model_qzip: str, mode: str = "num",
                   log_transform: bool = False, n_try: int = 0, n_keep: int = 0,
                   report: bool = True, timeout_s: int = 3600) -> dict:
    """AutoQSAR model building: train an automated QSAR ensemble (MLR/PLS/KPLS/... auto-selected)
    on a labeled learning set (.mae/.sdf/.smi-csv where every structure carries the `y_prop`
    activity) -> a `<model>.qzip` archive. Runs
    `autoqsar <model>.qzip build -i <train> -y <y_prop> -num|-cat [-log] [-try n] [-keep m] -WAIT`.
    mode='num' (regression -> R^2/Q^2/RMSE) or 'cat' (classification). log_transform adds -log
    (use when activities are IC50/Ki). When report=True, follows with the `report` task and returns
    the per-model stats table. Consumes a QSAR license token. DEFER: needs real assay data to train.
    NOTE: CLI verified against the installed 2026-2 autoqsar arg parser + job utils; runtime-untested
    (no assay set here)."""
    try:
        train = _safe_path(train, must_exist=True)
        model_qzip = _safe_path(model_qzip)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if mode not in ("num", "cat"):
        return {"error": "mode must be 'num' (regression) or 'cat' (classification)"}
    if not model_qzip.lower().endswith(".qzip"):
        # The arg parser identifies the model POSITIONAL by its .qzip suffix; without it the
        # command line is silently misparsed (model treated as a stray post-task arg).
        return {"error": f"model_qzip must end in .qzip, got {os.path.basename(model_qzip)!r}"}
    # y_prop reaches argv as `-y <y_prop>`. It is not a path (so not _safe_path'd) but is still a
    # client string: reject empty, control chars, and a leading '-' (would be read as a flag).
    if not y_prop.strip() or y_prop.strip().startswith("-") or any(c in y_prop for c in "\r\n\x00"):
        return {"error": f"invalid y_prop: {y_prop!r}"}
    # AutoQSAR ignores any leading path in <model> when building -> run in the out dir, pass basename.
    wd = os.path.dirname(model_qzip) or "."
    model_base = os.path.basename(model_qzip)
    os.makedirs(wd, exist_ok=True)
    argv = [_driver("autoqsar"), model_base, "build", "-i", train, "-y", y_prop, "-" + mode]
    if log_transform and mode == "num":
        argv.append("-log")
    if int(n_try) > 0:
        argv += ["-try", str(int(n_try))]
    if int(n_keep) > 0:
        argv += ["-keep", str(int(n_keep))]
    argv.append("-WAIT")
    srv = _ensure_job_server()
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s", "job_server": srv}
    out_model = os.path.join(wd, model_base)
    okay = os.path.join(wd, os.path.splitext(model_base)[0] + "_build.okay")
    res = {"returncode": p.returncode, "job_server": srv,
           "model_qzip": out_model if os.path.exists(out_model) else None,
           "build_okay": os.path.exists(okay),
           "stdout_tail": p.stdout[-2000:], "stderr_tail": p.stderr[-1500:]}
    if report and os.path.exists(out_model):
        # `report` is a synchronous, token-free summary of the built models (one line per model).
        try:
            rp = _exec([_driver("autoqsar"), model_base, "report"], timeout=300, cwd=wd)
            res["report"] = rp.stdout[-3000:]
            lines = [ln for ln in rp.stdout.splitlines() if ln.strip()]
            hi = next((i for i, ln in enumerate(lines) if "Code" in ln.split()), None)
            if hi is not None:  # best-effort structured parse of the aligned stats table
                hdr = lines[hi].split()
                res["models"] = [dict(zip(hdr, ln.split())) for ln in lines[hi + 1:]
                                 if len(ln.split()) == len(hdr)]
        except Exception as e:
            res["report_error"] = repr(e)
    return res


@mcp.tool()
def autoqsar_predict(model_qzip: str, new_mae: str, pred_csv: str = "", consensus: str = "all",
                     activities_known: bool = False, timeout_s: int = 1800) -> dict:
    """AutoQSAR prediction: apply a built `.qzip` model to new structures (.mae/.sdf/.smi-csv).
    Runs the `test` task
    (`autoqsar <model>.qzip test -i <new> -pred <out.csv> -all|-best [-unknown] -WAIT`) and parses
    the predicted `r_autoqsar_Pred_*` columns. consensus='all' (ensemble of retained models,
    default) or 'best' (top-ranked model only). Output defaults to a SMILES-CSV next to `new_mae`.
    activities_known=False (default) passes `-unknown` — REQUIRED by AutoQSAR when the input lacks
    the activity value, i.e. the normal predict-on-new-molecules case; set True only for a labeled
    test set where you want test stats. Consumes a QSAR token. DEFER: needs a model built by
    autoqsar_build from real assay data.
    NOTE: prediction is the `test` task (there is NO `pred` task) — verified against the installed
    2026-2 autoqsar_arg_utils.py/autoqsar_job_utils.py; runtime-untested here (no built model)."""
    try:
        model_qzip = _safe_path(model_qzip, must_exist=True)
        new_mae = _safe_path(new_mae, must_exist=True)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not model_qzip.lower().endswith(".qzip"):
        return {"error": f"model_qzip must end in .qzip, got {os.path.basename(model_qzip)!r}"}
    if consensus not in ("all", "best"):
        return {"error": "consensus must be 'all' or 'best'"}
    wd = os.path.dirname(new_mae) or "."
    if pred_csv:
        try:
            pred_csv = _safe_path(pred_csv)
        except ValueError as e:
            return {"error": str(e)}
    else:
        pred_csv = os.path.join(wd, os.path.splitext(os.path.basename(new_mae))[0] + "_autoqsar_pred.csv")
    # A test job ignores any leading path in -pred (written to the job dir) -> run in wd, pass basename.
    out_csv = os.path.join(wd, os.path.basename(pred_csv))
    argv = [_driver("autoqsar"), model_qzip, "test", "-i", new_mae,
            "-pred", os.path.basename(pred_csv), "-" + consensus]
    if not activities_known:
        # Required whenever any input structure lacks the y activity (normal prediction case);
        # without it the test job errors ("... lacks an activity value").
        argv.append("-unknown")
    argv.append("-WAIT")
    srv = _ensure_job_server()
    try:
        p = _exec(argv, timeout=timeout_s, cwd=wd)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s", "job_server": srv}
    res = {"returncode": p.returncode, "job_server": srv,
           "predictions_csv": out_csv if os.path.exists(out_csv) else None,
           "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    if os.path.exists(out_csv):
        with open(out_csv, newline="") as fh:
            rows = list(_csv.DictReader(fh))
        cols = list(rows[0].keys()) if rows else []
        res["n_predictions"] = len(rows)
        res["prediction_columns"] = [c for c in cols if "pred" in c.lower()] or cols
        res["predictions"] = rows[:200]
    return res


# ---------- Active-learning docking (COMPOSE + local-lib: rdkit+sklearn surrogate) ----------

@mcp.tool()
def al_dock(smiles_library: str, grid_file: str, seed: int = 0, iters: int = 3, batch: int = 48,
            precision: str = "HTVS", top_k: int = 20, refine_precision: str = "SP",
            surrogate: str = "ridge", kappa: float = 1.0, fp_radius: int = 2, fp_bits: int = 2048,
            out_dir: str = "", dock_timeout_s: int = 3600, ligprep_timeout_s: int = 1200) -> dict:
    """Active-learning docking: enrich a large SMILES library against a Glide grid WITHOUT docking
    all of it. Seeds a random `batch`, docks it (ligprep -> glide_dock at `precision`), Morgan-FP
    featurizes the docked survivors, trains a cheap sklearn surrogate (surrogate='ridge'|'rf') on
    FP -> docking score, acquires the next `batch` by an uncertainty-aware UCB (mean - kappa*std,
    minimizing score), repeats for `iters` rounds, then re-docks the enriched `top_k` at
    `refine_precision`. COMPOSE (calls the in-module ligprep()/glide_dock() tools) + local-lib
    (rdkit+sklearn run in the suite interpreter via _helper; both ship with 2026-2). BLOCKS for the
    whole campaign - every round is a synchronous Glide -WAIT - so keep batch/iters modest and
    expect a long call; consumes LigPrep+Glide tokens per round. Schrodinger also ships a native
    Glide active-learning workflow (glide_ml); this is the lightweight local-surrogate alternative.
    Confidence LOW: pipeline/argv-verified end-to-end but runtime-untested against a live grid. The
    score<->library mapping keys on the per-molecule title, which the helper sanitizes to be
    whitespace-free so the .smi round-trip through ligprep/glide is stable - validate the first
    campaign. DEFER."""
    try:
        smiles_library = _safe_path(smiles_library, must_exist=True)
        grid_file = _safe_path(grid_file, must_exist=True)
        wd = _safe_path(out_dir) if out_dir else (os.path.dirname(smiles_library) or ".")
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if precision not in ("HTVS", "SP", "XP") or refine_precision not in ("HTVS", "SP", "XP"):
        return {"error": "precision/refine_precision must be HTVS, SP, or XP"}
    if surrogate not in ("ridge", "rf"):
        return {"error": "surrogate must be 'ridge' or 'rf'"}
    iters, batch, top_k = max(1, int(iters)), max(1, int(batch)), max(1, int(top_k))
    os.makedirs(wd, exist_ok=True)
    srv = _ensure_job_server()
    prep = _helper("al_prep", {"library": smiles_library, "out_dir": wd, "seed": int(seed),
                               "batch": batch, "fp_radius": int(fp_radius), "fp_bits": int(fp_bits)},
                   timeout=600)
    if prep.get("error"):
        return {"stage": "al_prep", "job_server": srv, **prep}
    if not prep.get("sklearn"):
        return {"error": "scikit-learn not importable in the Schrodinger interpreter - al_dock needs it",
                "stage": "al_prep", "detail": prep, "job_server": srv}
    labeled, history, acq_info = {}, [], None      # labeled: title -> best docking score
    batch_smi = prep["seed_smi"]
    for it in range(iters):
        lp = ligprep(batch_smi, os.path.join(wd, f"_al_lig_{it}.mae"), timeout_s=ligprep_timeout_s)
        if not lp.get("output"):
            return {"error": "ligprep failed", "stage": f"round{it}:ligprep", "detail": lp,
                    "labeled": labeled, "history": history, "job_server": srv}
        dk = glide_dock(grid_file, lp["output"], precision=precision, timeout_s=dock_timeout_s)
        poses = dk.get("poses")
        sc = _helper("al_scores", {"pose_file": poses}, timeout=300) if poses else {"scores": {}}
        new = sc.get("scores", {})
        labeled.update(new)
        history.append({"round": it, "precision": precision, "batch_smi": batch_smi, "poses": poses,
                        "docked_this_round": len(new), "cumulative_labeled": len(labeled),
                        "best_score": (min(labeled.values()) if labeled else None),
                        "selected_by": (acq_info or {}).get("model")})
        if it < iters - 1:
            acq = _helper("al_acquire", {"out_dir": wd, "labeled": labeled, "acquire_n": batch,
                                         "surrogate": surrogate, "kappa": float(kappa),
                                         "iter_idx": it + 1, "seed": int(seed)}, timeout=900)
            if acq.get("error") or not acq.get("batch_smi"):
                return {"error": "acquisition failed / library exhausted", "stage": f"round{it}:acquire",
                        "detail": acq, "labeled": labeled, "history": history, "job_server": srv}
            acq_info, batch_smi = acq, acq["batch_smi"]
    # rank + re-dock the enriched top_k at the (usually higher) refine precision
    ranked = sorted(labeled.items(), key=lambda kv: kv[1])[:top_k]
    refine = {"skipped": "no labeled poses to refine"}
    if ranked:
        pick = _helper("al_write_smiles", {"out_dir": wd, "titles": [t for t, _ in ranked],
                                           "out_smi": os.path.join(wd, "_al_topk.smi")}, timeout=120)
        if pick.get("out_smi"):
            rl = ligprep(pick["out_smi"], os.path.join(wd, "_al_topk.mae"), timeout_s=ligprep_timeout_s)
            if rl.get("output"):
                rd = glide_dock(grid_file, rl["output"], precision=refine_precision,
                                timeout_s=dock_timeout_s)
                rp = rd.get("poses")
                rs = _helper("al_scores", {"pose_file": rp}, timeout=300) if rp else {"scores": {}}
                refine = {"precision": refine_precision, "poses": rp, "refined_scores": rs.get("scores", {})}
            else:
                refine = {"error": "top_k ligprep failed", "detail": rl}
        else:
            refine = {"error": "could not resolve top_k SMILES from cache", "detail": pick}
    return {"library_size": prep.get("n_library"), "iters": iters, "batch": batch,
            "precision": precision, "surrogate": surrogate, "n_labeled": len(labeled),
            "best_score": (min(labeled.values()) if labeled else None),
            "top_k": [{"title": t, "score": v} for t, v in ranked], "refined": refine,
            "history": history, "out_dir": wd, "job_server": srv}


# ---------- OpenMM bridge (COMPOSE; license-free local MD via the openmm-md MCP) ----------

@mcp.tool()
def openmm_from_prepared(prepared_mae: str, out_pdb: str) -> dict:
    """Bridge a Schrodinger-prepared complex (a prepwizard `.mae`/`.maegz`) to the LICENSE-FREE
    openmm-md MCP for local MD - the orthogonal cross-check path, since Desmond's MD engine is NOT
    installed on this host. Converts .mae -> .pdb via the in-module convert_structure tool
    (schrodinger.structure, no token), then hand `out_pdb` to the `mcp__openmm-md__` tools in order:
    openmm_prepare -> openmm_solvate -> openmm_minimize -> openmm_equilibrate -> openmm_production
    -> openmm_mmgbsa / openmm_analyze (poll openmm_status). COMPOSE/bridge only - the MD runs under
    the openmm-md server, not here. Returns {pdb, next_steps}."""
    try:
        prepared_mae = _safe_path(prepared_mae, must_exist=True)
        out_pdb = _safe_path(out_pdb)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    if not out_pdb.lower().endswith(".pdb"):
        return {"error": "out_pdb must end in .pdb (the openmm-md tools consume a PDB)"}
    os.makedirs(os.path.dirname(out_pdb) or ".", exist_ok=True)
    res = convert_structure(prepared_mae, out_pdb)   # existing tool -> schrodinger.structure writer
    if res.get("error"):
        return {"error": res["error"], "stage": "convert_structure"}
    return {"pdb": res.get("dst"), "structures": res.get("structures"),
            "size_bytes": res.get("size_bytes"),
            "next_steps": [
                "mcp__openmm-md__openmm_prepare: input the returned pdb (assign force field; "
                "split receptor/ligand if the tool expects separate inputs)",
                "mcp__openmm-md__openmm_solvate: add explicit water + neutralizing ions (box padding)",
                "mcp__openmm-md__openmm_minimize: energy-minimize the solvated system",
                "mcp__openmm-md__openmm_equilibrate: NVT/NPT equilibration with restraints",
                "mcp__openmm-md__openmm_production: production MD (GPU) - poll mcp__openmm-md__openmm_status",
                "mcp__openmm-md__openmm_mmgbsa or openmm_analyze: end-state dG / trajectory metrics",
            ],
            "note": "License-free local MD + an orthogonal cross-check to Desmond/Prime. For a "
                    "ligand-only or receptor-only leg, convert that selection to its own PDB first."}


if __name__ == "__main__":
    mcp.run()
