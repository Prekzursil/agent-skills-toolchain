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
import json
import shutil
import subprocess
import tempfile
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


def _exec(argv, timeout=300, cwd=None):
    """Single subprocess chokepoint. argv is a pre-built list; never shell=True.
    Callers pass only validated, structured args -> no shell/arg injection here.
    stdin=DEVNULL is REQUIRED: this server runs over stdio (its own stdin is the MCP
    pipe). Without redirecting, a spawned `run python3 ...` child inherits that live
    pipe and blocks forever reading it -> every compute tool hangs to the 300s client
    timeout (while the same command runs in ~1s from a shell). DEVNULL gives an
    immediate EOF so the child never blocks on stdin."""
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd,
                          stdin=subprocess.DEVNULL)


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


def _submit_async(argv, cwd=None, timeout=300) -> dict:
    """Ensure the job server, run a jobcontrol driver WITHOUT -WAIT, parse its JobId.
    The launcher returns in seconds; the compute runs detached under the job server."""
    srv = _ensure_job_server()
    try:
        p = _exec(argv, timeout=timeout, cwd=cwd)
    except subprocess.TimeoutExpired:
        return {"error": f"submission did not return within {timeout}s", "job_server": srv}
    blob = (p.stdout or "") + "\n" + (p.stderr or "")
    m = _JOBID_RE.search(blob)
    if not m:
        return {"error": "no JobId in launcher output - submission likely failed",
                "job_server": srv, "returncode": p.returncode,
                "stdout_tail": p.stdout[-1500:], "stderr_tail": p.stderr[-1500:]}
    return {"jobid": m.group(1), "job_server": srv, "returncode": p.returncode,
            "stdout_tail": p.stdout[-600:]}


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
    return _helper("smiles_to_3d", {"smiles": smiles, "out_path": _safe_path(out_path), "title": title})


@mcp.tool()
def molecule_properties(smiles: str) -> dict:
    """Drug-likeness panel for a SMILES: formula, MW, logP, HBD/HBA, TPSA, rot-bonds, rings, QED, Lipinski."""
    return _helper("properties", {"smiles": smiles})


@mcp.tool()
def convert_structure(src: str, dst: str) -> dict:
    """Convert a structure file between formats (.sdf <-> .mae <-> .pdb) via schrodinger.structure."""
    return _helper("convert", {"src": _safe_path(src, must_exist=True), "dst": _safe_path(dst)})


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
    accurate than PROPKA for phenibut's COOH (~4.1) / NH3+ (~9.3) groups - the protonation
    state is load-bearing for the GABA-B binding mode. Returns the .out path. NOTE: untested
    against a live run; verify the first invocation."""
    try:
        structure_file = _safe_path(structure_file, must_exist=True)
        out_dir = _safe_path(out_dir)
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(out_dir, exist_ok=True)
    job = os.path.splitext(os.path.basename(structure_file))[0] + "_pka"
    argv = [_driver("jaguar"), "pka", structure_file, "-WAIT", "-jobname", job]
    try:
        p = _exec(argv, timeout=timeout_s, cwd=out_dir)
    except subprocess.TimeoutExpired:
        return {"error": f"timeout after {timeout_s}s"}
    out = os.path.join(out_dir, job + ".out")
    return {"returncode": p.returncode, "pka_out": out if os.path.exists(out) else None,
            "stdout_tail": p.stdout[-2000:], "stderr_tail": p.stderr[-1500:]}


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
    res = _submit_async(argv, cwd=wd, timeout=300)
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
            "-HOST", f"localhost:{nj}", "-NJOBS", str(nj)]
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
def fep_plus(fmp_map: str, out_dir: str = "", subhost_gpus: int = 1, timeout_s: int = 300) -> dict:
    """FEP+ relative binding free energy on a prebuilt FEP map (.fmp). ASYNC (GPU, long) via the
    P0 job-control layer -> {jobid}; poll job_status. The .fmp perturbation graph is authored in
    Maestro's FEP Mapper (or the scisol fep API) - this RUNS an existing .fmp. On a 6GB GPU keep
    maps SMALL (few edges). NOTE: also requires the Desmond MD engine, which is NOT installed on
    this host (see desmond_md) - so this is argv/submit-verified only here."""
    try:
        fmp_map = _safe_path(fmp_map, must_exist=True)
        wd = _safe_path(out_dir) if out_dir else (os.path.dirname(fmp_map) or ".")
    except (ValueError, FileNotFoundError) as e:
        return {"error": str(e)}
    os.makedirs(wd, exist_ok=True)
    job = _jobname(fmp_map)
    nj = max(1, int(subhost_gpus))
    argv = [_driver("fep_plus"), fmp_map, "-JOBNAME", job, "-HOST", "localhost",
            "-SUBHOST", f"localhost:{nj}"]
    res = _submit_async(argv, cwd=wd, timeout=300)
    res["expected_out_fmp"] = os.path.join(wd, job + "-out.fmp")
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
    res = _submit_async(argv, cwd=wd, timeout=300)
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
    res = _submit_async(argv, cwd=wd, timeout=300)
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
    res = _submit_async(argv, cwd=wd, timeout=300)
    res["expected_poses"] = os.path.join(wd, job + "-out.maegz")
    return res


if __name__ == "__main__":
    mcp.run()
