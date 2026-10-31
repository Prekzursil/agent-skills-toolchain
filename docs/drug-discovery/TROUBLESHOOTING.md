---
title: TROUBLESHOOTING
type: note
permalink: dqverify-repo-20261013/docs/drug-discovery/troubleshooting
---

# Drug-Discovery MCP Stack — Troubleshooting

Troubleshooting for the local drug-discovery research stack on **Windows** (with
cross-platform notes). Stack components:

| MCP | Source | Launch (from registered config) |
|-----|--------|---------------------------------|
| `tooluniverse` | `uvx tooluniverse==1.2.4` (Apache-2.0, Harvard Zitnik lab) | `uvx tooluniverse==1.2.4`, env `PYTHONIOENCODING=utf-8` |
| `rdkit` | `tandemai-inc/rdkit-mcp-server` (MIT) at `C:\Users\Prekzursil\source\repos\rdkit-mcp-server` | `.venv\Scripts\python.exe run_server.py --transport stdio` |
| `schrodinger` | custom-built at `C:\Users\Prekzursil\source\repos\schrodinger-mcp` | `.venv\Scripts\python.exe server.py`, env `SCHRODINGER` |
| `gogcli-classroom` | `gogcli-mcp-classroom` (npm -g) over `gog.exe` v0.21.0 at `C:\Users\Prekzursil\tools\gogcli\gog.exe` | `gogcli-mcp-classroom`, env `GOG_ACCOUNT`, `GOG_PATH` |

Each fix below is **symptom → cause → fix**. Paths shown Windows-first; POSIX
equivalents noted where the stack is cross-platform.

> Cross-platform key: `$SCHRODINGER` is `D:\Program Files\Schrodinger 2022-4` on
> this Windows box. On POSIX, set it to your suite root (e.g. `/opt/schrodinger/2022-4`).
> The custom server's `_run()` / `_driver()` helpers try the `.exe` name first,
> then fall back to the bare name — so the same code resolves `run.exe`/`glide.exe`
> on Windows and `run`/`glide` on Linux/macOS, provided `$SCHRODINGER` points at
> the right root.

---

## 1. rdkit MCP — dead version pin (`rdkit==2025.3.1`)

**Symptom.** `uv`/`pip` install of `rdkit-mcp-server` fails resolving its
dependency: `rdkit==2025.3.1` cannot be found / is no longer on PyPI. Server
never starts; shows **Failed to connect** in `claude mcp list`.

**Cause.** `pyproject.toml` (line 24) hard-pins `rdkit==2025.3.1`, which has been
removed from PyPI. A normal `pip install .` tries to satisfy that exact pin and
errors out.

**Fix.** Install a current RDKit first, then install the package **without
re-resolving deps**:

```powershell
# from C:\Users\Prekzursil\source\repos\rdkit-mcp-server
.venv\Scripts\python.exe -m pip install rdkit==2026.3.3 mcp
.venv\Scripts\python.exe -m pip install --no-deps .
```

`--no-deps` is the load-bearing flag — it installs the server package while
skipping the dead `rdkit==2025.3.1` pin (the already-installed `rdkit 2026.3.3`
satisfies imports at runtime). POSIX: same commands with `.venv/bin/python`.

---

## 2. rdkit MCP — defaults to SSE on port 8000 instead of stdio

**Symptom.** The rdkit server starts but Claude Code can't talk to it — it logs
`Starting RDKit MCP Server with transport: sse` / `Server running on
127.0.0.1:8000 using SSE transport`, then sits as an HTTP listener. MCP shows
**Failed to connect** (Claude Code launched it expecting stdio).

**Cause.** `run_server.py` defaults `--transport sse` (and `--port 8000`,
`--host 127.0.0.1`). Without an explicit transport it runs as an SSE HTTP server,
not a stdio child process.

**Fix.** Register with `--transport stdio` in the args (already done in this
stack):

