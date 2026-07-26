# mcpctl

Read-only MCP inventory + health matrix core. Pure functions over the **five** on-disk
MCP configuration scopes, credential-name-only redaction, and a read-only CLI.

**Read-only, by construction.** There is no enable/disable, no reconnect, no config
edit, and no file write anywhere in the package. `tests/test_cli.py` asserts that
mechanically over the **AST** of every module (no write call, no out-of-process call)
rather than trusting this sentence. Live mutation, the localhost web GUI and
curation-apply are separate, later work units.

```powershell
python -m mcpctl                 # the health/status matrix (default)
python -m mcpctl topology        # which scopes exist, what each holds, the precedence
python -m mcpctl credentials     # env VARIABLE NAMES + present/absent/reference
python -m mcpctl conflicts       # servers whose scopes disagree
python -m mcpctl matrix --json   # observation envelope + rows, machine-readable

python -m mcpctl matrix --project C:/Users/you/some/dir   # apply a projects[] row
python -m mcpctl matrix --home H:/other-profile           # read a different profile
```

---

## The five scopes, and why the count matters

Measured on this box 2026-07-26. The counts are that day's observation; the scope
**set** and each key's **shape** are the durable facts.

| file | key | shape | n |
|---|---|---|---|
| `~/.claude.json` | `mcpServers` | `dict` name -> spec | 66 |
| `~/.claude.json` (line 949) | `disabledMcpServers` | `list[str]` | 122 |
| `~/.claude.json` | `projects[<exact cwd>].disabledMcpServers` | `list[str]` | see below |
| `~/.mcp.json` | `mcpServers` | `dict` (project scope) | 14 |
| `~/.claude/settings.local.json` (line 41) | `enabledMcpjsonServers` | `list[str]` | 12 |
| `~/.claude/settings.local.json` | `enableAllProjectMcpServers` | `bool` | `False` |
| `~/.claude/settings.json` (line 82) | `deniedMcpServers` | **`list[{"serverName": str}]`** | 5 |
| `~/.claude/.mcp-disabled-defaults.json` | `disabledMcpServers` | `list[str]` (ADVISORY) | 85 |

Two shapes bite a naive reader:

1. **`deniedMcpServers` holds OBJECTS, not strings.** Observed element:
   `{"serverName": "markitdown"}`. A `set(list_of_str)` reader raises `TypeError`; a
   tolerant one silently yields nothing. This key is not modelled by `tools/mcp-manager`
   at all, so those 5 denials are invisible to it.
2. **`projects` is keyed by the session's EXACT cwd.** An ancestor row must not be
   substituted. Measured: for cwd
   `C:/Users/Prekzursil/.claude/agent-worktrees/agent-364079870` there is **no** row,
   while the ancestor row `C:/Users/Prekzursil` carries 117 disabled names -- a different
   project. Attributing that 117 to the session is wrong in both directions.

`.mcp-disabled-defaults.json` is a **template**, not a scope the host consults: a tool
copies it INTO a project's `disabledMcpServers`. mcpctl labels it `ADVISORY` and never
lets it decide a state.

## Precedence -- measured, and it refuted the natural guess

```
settings-denied  >  claude-project-disabled  >  claude-user-disabled  >  mcpjson-approved
```

Evidence, using this session's own injected MCP tool namespaces as a liveness signal
that is mechanically independent of the JSON keys being read:

* **Approval does NOT override a disable.** `ghidra-mcp`, `hexstrike-ai` and
  `ida-pro-mcp` are each listed in `enabledMcpjsonServers` **and** in the root
  `disabledMcpServers`, and none of the three is live. So `mcpjson-approved` sits
  *below* both disable lists.
* **The root `disabledMcpServers` is effective**, contradicting an earlier note in this
  estate that recorded it as inert: 43/43 servers defined only in `~/.claude.json` and
  listed there are absent, as are the http-transport `apify`, `linear` and `notion`.
* **Detector control:** 117 servers listed in both disable scopes are absent, so the
  liveness signal can in fact see the "disabled" state it is being asked about --
  its silence is meaningful rather than vacuous.
* **One unexplained anomaly, disclosed rather than smoothed over:** `angr` is in the
  root `disabledMcpServers`, is *not* in `enabledMcpjsonServers`, and **is live**. It is
  the sole exception in 46 root-disabled defined servers. A transport hypothesis was
  raised and then **REFUTED** by a second probe -- `angr`'s root definition is
  `type: "sse"`, but the http-transport `apify`/`linear`/`notion` are root-disabled and
  correctly absent, so "remote transports bypass the disable list" is false.
  `UNVERIFIED` -- the mechanism behind the `angr` exception is not established.
  **Settling experiment:** read the `/mcp` panel (or `claude mcp list`) and compare each
  server's `failed` vs `disabled` glyph against these two lists; a per-server state from
  the host itself distinguishes "suppressed by config" from "started and errored", which
  a tool-namespace probe cannot.

