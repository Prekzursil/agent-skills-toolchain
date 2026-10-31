---
title: SCHRODINGER-MCP
type: note
permalink: dqverify-repo-20261013/docs/drug-discovery/schrodinger-mcp
---

# Schrodinger MCP Server

A thin, security-conscious [Model Context Protocol](https://modelcontextprotocol.io) (MCP)
server that wraps a **local Schrodinger / Maestro Suite install** and exposes 67
tools for structure prep, docking, screening, MD/free energy, QM, ADMET, pose
analysis, and job orchestration to Claude Code / Claude Desktop.

- **Location:** `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp`
- **Entry point:** `server.py` (FastMCP, stdio transport)
- **Backend helper:** `_sch_helper.py` (runs *inside* the Schrodinger interpreter)
- **Suite status:** the core pipeline was live-tested against Schrodinger 2022-4,
  build 79134. The expanded 67-tool surface targets 2026-2 and is statically
  verified, with live-box smoke testing still pending.
- **Status:** register the canonical launch path below, then verify `✓ Connected`
  with `claude mcp get schrodinger`.

---

## Overview

This is a **custom-built** MCP connector (not an upstream package). It gives an LLM
agent a typed, security-conscious surface onto an installed Schrodinger Suite for
drug-discovery work:

1. **Structure prep / cheminformatics** (no license token): version/build info,
   SMILES to 3D, drug-likeness descriptors, format conversion, and a raw
   Schrodinger-Python escape hatch.
2. **Product drivers** (consume Schrodinger license tokens): preparation,
   docking, pose analysis, MD/free-energy, QM, and property workflows.
3. **Operations:** job lifecycle, GPU-pool, diagnostics, and recovery tools for
   long-running licensed workflows.

The architectural keystone is that the server process **never imports
`schrodinger` in-process**. The `schrodinger` Python package and its bundled
`rdkit` only import correctly when launched under `$SCHRODINGER/run`. So the
server (which lives in its own ordinary venv) shells out: it builds an argv list
and runs `run.exe python3 _sch_helper.py <cmd> <json-args>`, then parses the one
JSON line the helper prints. Product drivers (LigPrep/QikProp/Glide) are invoked
as their own executables (`ligprep`, `qikprop`, `glide`) rather than through the
helper.

---

## Security Model

The server is designed for **local, single-user use** and treats every
client-supplied value as untrusted until validated. Three properties enforce this:

### 1. Single subprocess chokepoint: `_exec()`

There is exactly **one** place in the codebase that calls `subprocess.run`:

```python
def _exec(argv, timeout=300, cwd=None):
    """Single subprocess chokepoint. argv is a pre-built list; never shell=True."""
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)
```

- `_exec` is **never decorated as an MCP tool** — untrusted tool parameters cannot
  flow *directly* into `subprocess.run`; they pass through a tool function first.
- It always runs with a **pre-built argv list and never `shell=True`**, so there is
  no shell to interpret metacharacters → no shell injection.
- All other internal subprocess helpers (`_helper`, the driver tools) call `_exec`;
  no other module-level subprocess site exists.

### 2. Path validation: `_safe_path()`

Any client-supplied filesystem path is passed through `_safe_path` *before* it can
reach an argv:

```python
def _safe_path(p, must_exist=False):
    if not isinstance(p, str) or not p.strip() or p.strip().startswith("-"):
        raise ValueError(f"invalid/unsafe path: {p!r}")
    ap = os.path.abspath(p)
    if must_exist and not os.path.exists(ap):
        raise FileNotFoundError(ap)
    return ap
```

- Rejects empty/whitespace-only values.
- **Rejects flag-like values** (anything starting with `-`), preventing a path
  argument from being smuggled in as a CLI option (argument injection).
- Normalizes to an absolute path; optionally asserts existence.

Input-file params use `_safe_path(..., must_exist=True)`; output params use
`_safe_path(...)` (no existence check).

### 3. No in-process `schrodinger` import

The server never `import schrodinger`. The `schrodinger`/`rdkit` packages are
imported only inside `_sch_helper.py`, which runs in the Schrodinger interpreter
via subprocess. JSON args are encoded into **one argv element** (`json.dumps(args)`),
so the values are inert data, not shell tokens.

### Residual risk — `run_schrodinger_python`

The `run_schrodinger_python` tool is a deliberate escape hatch that executes an
**arbitrary Python snippet** inside the Schrodinger interpreter (it writes the code
to a temp file under the server directory and runs it under `run`). This is
powerful by design and is the reason the server is **intended for local,
single-user use only** — do not expose it to an untrusted client.

---

## The 67 Tools

The complete surface, grouped by capability, is:

- **Diagnostics and structure I/O (10):** `schrodinger_version`, `backend_info`,
  `backend_doctor`, `smiles_to_3d`, `molecule_properties`, `convert_structure`,
  `structure_properties_extract`, `pdb_fetch`, `run_schrodinger_python`,
  `install_cure`.
- **Prep, docking, and pose workflows (15):** `prepwizard`, `prep_target`,
  `glide_grid`, `ligprep`, `glide_dock`, `ensemble_dock`, `al_dock`,
  `dock_triage`, `prime_mmgbsa`, `induced_fit_docking`, `covalent_docking`,
  `pose_validity`, `pose_interaction_fingerprint`, `pose_viewer_split`,
  `pymol_render`.
- **Screening, properties, and analogs (13):** `qikprop_admet`,
  `qikprop_parse_results`, `sitemap`, `confgen`, `shape_screen`,
  `canvas_fingerprints`, `canvas_descriptors`, `phase_pharmacophore`,
  `phase_screen`, `ligfilter`, `propfilter`, `analog_scan`,
  `reaction_enumerate`.
- **MD and free energy (14):** `desmond_setup`, `desmond_md`,
  `desmond_trajectory_analysis`, `desmond_interactions`,
  `desmond_membrane_setup`, `thermal_mmgbsa`, `fep_plus`, `fep_map_build`,
  `fep_parse_results`, `fep_absolute_binding`, `watermap`, `bpmd`,
  `bpmd_ladder`, `openmm_from_prepared`.
- **QM, advanced modeling, and ML (10):** `jaguar_pka`, `jaguar_qm`,
  `epik_enumerate`, `epik_pka`, `qm_cluster_extract`,
  `macromodel_confsearch`, `residue_scanning`, `qsite_qmmm`,
  `autoqsar_build`, `autoqsar_predict`.
- **Job and GPU operations (5):** `job_server_control`, `job_status`, `job_wait`,
  `job_restart`, `schrodinger_gpu_pool`.

The core structure and docking tools are documented in depth below.

### Structure / cheminformatics (no license token)

#### 1. `schrodinger_version() -> str`
Returns the Schrodinger suite version + resolved environment, captured from
`run -v`. On failure returns an `ERROR: ...` string that also echoes the
`SCHRODINGER` path for diagnosis.

#### 2. `backend_info() -> dict`
Schrodinger build + bundled RDKit version + the install path visible to the
backend. Routed through `_sch_helper.py` (`info`); keys: `schrodinger_path`,
`schrodinger_build`, `rdkit`.

#### 3. `smiles_to_3d(smiles, out_path, title="") -> dict`
SMILES → 3D structure file. 3D coordinates are generated with **RDKit ETKDGv3
embedding + MMFF optimization** (fixed `randomSeed=42`). The output extension
selects the format: `.sdf`/`.sd` writes via RDKit's `SDWriter`; otherwise
(`.mae`/`.maegz`) the RDKit mol is converted with `schrodinger.adapter.to_structure`
(preserving the 3D coords) — use `.mae` for Glide/Prime downstream, `.sdf` for
portability. `out_path` is validated with `_safe_path`. Returns
`{ok, out_path, atoms, size_bytes}` (or `{error: ...}` on bad SMILES / failed embed).

#### 4. `molecule_properties(smiles) -> dict`
Drug-likeness descriptor panel for a SMILES (RDKit). Returns: `formula`, `mw`,
`logp`, `hbd`, `hba`, `tpsa`, `rotatable_bonds`, `rings`, `qed`, and a boolean
`lipinski_pass` (MW ≤ 500, logP ≤ 5, HBD ≤ 5, HBA ≤ 10).

#### 5. `convert_structure(src, dst) -> dict`
Convert a structure file between formats (`.sdf` ↔ `.mae` ↔ `.pdb`) via
`schrodinger.structure` (reads all structures from `src`, writes them to `dst`).
`src` is validated with `must_exist=True`; `dst` with `_safe_path`. Returns
`{ok, dst, structures, size_bytes}`.

#### 6. `run_schrodinger_python(code, timeout_s=300) -> dict`
**Escape hatch.** Runs an arbitrary Python snippet inside the Schrodinger
interpreter (where both `schrodinger` and `rdkit` are importable). The code is
written to a temp `.py` file under the server dir, executed via
`run python3 <tmp>`, then the temp file is deleted. Returns
`{returncode, stdout, stderr}` (stdout truncated to last 8000 chars, stderr to
4000) or `{error: "timeout ..."}`. **Arbitrary local code execution — local
single-user use only.**

### Product drivers (consume Schrodinger LICENSE TOKENS; synchronous `-WAIT`)

> **License note:** the tools below shell out to Schrodinger product
> executables (`prepwizard`, `glide` for grid + dock, `ligprep`, `qikprop`,
> `prime_mmgbsa`) and **each checkout consumes a Schrodinger license token** for
> the corresponding product. They run with the `-WAIT` flag (synchronous /
> blocking) so the MCP call returns only when the job finishes. Generous default
> timeouts are provided and are configurable per call.

#### 7. `ligprep(input_file, output_mae, timeout_s=1200) -> dict`
**LigPrep** — generates prepared 3D ligand states (ionization / tautomers /
stereoisomers). Accepts `.smi` (`-ismi`), `.sdf`/`.sd` (`-isd`), or `.mae`/other
(`-imae`); always writes MAE via `-omae`. Runs `ligprep ... -WAIT` in the output
file's directory. Inputs validated (`must_exist=True`); output validated. Returns
`{returncode, output, stdout_tail, stderr_tail}` (`output` is the MAE path if it
was produced, else `null`). **Consumes a LigPrep license token.**

#### 8. `qikprop_admet(structure_file, timeout_s=900) -> dict`
**QikProp** — ADMET / physicochemical property prediction on a 3D structure
(`.mae`/`.sdf`). Runs `qikprop -WAIT <structure_file>` in the structure's
directory and looks for `<basename>.CSV`. Returns `{returncode, csv,
stdout_tail, stderr_tail}` plus `csv_head` (first 3 lines of the result CSV) when
the CSV exists. **Consumes a QikProp license token.**

#### 9. `glide_dock(grid_file, ligands_mae, precision="SP", timeout_s=3600) -> dict`
**Glide** — docks prepared ligands into a receptor grid (`.zip`) built by
`glide_grid` (#11). `precision` must be one of `HTVS | SP | XP` (validated). The
tool writes a small Glide `.in` file (`GRIDFILE` / `LIGANDFILE` / `PRECISION`,
plus `POSE_OUTTYPE poseviewer`) in the ligands' directory, then runs
`glide <job>.in -WAIT -OVERWRITE`. Returns `{returncode, poses, stdout_tail,
stderr_tail}` where `poses` is the `*_pv.maegz` pose-viewer path if produced.
**Consumes a Glide license token.**

#### 10. `prepwizard(input_file, output_mae, ph=7.0, fill_sidechains=True, timeout_s=1800) -> dict`
**Protein Preparation Wizard** — cleans a raw receptor (`.pdb`/`.mae`) for
docking: adds hydrogens, assigns bond orders, optionally fills missing side
chains (`fill_sidechains`), and sets protonation at `ph` via PROPKA. The
`prepwizard` binary lives in `$SCHRODINGER/utilities`. Runs `prepwizard -WAIT
[-fillsidechains] -propka_pH <ph> <input> <output>` in the output file's
directory; inputs validated (`must_exist=True`), output validated. Returns
`{returncode, output, stdout_tail, stderr_tail}` (`output` is the prepared `.mae`
path if produced, else `null`). The prepared `.mae` feeds `glide_grid` (#11).

#### 11. `glide_grid(receptor_mae, out_grid_zip, center="", ligand_molnum=0, inner_box=10, outer_box=30, timeout_s=1800) -> dict`
**Glide grid generation** — produces the docking grid (`.zip`) that `glide_dock`
(#9) requires, directly from a prepared receptor (`.mae`/`.maegz`) — closing the
gap where no MCP tool built a grid. Define the box with **either** explicit
`center="x,y,z"` coordinates **or** `ligand_molnum` (the 1-based molecule number
of a co-crystallized ligand already in the receptor file; this both centers the
box on and excludes that ligand). One of the two is required (validated), and
`center` is range-checked to numeric `x,y,z`. Writes a Glide `.in`
(`GRIDFILE` / `RECEP_FILE` / `GRID_CENTER` or `LIGAND_MOLECULE` / `INNERBOX` /
`OUTERBOX`), then runs `glide <job>.in -WAIT -OVERWRITE`. Returns `{returncode,
grid, stdout_tail, stderr_tail}` where `grid` is the `.zip` path if produced.
**Consumes a Glide license token.**

#### 12. `prime_mmgbsa(pose_viewer, timeout_s=3600) -> dict`
**Prime MM-GBSA** — binding free-energy (`dG_Bind`) rescoring of docked poses,
far more reliable than the raw Glide score. Input is a Glide pose-viewer file
(the `*_pv.maegz` from `glide_dock`). Runs `prime_mmgbsa <pose_viewer> -WAIT` in
the pose file's directory; Prime drops a trailing `_pv` from the jobname so
`<job>_pv.maegz` -> `<job>-out.csv`. Returns `{returncode, csv, out_maegz,
stdout_tail, stderr_tail}` plus `csv_head` (first 3 lines of the result CSV,
which carries `r_psp_MMGBSA_dG_Bind`) when the CSV exists. **Consumes a Prime
license token.**

---

## Setup

### Prerequisites
- A working Schrodinger Suite install (current target: 2026-2 at
  `D:\Program Files\Schrodinger 2026-2`).
- Python with `venv` (the server venv is independent of the Schrodinger interpreter).

### 1. `$SCHRODINGER` environment variable
The server reads the install root from the `SCHRODINGER` env var; it defaults to
the Windows path `D:\Program Files\Schrodinger 2026-2` if unset. Set it at User
scope (Windows) so it is visible to all sessions:

```powershell
# Windows (PowerShell) — User scope, persists across sessions
[Environment]::SetEnvironmentVariable("SCHRODINGER", "D:\Program Files\Schrodinger 2026-2", "User")
```

```bash
# POSIX (Linux/macOS)
export SCHRODINGER="/opt/schrodinger/suite2026-2"
```

> The MCP registration **also** passes `SCHRODINGER` in the server's `env` block
> (see below), so it works even if the OS-level variable is not set.

### 2. Create the server venv and install deps
The server itself only needs the MCP SDK (`mcp` / FastMCP) — **not** RDKit or
Schrodinger (those live in the Suite interpreter).

```powershell
# from C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install mcp
```

```bash
# POSIX equivalent
python3 -m venv .venv
.venv/bin/python -m pip install mcp
```

### 3. (Optional) smoke-test the Schrodinger backend
`_smoke.py` verifies the building blocks (SMILES → structure, round-trip read,
package import). Run it **inside the Schrodinger interpreter**, not the server venv:

```powershell
& "$env:SCHRODINGER\run.exe" python3 _smoke.py
```

### 4. Register with Claude Code
```powershell
claude mcp add schrodinger `
  -s user `
  -e SCHRODINGER="D:\Program Files\Schrodinger 2026-2" `
  -- "C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\.venv\Scripts\python.exe" `
     "C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\server.py"
```

### 5. Verify
```powershell
claude mcp get schrodinger
```
Expected after registration:
```
schrodinger:
  Scope: User config (available in all your projects)
  Status: ✓ Connected
  Type: stdio
  Command: C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\.venv\Scripts\python.exe
  Args: C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\server.py
  Environment:
    SCHRODINGER=D:\Program Files\Schrodinger 2026-2
```

---

## Cross-platform notes

The server is path-aware and works on Windows and POSIX:

- **`run.exe` vs `run`:** `_run()` prefers `$SCHRODINGER\run.exe` (Windows) and
  falls back to `$SCHRODINGER/run` (Linux/macOS):
  ```python
  def _run():
      win = os.path.join(SCHRODINGER, "run.exe")
      return win if os.path.exists(win) else os.path.join(SCHRODINGER, "run")
  ```
- **Driver executables:** `_driver(name)` applies the same `.exe`-or-bare logic for
  `ligprep` / `qikprop` / `glide`.
- **Paths:** all paths are joined with `os.path.join` and normalized with
  `os.path.abspath`; the default `SCHRODINGER` is a Windows `D:\` path but is
  overridable for POSIX (e.g. `/opt/schrodinger/suite2026-2`).
- **venv interpreter path** differs by OS: `.venv\Scripts\python.exe` (Windows) vs
  `.venv/bin/python` (POSIX) — adjust the `claude mcp add` command accordingly.

---

## How to add a CUSTOM MCP connector to Claude Code (worked example)

This server is a complete, end-to-end example of adding a **custom, locally-built,
stdio** MCP server to Claude Code. Use it as a template.

### Step 1 — Write the server (stdio transport)
Use FastMCP, decorate functions with `@mcp.tool()`, and finish with `mcp.run()`
(stdio is the default transport). Keep tool signatures simple and typed; the
docstring becomes the tool description the model sees.

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("schrodinger")

@mcp.tool()
def molecule_properties(smiles: str) -> dict:
    """Drug-likeness panel for a SMILES: MW, logP, HBD/HBA, TPSA, QED, Lipinski."""
    ...

if __name__ == "__main__":
    mcp.run()
```

### Step 2 — Give it an isolated runtime
Create a dedicated venv so the server's deps never collide with the system /
other projects, and install the MCP SDK:
```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install mcp
```

### Step 3 — Decide the launch command + args
For a stdio server, the **Command** is the interpreter and the **Args** are the
script (plus any flags). Use absolute paths so it works from any project:
- Command: `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\.venv\Scripts\python.exe`
- Args: `C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\server.py`

> Tip: many third-party servers default to an HTTP/SSE transport on a port — if so,
> pass the flag that forces stdio (e.g. the sibling `rdkit` server needs
> `--transport stdio`). This Schrodinger server is stdio-only, so no flag is needed.

### Step 4 — The equivalent JSON config
`claude mcp add` writes this into your config (User scope shown). Anatomy of a
stdio entry:
```json
{
  "mcpServers": {
    "schrodinger": {
      "type": "stdio",
      "command": "C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\schrodinger-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\schrodinger-mcp\\server.py"],
      "env": { "SCHRODINGER": "D:\\Program Files\\Schrodinger 2026-2" }
    }
  }
}
```
Note Windows backslashes must be escaped (`\\`) in JSON. You can edit this by hand,
but prefer `claude mcp add` (next step) so the file stays valid.

### Step 5 — Register via `claude mcp add`
The `--` separator marks the end of options; everything after it is the literal
command + its arguments. `-e KEY=value` adds an env var; `-s user` makes it global
to all your projects (vs the default `local`, or `project` for a checked-in
`.mcp.json`).
```powershell
claude mcp add schrodinger `
  -s user `
  -e SCHRODINGER="D:\Program Files\Schrodinger 2026-2" `
  -- "C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\.venv\Scripts\python.exe" `
     "C:\Users\Prekzursil\source\agent-skills-toolchain\tools\mcp\schrodinger-mcp\server.py"
```
Anatomy of the command:
- `schrodinger` — the server name (how it appears in `claude mcp get/list`).
- `-s user` — scope (`local` | `user` | `project`); default is `local`.
- `-e SCHRODINGER=...` — environment variable(s) passed to the server process.
- `--` — end-of-options sentinel; the rest is the launch command.
- `<python.exe> <server.py>` — Command + Args (no `--transport` flag needed here
  because the server is stdio by default).

### Step 6 — Verify it connected
```powershell
claude mcp get schrodinger      # shows Status: ✓ Connected + the resolved config
claude mcp list                 # lists all servers and their connection status
```
A `✓ Connected` status means Claude Code spawned the process and completed the MCP
handshake. If it shows failed/not connected, run the Command+Args manually in a
terminal to see the stderr (a stdio server should start and wait silently on
stdin). To remove: `claude mcp remove schrodinger -s user`.

---

## Companion servers in this drug-discovery stack
For context, this server sits alongside two sibling MCP servers (all User scope,
all `✓ Connected`):
- **`tooluniverse`** — `uvx tooluniverse==1.2.4` (env `PYTHONIOENCODING=utf-8`);
  2206 biomedical tools (DDI/ADMET/CYP/targets/FDA labels/repurposing/
  pharmacovigilance). Apache-2.0, Harvard Zitnik lab.
- **`rdkit`** — `…\rdkit-mcp-server\.venv\Scripts\python.exe run_server.py
  --transport stdio`; 74 cheminformatics tools. MIT. (Note the required
  `--transport stdio` flag — it defaults to SSE on :8000 otherwise.)