```jsonc
"rdkit": {
  "type": "stdio",
  "command": "C:\\Users\\Prekzursil\\source\\repos\\rdkit-mcp-server\\.venv\\Scripts\\python.exe",
  "args": [
    "C:\\Users\\Prekzursil\\source\\repos\\rdkit-mcp-server\\run_server.py",
    "--transport", "stdio"
  ],
  "env": {}
}
```

Valid transports are `sse`, `stdio`, `streamable_http`. For a stdio MCP client
you **must** pass `--transport stdio`.

---

## 3. Any MCP server shows "Failed to connect"

**Symptom.** `claude mcp list` / `claude mcp get <name>` reports the server as
not connected; tools don't appear after a Claude Code restart.

**Cause.** Almost always the launch command itself errors before the MCP
handshake — wrong interpreter path, missing dependency, an exception at import,
or a non-stdio transport (see #2).

**Fix — reproduce the exact launch by hand.** Run the command + args from the
registered config directly in a terminal:

```powershell
# schrodinger example — run exactly what the config launches:
& "C:\Users\Prekzursil\source\repos\schrodinger-mcp\.venv\Scripts\python.exe" `
  "C:\Users\Prekzursil\source\repos\schrodinger-mcp\server.py"
```

Interpreting what you see:

- **It prints nothing and appears to "hang", waiting on input** → this is
  **healthy**. A stdio MCP server blocks reading JSON-RPC from stdin. Press
  `Ctrl+C` to exit; the server is fine — the problem is elsewhere (env var,
  client registration). You can confirm a clean start by piping empty/EOF input:
  `$null | & "...python.exe" "...server.py"` (it should exit without a traceback).
- **It prints a Python traceback immediately** → that traceback *is* the bug
  (missing module, bad path, syntax error). Fix it, then re-run.
- **Re-verify** registration with `claude mcp get <name>` (the same command used
  to confirm all four servers as ✓ Connected in this stack). Tools only load on
  the **next Claude Code restart** — registering mid-session won't surface them.

POSIX: substitute `.venv/bin/python` and forward slashes.

---

## 4. `gog` — "context deadline exceeded" during OAuth

**Symptom.** `gog auth` (or first `gog ... classroom ...` call) fails with
`context deadline exceeded`; the browser opens but the CLI never receives the
authorization.

**Cause.** The OAuth redirect didn't get back to the CLI in time. With the
`--remote` manual flow this is common when the browser churns (redirects, account
switches, profile picks) and the code never makes it back to `gog`.

**Fix.** Use the **loopback auto-capture** flow (the default, no `--remote`).
`gog` spins up a local listener and captures the redirect automatically — this is
what succeeded for this stack. If you previously tried `--remote`, drop it:

```powershell
& "C:\Users\Prekzursil\tools\gogcli\gog.exe" auth
```

Complete the consent quickly and let it land on the loopback page. If a timeout
still fires, be ready to click through the Google **Allow** screen fast — the
deadline is on the round-trip, not on the listener. On success the token is
stored in the OS keyring (account `prekzursil1993@gmail.com`).

---

## 5. `gog` — OAuth account-chooser stuck / wrong account

**Symptom.** The Google account-chooser keeps reappearing, lands on the wrong
account, or the consent loops without completing.

**Cause.** Multiple signed-in Google accounts and/or a stale browser session;
the chooser intercepts the redirect before the loopback listener gets the code
(related to #4's browser churn).

**Fix.**
- Pick the intended account (`prekzursil1993@gmail.com`) decisively on the first
  chooser screen; don't switch accounts mid-flow.
- Prefer a clean browser profile / incognito window with only the target account
  signed in, so there's no chooser to stall on.
- Re-run the loopback flow (`gog auth`, no `--remote`).
- Verify the round-trip once authorized:
  ```powershell
  & "C:\Users\Prekzursil\tools\gogcli\gog.exe" -a prekzursil1993@gmail.com classroom courses list
  ```
  This returned 3 real courses when verified.

> **Student-account limitation (not a bug):** the authorized account is a
> *student* in Classroom, so **write** tools return HTTP **403**. Reads and your
> **own** submissions work. This is the Classroom API permission model, not a
> stack misconfiguration — don't chase it as an auth failure.

---

## 6. semgrep CRITICAL — "MCP tool param flows into subprocess"

**Symptom.** A security scan (semgrep, e.g. via the semgrep-mcp hook) flags a
**CRITICAL**: untrusted MCP tool parameters reaching `subprocess.run` (command /
argument injection risk).

**Cause.** Calling `subprocess.run(...)` **inside** an `@mcp.tool()` function
means the rule sees client-controlled params flow directly into a subprocess.

**Fix — centralize the subprocess in a non-tool chokepoint + validate paths.**
This is exactly the schrodinger server's design:

- All subprocess execution lives in a single **non-tool** function `_exec(argv,
  …)` (`server.py:52`) that runs a pre-built argv list with **`shell=False`**
  (never `shell=True`). Because it isn't an `@mcp.tool`, untrusted params never
  flow *directly* into `subprocess.run` from a tool.
- Client-supplied paths pass through `_safe_path()` (`server.py:41`) first, which
  rejects empty/flag-like (`-…`) values and normalizes to absolute, before they
  ever reach an argv.
- Structured args are JSON-encoded into a single argv element for the helper
  (`_helper`), so values are inert data, not shell tokens.

> **`nosemgrep` is NOT honored by the semgrep-mcp hook.** You cannot suppress
> this finding with an inline `# nosemgrep` comment — the hook ignores it. The
> rule only clears when the `subprocess.run` call is genuinely **out of** the
> `@mcp.tool` function body (i.e. behind the `_exec` chokepoint). Refactor, don't
> suppress.

---

## 7. `$SCHRODINGER` unset / wrong — silent fallback to the Windows default

**Symptom.** Schrodinger tools fail with `run`/driver **not found**, or operate
against the *wrong* suite — but there is **no clean "missing env var" error**.

**Cause.** `server.py:22` reads
`os.environ.get("SCHRODINGER", r"D:\Program Files\Schrodinger 2022-4")` — if the
env var is unset it **silently falls back** to the hard-coded Windows path. On a
machine where the suite lives elsewhere (or on POSIX), `_run()`/`_driver()` then
resolve to a non-existent `run.exe`/`run`, and you get a not-found / wrong-path
failure downstream rather than an upfront "SCHRODINGER not set" message.

**Fix.**
- Set the env var to the real suite root and register it with the server:
  ```powershell
  # User-scope (persists), Windows:
  setx SCHRODINGER "D:\Program Files\Schrodinger 2022-4"
  ```
  POSIX: `export SCHRODINGER=/opt/schrodinger/2022-4` (in your shell profile).
- The MCP registration already pins it via `env`:
  ```jsonc
  "schrodinger": { ..., "env": { "SCHRODINGER": "D:\\Program Files\\Schrodinger 2022-4" } }
  ```
- Quick sanity check (also the `schrodinger_version` tool): from the suite root,
  `run.exe -v` (Windows) / `run -v` (POSIX) should print build **79134**. If it
  doesn't resolve, `$SCHRODINGER` is wrong.

---

## 8. Windows paths with spaces (`D:\Program Files\Schrodinger 2022-4`)

**Symptom.** Path with a space breaks: a launch fails, or an argument is split at
the space into two tokens.

**Cause.** Spaces are only a problem when a path is passed through a **shell** or
unquoted argument string. The install root (`D:\Program Files\Schrodinger
2022-4`) and the venv paths both contain spaces/long names.

**Fix.**
- **Inside the server, this is already safe:** `_exec` builds an **argv list** and
  runs with `shell=False`, so each element (including space-containing paths) is
  passed as a single, correctly-quoted argument — no shell word-splitting. You do
  **not** need to add quotes inside the Python code.
- **The real risk is registration/env quoting.** In `.claude.json`, keep each
  space-containing value as one JSON string and escape backslashes
  (`"D:\\Program Files\\Schrodinger 2022-4"`).
- **When running launch commands by hand** in PowerShell, quote the whole path
  and use the call operator: `& "C:\path with spaces\python.exe" "C:\path with spaces\server.py"`.
- For `setx SCHRODINGER "D:\Program Files\Schrodinger 2022-4"`, keep the quotes.

---

## 9. Schrodinger driver tools — license-token errors

**Symptom.** A **driver** tool (`prepwizard`, `glide_grid`, `ligprep`,
`qikprop_admet`, `glide_dock`, or `prime_mmgbsa`) fails or hangs with a
licensing error (e.g. no token available, license server unreachable, feature
not licensed). Structure/cheminformatics tools (`molecule_properties`,
`smiles_to_3d`, `convert_structure`, `backend_info`) keep working.

**Cause.** Only the **driver** tools consume Schrodinger **license tokens** and
run synchronously with `-WAIT`:

- `prepwizard` → `prepwizard -WAIT [-fillsidechains] -propka_pH <ph> <in> <out>`
- `glide_grid` → `glide <job>.in -WAIT -OVERWRITE` (consumes a **Glide** token)
- `ligprep` → `ligprep -i… <in> -omae <out> -WAIT`
- `qikprop_admet` → `qikprop -WAIT <structure>`
- `glide_dock` → `glide <job>.in -WAIT -OVERWRITE` (consumes a **Glide** token)
- `prime_mmgbsa` → `prime_mmgbsa <pose_viewer> -WAIT` (consumes a **Prime** token)

The license-token-free tools (RDKit-backed properties/3D-embed, structure
conversion, version/info) don't need a token — which is why they still respond
when the driver tools fail.

> **Validated live end-to-end on 2026-06-06** (3PTB pipeline + qikprop on
> warfarin); see `schrodinger-mcp/VALIDATION.md`. The driver tools have been
> exercised against a live license server, so a failure here is a real
> environment/license issue (token unavailable, server unreachable), not an
> untested-code regression.

**Fix.**
- Confirm a license is available before invoking drivers: from the suite root run
  `licadmin STAT` (Windows: `licadmin.exe STAT`) and check the relevant feature
  tokens (GLIDE_*, QIKPROP, etc.) are present and not all checked out.
- Verify `$SCHRODINGER` and that `run -v` resolves (see #7) — a wrong suite root
  also breaks the driver path resolution.
- These tools are **synchronous** (`-WAIT`) and can be long-running — the server
  sets generous timeouts (`ligprep` 1200s, `qikprop` 900s, `glide` 3600s). A
  `timeout after Ns` result means the job exceeded that budget, not a license
  failure; raise `timeout_s` or investigate the job logs in the working dir.

---

## Quick reference — verifying the whole stack

```powershell
# 1. Schrodinger suite resolves (expect build 79134):
& "D:\Program Files\Schrodinger 2022-4\run.exe" -v

# 2. Each MCP connects (run after a Claude Code restart):
claude mcp get tooluniverse
claude mcp get rdkit
claude mcp get schrodinger
claude mcp get gogcli-classroom

# 3. Classroom round-trip (reads work on the student account):
& "C:\Users\Prekzursil\tools\gogcli\gog.exe" -a prekzursil1993@gmail.com classroom courses list
```

The `gogcli-classroom` MCP was registered with:

```
claude mcp add gogcli-classroom -e GOG_ACCOUNT=<email> -e GOG_PATH=...\gog.exe -- gogcli-mcp-classroom
```

and confirmed **✓ Connected** via `claude mcp get`. (Tools become available only
after the next Claude Code restart.)