**Design consequence, and the whole point of this package:** no single scope is
authoritative, so mcpctl never reduces a server to a bare enabled/disabled boolean.
Every `Resolution` carries `basis` (every scope that contributed), `conflicts` (a note
whenever two scopes disagree) and `inferred` (true when more than one scope spoke). The
matrix marks an inferred state with `~`.

## Security

* **Structural, not cosmetic.** `safety.env_fields` is the only route by which a server's
  `env` block enters the data model, and it captures a variable **name** plus a
  three-way classification (`present` / `absent` / `reference` for a `${VAR}`
  indirection) -- never the value. A credential cannot leak from a record that never
  held it, which is strictly stronger than redacting at render time.
* **Textual defence in depth.** Free text mcpctl *does* carry -- `command`, `args`, and
  an injected `last_error` -- passes an always-on redaction layer.
* **The layer does not depend on `monitorcore`.** `monitorcore.redact`'s pattern set
  (`redact.py:32-59`) covers `sk-`, `ghp_`, `github_pat_`, `AKIA`, `xox?-`, Bearer-JWT,
  PEM, `.gitcrypt.key`, `gh[oure]_` and a bare JWT -- and nothing else. The shapes this
  box's MCP `env` blocks actually carry include `xai-...` and `AIza...` keys plus wholly
  opaque tokens (`SONARQUBE_TOKEN`, `FB_PAGE_ACCESS_TOKEN`, `DIGITALOCEAN_API_TOKEN`,
  ...), none of which match any upstream pattern. mcpctl therefore owns its own patterns
  and layers monitorcore's *after* them, so the floor never depends on that import
  resolving. Note mcpctl's own set does **not** include a PEM pattern; PEM masking comes
  only from the optional monitorcore layer.
* **Control bytes are stripped** (C0 except TAB/LF/CR, DEL, C1, ESC) before any string
  can reach a terminal, and the renderers emit no escapes at all -- so an OSC-8 / OSC-52
  payload smuggled through a server name in a config file cannot reach the terminal.

### monitorcore reuse, and how drift is caught

`monitorcore.textsafe.strip_controls` is reused when importable, with a byte-identical
local fallback otherwise. `tests/test_safety_contract.py` loads monitorcore's real module
**by path** -- not by import -- and asserts the two agree across the whole `0x00-0xFF`
range. Loading by path is deliberate: the drift detector then runs in every environment
with no `pip install -e ../monitorcore` and no `skipif`. A skip would make it silent in
exactly the state it exists to catch.

## Reuse boundary -- what already existed and why it is not reused

* **`tools/mcp-manager`** -- the closest existing artifact: a cross-plane MCP inventory
  CLI + PySide6 GUI with presets, and it is CI-gated at 100%. mcpctl does not extend it
  and does not duplicate its purpose. It models **four** planes (claude-user,
  claude-project, codex `config.toml`, funnel) and reads the root `disabledMcpServers` as
  the `claude-user` plane's verdict (`core/inventory.py:80`); it does **not** read
  `deniedMcpServers` or `enabledMcpjsonServers` at all, it resolves to a single
  `enabled: bool` (`core/models.py:48`) with no record of which scope decided, and its
  `ServerRow` carries a raw `command` string and plane-specific raw `extra` data with no
  redaction layer. mcpctl's contribution is exactly the three things that absence costs:
  the two unmodelled scopes, the scope-qualified non-boolean state, and
  credential-name-only rendering. mcp-manager additionally *writes* config (its reason
  for existing); mcpctl deliberately cannot.
* **`tools/mcp/mcp-host-supervisor`** has a `ServerSpec` dataclass, but it models a
  loopback-published shared host (`name`, `port`, `command`, `health_path`) and its
  README states it never touches `~/.claude.json`. Different domain; nothing to reuse.
* **`monitorcore.databricks_source.Liveness`** is an 8-state `StrEnum` unit-liveness
  vocabulary for Databricks units, not a per-server observation record. Same word,
  different concept.

## Gate

```powershell
cd tools/mcpctl
pip install -e ".[dev]"
pytest --cov=mcpctl --cov-branch --cov-report=term-missing --cov-fail-under=100
basedpyright mcpctl        # 1.39.8, standard mode
```

100% line + branch, hermetic (fixtures only -- no live MCP call, no network, no process
probe), with **zero `# pragma: no cover` in the package source**. The editable install is
load-bearing for the test step: `tests/` is a subdirectory, so bare `pytest` -- which,
unlike `python -m pytest`, does not put the cwd on `sys.path` -- cannot import `mcpctl`
without it.

Liveness (`tool_count`, `last_error`, `pid`, `rss_bytes`) is **injected**. `None` means
"not measured", never "zero" and never "dead": the matrix prints `-` for an unmeasured
tool count so an absent measurement can never read as a health verdict.
