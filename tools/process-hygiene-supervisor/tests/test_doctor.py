"""Tests for hygiene_doctor: read-only estate checks and the MCP config rewriter."""

from __future__ import annotations

import json
import pathlib

import hygiene_doctor as doc

NOW = 1_788_324_600


class FakeProbe:
    """Filesystem + command + clock seam. Paths are keyed by their posix string."""

    def __init__(
        self,
        files: dict[str, str] | None = None,
        commands: dict[str, tuple[int, str]] | None = None,
        now=NOW,
    ):
        self.files = {k: v for k, v in (files or {}).items()}
        self.commands = commands or {}
        self.now_value = now
        self.calls: list[list[str]] = []
        self.written: dict[str, str] = {}

    def _k(self, path) -> str:
        return pathlib.PurePath(str(path)).as_posix()

    def exists(self, path) -> bool:
        return self._k(path) in self.files

    def read_text(self, path) -> str:
        return self.files[self._k(path)]

    def write_text(self, path, text) -> None:
        self.files[self._k(path)] = text
        self.written[self._k(path)] = text

    def glob(self, root, pattern):
        # supports the two patterns the resolver uses: "*/node_modules/<pkg>/package.json"
        # and "<pkg>/package.json" relative to root
        root = self._k(root).rstrip("/")
        want_tail = pattern.replace("*/", "")
        out = []
        for key in self.files:
            if key.startswith(root + "/") and key.endswith(want_tail):
                out.append(pathlib.PurePosixPath(key))
        return sorted(out)

    def run(self, args):
        self.calls.append(list(args))
        code, out = self.commands.get(args[0], (127, ""))
        return code, out

    def now(self) -> int:
        return self.now_value


ROOT = "C:/Users/x/.agent-guard/process-hygiene"
HOME = "C:/Users/x"


def heartbeat(ts, apply=True):
    return json.dumps(
        {
            "schema": "process-hygiene-heartbeat-v1",
            "ts": ts,
            "apply": apply,
            "tier": "normal",
        }
    )


def probe(**over):
    files = {
        f"{ROOT}/state/heartbeat.json": heartbeat(NOW - 120),
        f"{HOME}/.wslconfig": "[wsl2]\nmemory=8GB\n\n[experimental]\nautoMemoryReclaim=dropCache\n",
        f"{HOME}/.claude.json": json.dumps(
            {
                "mcpServers": {
                    "git": {"command": "node", "args": ["C:/x/git/dist/index.js"]}
                }
            }
        ),
    }
    files.update(over.pop("files", {}))
    commands = {
        "claude": (0, "2.1.200 (Claude Code)"),
        "codex": (0, "codex-cli 0.90.0"),
    }
    commands.update(over.pop("commands", {}))
    return FakeProbe(files=files, commands=commands, **over)


def run_doctor(p, **kw):
    return doc.run_checks(p, root=ROOT, home=HOME, interval_minutes=5, **kw)


def by_id(findings, ident):
    return [f for f in findings if f.id == ident]


# ----------------------------------------------------------------- heartbeat


def test_healthy_heartbeat_is_ok():
    findings = run_doctor(probe())
    beat = by_id(findings, "heartbeat")[0]
    assert beat.severity == "ok"
    assert "2 min" in beat.summary


def test_stale_heartbeat_is_action_required_with_the_age():
    findings = run_doctor(
        probe(files={f"{ROOT}/state/heartbeat.json": heartbeat(NOW - 3 * 3600)})
    )
    beat = by_id(findings, "heartbeat")[0]
    assert beat.severity == "action_required"
    assert "180 min" in beat.summary
    assert "Get-ScheduledTask" in beat.remediation


def test_missing_heartbeat_means_the_supervisor_never_ran():
    p = probe()
    del p.files[f"{ROOT}/state/heartbeat.json"]
    beat = by_id(run_doctor(p), "heartbeat")[0]
    assert beat.severity == "action_required"
    assert "never" in beat.summary


def test_unreadable_heartbeat_is_reported_not_raised():
    beat = by_id(
        run_doctor(probe(files={f"{ROOT}/state/heartbeat.json": "{not json"})),
        "heartbeat",
    )[0]
    assert beat.severity == "action_required"
    assert "unreadable" in beat.summary


def test_report_only_mode_is_surfaced_as_info():
    beat = by_id(
        run_doctor(
            probe(
                files={f"{ROOT}/state/heartbeat.json": heartbeat(NOW - 60, apply=False)}
            )
        ),
        "heartbeat",
    )[0]
    assert beat.severity == "ok"
    assert "REPORT-ONLY" in beat.summary


# ------------------------------------------------------------- runtime versions


def test_runtime_versions_compare_against_known_fixes():
    findings = run_doctor(probe(commands={"claude": (0, "2.1.100 (Claude Code)")}))
    claude = by_id(findings, "runtime-version:claude")[0]
    assert claude.severity == "warn"
    assert "2.1.153" in claude.remediation
    codex = by_id(findings, "runtime-version:codex")[0]
    assert (
        codex.severity == "info"
    )  # no version gate we can vouch for; report + advisory
    assert "#19753" in codex.remediation


def test_runtime_version_current_is_ok_and_missing_binary_is_info():
    findings = run_doctor(probe(commands={"claude": (0, "2.1.212 (Claude Code)")}))
    assert by_id(findings, "runtime-version:claude")[0].severity == "ok"
    findings = run_doctor(probe(commands={"claude": (127, "")}))
    assert by_id(findings, "runtime-version:claude")[0].severity == "info"


def test_version_parsing_is_tolerant():
    assert doc.parse_version("2.1.153 (Claude Code)") == (2, 1, 153)
    assert doc.parse_version("codex-cli 0.90.0") == (0, 90, 0)
    assert doc.parse_version("v1.2") == (1, 2)
    assert doc.parse_version("garbage") is None


# ------------------------------------------------------------------ wslconfig


def test_wslconfig_correct_placement_is_ok():
    assert by_id(run_doctor(probe()), "wslconfig")[0].severity == "ok"


def test_wslconfig_misplaced_experimental_keys_are_flagged():
    bad = "[wsl2]\nmemory=8GB\nautoMemoryReclaim=gradual\nsparseVhd=true\n"
    finding = by_id(run_doctor(probe(files={f"{HOME}/.wslconfig": bad})), "wslconfig")[
        0
    ]
    assert finding.severity == "warn"
    assert "autoMemoryReclaim" in finding.summary and "sparseVhd" in finding.summary
    assert "[experimental]" in finding.remediation


def test_wslconfig_missing_reclaim_and_missing_file():
    finding = by_id(
        run_doctor(probe(files={f"{HOME}/.wslconfig": "[wsl2]\nmemory=8GB\n"})),
        "wslconfig",
    )[0]
    assert finding.severity == "warn"
    assert "autoMemoryReclaim" in finding.summary
    p = probe()
    del p.files[f"{HOME}/.wslconfig"]
    finding = by_id(run_doctor(p), "wslconfig")[0]
    assert finding.severity == "warn"
    assert "no .wslconfig" in finding.summary


def test_wslconfig_gradual_is_noted():
    text = "[wsl2]\nmemory=8GB\n[experimental]\nautoMemoryReclaim=gradual\n"
    finding = by_id(run_doctor(probe(files={f"{HOME}/.wslconfig": text})), "wslconfig")[
        0
    ]
    assert finding.severity == "info"
    assert "gradual" in finding.summary


# ----------------------------------------------------------- mcp config scan


CLAUDE_JSON = {
    "mcpServers": {
        "git": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-git"]},
        "fs": {
            "command": "cmd",
            "args": [
                "/c",
                "npx",
                "-y",
                "@modelcontextprotocol/server-filesystem",
                "C:/w",
            ],
        },
        "py": {"command": "uvx", "args": ["mcp-server-fetch"]},
        "direct": {"command": "node", "args": ["C:/x/dist/index.js"]},
        "http": {"url": "http://127.0.0.1:8765/mcp"},
    }
}
CODEX_TOML = """
[mcp_servers.git]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-git"]

[mcp_servers.direct]
command = "node"
args = ["C:/x/dist/index.js"]
"""


def test_mcp_scan_finds_wrapper_launched_servers_across_json_and_toml():
    p = probe(
        files={
            f"{HOME}/.claude.json": json.dumps(CLAUDE_JSON),
            f"{HOME}/.codex/config.toml": CODEX_TOML,
        }
    )
    findings = run_doctor(p)
    scan = by_id(findings, "mcp-wrappers")[0]
    assert scan.severity == "warn"
    names = {
        (d["file"].rsplit("/", 1)[-1], d["server"]) for d in scan.detail["servers"]
    }
    assert names == {
        (".claude.json", "git"),
        (".claude.json", "fs"),
        (".claude.json", "py"),
        ("config.toml", "git"),
    }
    assert "direct" not in {d["server"] for d in scan.detail["servers"]}
    assert "rewrite-mcp" in scan.remediation


def test_mcp_scan_all_direct_is_ok_and_malformed_file_is_reported():
    assert by_id(run_doctor(probe()), "mcp-wrappers")[0].severity == "ok"
    p = probe(files={f"{HOME}/.claude.json": "{broken"})
    scan = by_id(run_doctor(p), "mcp-wrappers")[0]
    assert scan.severity == "warn"
    assert any("unreadable" in e for e in scan.detail["errors"])


def test_mcp_scan_handles_cursor_and_grok_files_too():
    p = probe(
        files={
            f"{HOME}/.cursor/mcp.json": json.dumps(
                {"mcpServers": {"pw": {"command": "npx", "args": ["@playwright/mcp"]}}}
            ),
            f"{HOME}/.grok/config.toml": '[mcp_servers.bridge]\ncommand = "cmd"\nargs = ["/c", "npx", "agentbridge"]\n',
        }
    )
    servers = by_id(run_doctor(p), "mcp-wrappers")[0].detail["servers"]
    assert {d["server"] for d in servers} == {"pw", "bridge"}


# ------------------------------------------------------------------- doctor CLI


def test_cli_human_and_json_output_and_exit_code(capsys):
    p = probe(files={f"{ROOT}/state/heartbeat.json": heartbeat(NOW - 3 * 3600)})
    code = doc.main(["--root", ROOT, "--home", HOME, "--json"], probe=p)
    out = json.loads(capsys.readouterr().out)
    assert code == 1  # an ACTION_REQUIRED finding makes the exit code non-zero
    assert any(
        f["id"] == "heartbeat" and f["severity"] == "action_required"
        for f in out["findings"]
    )
    code = doc.main(["--root", ROOT, "--home", HOME], probe=probe())
    text = capsys.readouterr().out
    assert code == 0
    assert "SUCCESS:process-hygiene-doctor" in text
    assert "[ok]" in text


def test_cli_digest_appends_one_stale_line_with_cooldown(capsys):
    p = probe(files={f"{ROOT}/state/heartbeat.json": heartbeat(NOW - 3 * 3600)})
    digest = f"{ROOT}/DIGEST.md"
    doc.main(["--root", ROOT, "--home", HOME, "--digest", digest], probe=p)
    assert p.files[digest].count("\n") == 1
    line = p.files[digest].strip()
    assert (
        line.startswith("[")
        and "[process-hygiene-doctor] ACTION_REQUIRED:" in line
        and "PROPOSE:" in line
    )
    # same finding again inside the cooldown: no second line
    doc.main(["--root", ROOT, "--home", HOME, "--digest", digest], probe=p)
    assert p.files[digest].count("\n") == 1
    # after the cooldown it is repeated
    p.now_value = NOW + 13 * 3600
    doc.main(["--root", ROOT, "--home", HOME, "--digest", digest], probe=p)
    assert p.files[digest].count("\n") == 2
    # a healthy estate never writes a digest line
    healthy = probe()
    doc.main(["--root", ROOT, "--home", HOME, "--digest", digest], probe=healthy)
    assert digest not in healthy.files


def test_default_probe_is_the_real_filesystem(tmp_path):
    real = doc.RealProbe()
    target = tmp_path / "a.txt"
    real.write_text(target, "hi")
    assert real.exists(target) and real.read_text(target) == "hi"
    assert real.now() > 1_700_000_000
    (tmp_path / "n" / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "n" / "node_modules" / "pkg" / "package.json").write_text("{}")
    assert [p.name for p in real.glob(tmp_path, "*/node_modules/pkg/package.json")] == [
        "package.json"
    ]
    code, out = real.run(["python3", "-c", "print('v')"])
    assert code == 0 and out.strip() == "v"
    code, _ = real.run(["definitely-not-a-binary-xyz"])
    assert code == 127


# ---------------------------------------------------------------- rewrite-mcp


NPX_CACHE = f"{HOME}/AppData/Local/npm-cache/_npx"
NPM_PREFIX = f"{HOME}/AppData/Roaming/npm"
UV_TOOLS = f"{HOME}/AppData/Roaming/uv/tools"


def resolver_probe(config=CLAUDE_JSON):
    files = {
        f"{HOME}/.claude.json": json.dumps(config),
        f"{NPX_CACHE}/abc123/node_modules/@modelcontextprotocol/server-git/package.json": json.dumps(
            {
                "name": "@modelcontextprotocol/server-git",
                "bin": {"mcp-server-git": "dist/index.js"},
            }
        ),
        f"{NPM_PREFIX}/node_modules/@modelcontextprotocol/server-filesystem/package.json": json.dumps(
            {"name": "@modelcontextprotocol/server-filesystem", "bin": "dist/index.js"}
        ),
        f"{UV_TOOLS}/mcp-server-fetch/Scripts/mcp-server-fetch.exe": "MZ",
    }
    return FakeProbe(files=files)


def test_rewrite_resolves_npx_cmd_and_uvx_wrappers_to_direct_executables():
    p = resolver_probe()
    result = doc.rewrite_mcp(
        p,
        f"{HOME}/.claude.json",
        npx_cache=NPX_CACHE,
        npm_prefix=NPM_PREFIX,
        uv_tools=UV_TOOLS,
        node="C:/Program Files/nodejs/node.exe",
    )
    servers = result["rewritten"]["mcpServers"]
    assert servers["git"] == {
        "command": "C:/Program Files/nodejs/node.exe",
        "args": [
            f"{NPX_CACHE}/abc123/node_modules/@modelcontextprotocol/server-git/dist/index.js"
        ],
    }
    assert servers["fs"]["command"] == "C:/Program Files/nodejs/node.exe"
    assert servers["fs"]["args"] == [
        f"{NPM_PREFIX}/node_modules/@modelcontextprotocol/server-filesystem/dist/index.js",
        "C:/w",
    ]
    assert servers["py"] == {
        "command": f"{UV_TOOLS}/mcp-server-fetch/Scripts/mcp-server-fetch.exe",
        "args": [],
    }
    assert servers["direct"] == CLAUDE_JSON["mcpServers"]["direct"]  # untouched
    assert servers["http"] == CLAUDE_JSON["mcpServers"]["http"]  # untouched
    assert result["changed"] == ["fs", "git", "py"]
    assert result["unresolved"] == []
    assert (
        '-  "command": "npx"' in result["diff"] or '"command": "npx"' in result["diff"]
    )


def test_rewrite_reports_unresolved_packages_and_leaves_them_alone():
    config = {
        "mcpServers": {
            "ghost": {"command": "npx", "args": ["-y", "@nobody/ghost-server"]},
            "uv": {"command": "uvx", "args": ["not-installed"]},
        }
    }
    p = resolver_probe(config)
    result = doc.rewrite_mcp(
        p,
        f"{HOME}/.claude.json",
        npx_cache=NPX_CACHE,
        npm_prefix=NPM_PREFIX,
        uv_tools=UV_TOOLS,
        node="node",
    )
    assert result["changed"] == []
    assert {u["server"] for u in result["unresolved"]} == {"ghost", "uv"}
    assert (
        "npx -y @nobody/ghost-server" in result["unresolved"][0]["hint"]
        or "install" in result["unresolved"][0]["hint"]
    )
    assert result["rewritten"] == config


def test_rewrite_keeps_npx_flags_out_of_the_entry_args_and_picks_the_right_bin():
    config = {
        "mcpServers": {
            "multi": {
                "command": "npx",
                "args": ["--yes", "--package=@x/tool", "@x/tool", "--port", "1"],
            },
        }
    }
    files = {
        f"{HOME}/.claude.json": json.dumps(config),
        f"{NPM_PREFIX}/node_modules/@x/tool/package.json": json.dumps(
            {"name": "@x/tool", "bin": {"other": "o.js", "tool": "dist/cli.js"}}
        ),
    }
    p = FakeProbe(files=files)
    result = doc.rewrite_mcp(
        p,
        f"{HOME}/.claude.json",
        npx_cache=NPX_CACHE,
        npm_prefix=NPM_PREFIX,
        uv_tools=UV_TOOLS,
        node="node",
    )
    assert result["rewritten"]["mcpServers"]["multi"]["args"] == [
        f"{NPM_PREFIX}/node_modules/@x/tool/dist/cli.js",
        "--port",
        "1",
    ]


def test_rewrite_handles_bin_dict_with_no_matching_name_and_missing_bin():
    config = {
        "mcpServers": {
            "a": {"command": "npx", "args": ["@x/a"]},
            "b": {"command": "npx", "args": ["@x/b"]},
        }
    }
    files = {
        f"{HOME}/.claude.json": json.dumps(config),
        f"{NPM_PREFIX}/node_modules/@x/a/package.json": json.dumps(
            {"name": "@x/a", "bin": {"z1": "one.js", "z2": "two.js"}}
        ),
        f"{NPM_PREFIX}/node_modules/@x/b/package.json": json.dumps(
            {"name": "@x/b", "main": "index.js"}
        ),
    }
    result = doc.rewrite_mcp(
        FakeProbe(files=files),
        f"{HOME}/.claude.json",
        npx_cache=NPX_CACHE,
        npm_prefix=NPM_PREFIX,
        uv_tools=UV_TOOLS,
        node="node",
    )
    # ambiguous bin dict -> unresolved with a hint; no bin but a main -> use main
    assert [u["server"] for u in result["unresolved"]] == ["a"]
    assert result["rewritten"]["mcpServers"]["b"]["args"] == [
        f"{NPM_PREFIX}/node_modules/@x/b/index.js"
    ]


def test_rewrite_uv_tool_run_form_and_python_module_form():
    config = {
        "mcpServers": {
            "u": {"command": "uv", "args": ["tool", "run", "mcp-server-fetch", "--x"]},
            "m": {
                "command": "cmd",
                "args": ["/c", "python", "-m", "basic_memory", "mcp"],
            },
        }
    }
    p = resolver_probe(config)
    result = doc.rewrite_mcp(
        p,
        f"{HOME}/.claude.json",
        npx_cache=NPX_CACHE,
        npm_prefix=NPM_PREFIX,
        uv_tools=UV_TOOLS,
        node="node",
    )
    assert result["rewritten"]["mcpServers"]["u"] == {
        "command": f"{UV_TOOLS}/mcp-server-fetch/Scripts/mcp-server-fetch.exe",
        "args": ["--x"],
    }
    # `cmd /c python ...` just drops the shell: python is already a direct executable
    assert result["rewritten"]["mcpServers"]["m"] == {
        "command": "python",
        "args": ["-m", "basic_memory", "mcp"],
    }


def test_rewrite_cli_dry_run_writes_sidecar_and_apply_backs_up_then_writes(capsys):
    p = resolver_probe()
    target = f"{HOME}/.claude.json"
    code = doc.main(
        [
            "rewrite-mcp",
            "--config",
            target,
            "--npx-cache",
            NPX_CACHE,
            "--npm-prefix",
            NPM_PREFIX,
            "--uv-tools",
            UV_TOOLS,
            "--node",
            "node",
        ],
        probe=p,
    )
    out = capsys.readouterr().out
    assert code == 0
    assert f"{target}.rewritten.json" in p.written
    assert target not in p.written  # dry run never touches the original
    assert "changed: fs, git, py" in out
    code = doc.main(
        [
            "rewrite-mcp",
            "--config",
            target,
            "--npx-cache",
            NPX_CACHE,
            "--npm-prefix",
            NPM_PREFIX,
            "--uv-tools",
            UV_TOOLS,
            "--node",
            "node",
            "--apply",
        ],
        probe=p,
    )
    assert code == 0
    backups = [k for k in p.written if ".BEFORE-" in k]
    assert len(backups) == 1
    assert json.loads(p.files[target])["mcpServers"]["git"]["command"] == "node"


def test_rewrite_cli_refuses_toml_and_missing_files(capsys):
    p = FakeProbe(files={f"{HOME}/.codex/config.toml": CODEX_TOML})
    code = doc.main(["rewrite-mcp", "--config", f"{HOME}/.codex/config.toml"], probe=p)
    assert code == 2
    assert "JSON" in capsys.readouterr().out
    code = doc.main(["rewrite-mcp", "--config", f"{HOME}/nope.json"], probe=p)
    assert code == 2


def test_rewrite_cli_exit_code_1_when_something_stays_unresolved(capsys):
    config = {"mcpServers": {"ghost": {"command": "npx", "args": ["@nobody/ghost"]}}}
    p = FakeProbe(files={f"{HOME}/.claude.json": json.dumps(config)})
    code = doc.main(
        [
            "rewrite-mcp",
            "--config",
            f"{HOME}/.claude.json",
            "--npx-cache",
            NPX_CACHE,
            "--npm-prefix",
            NPM_PREFIX,
            "--uv-tools",
            UV_TOOLS,
        ],
        probe=p,
    )
    assert code == 1
    assert "unresolved: ghost" in capsys.readouterr().out


def test_rewrite_config_without_mcp_servers_is_a_noop():
    p = FakeProbe(files={f"{HOME}/.claude.json": json.dumps({"other": 1})})
    result = doc.rewrite_mcp(
        p,
        f"{HOME}/.claude.json",
        npx_cache=NPX_CACHE,
        npm_prefix=NPM_PREFIX,
        uv_tools=UV_TOOLS,
        node="node",
    )
    assert result["changed"] == [] and result["rewritten"] == {"other": 1}


def test_default_paths_are_derived_from_home_and_appdata(monkeypatch):
    monkeypatch.setenv("APPDATA", "C:/Users/x/AppData/Roaming")
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/x/AppData/Local")
    defaults = doc.default_paths("C:/Users/x")
    assert defaults["npx_cache"].endswith("npm-cache/_npx")
    assert defaults["npm_prefix"].endswith("Roaming/npm")
    assert defaults["uv_tools"].endswith("uv/tools")
    monkeypatch.delenv("APPDATA")
    monkeypatch.delenv("LOCALAPPDATA")
    defaults = doc.default_paths("C:/Users/x")
    assert defaults["npm_prefix"] == "C:/Users/x/AppData/Roaming/npm"


def test_wslconfig_line_without_equals_and_comments_are_ignored():
    text = "# a comment\n[wsl2]\nmemory=8GB\njunk line\n[experimental]\nautoMemoryReclaim=dropCache # trailing\n"
    finding = by_id(run_doctor(probe(files={f"{HOME}/.wslconfig": text})), "wslconfig")[
        0
    ]
    assert finding.severity == "ok"


def test_split_npx_handles_value_flags_versions_and_flag_only_args():
    assert doc._split_npx(["-y", "-p", "@x/tool", "@x/tool@1.2.3", "--port", "1"]) == (
        "@x/tool",
        ["--port", "1"],
    )
    assert doc._split_npx(["server-git@latest"]) == ("server-git", [])
    assert doc._split_npx(["@scope/name"]) == ("@scope/name", [])
    assert doc._split_npx(["-y", "--quiet"]) == (None, [])


def test_rewrite_flags_only_npx_and_package_without_bin_or_main_are_unresolved():
    config = {
        "mcpServers": {
            "empty": {"command": "npx", "args": ["-y"]},
            "bare": {"command": "npx", "args": ["@x/bare"]},
        }
    }
    files = {
        f"{HOME}/.claude.json": json.dumps(config),
        f"{NPM_PREFIX}/node_modules/@x/bare/package.json": json.dumps(
            {"name": "@x/bare"}
        ),
    }
    result = doc.rewrite_mcp(
        FakeProbe(files=files),
        f"{HOME}/.claude.json",
        npx_cache=NPX_CACHE,
        npm_prefix=NPM_PREFIX,
        uv_tools=UV_TOOLS,
        node="node",
    )
    hints = {u["server"]: u["hint"] for u in result["unresolved"]}
    assert set(hints) == {"empty", "bare"}
    assert "neither bin nor main" in hints["bare"]


def test_digest_marker_that_is_corrupt_is_ignored_and_rewritten():
    p = probe(
        files={
            f"{ROOT}/state/heartbeat.json": heartbeat(NOW - 3 * 3600),
            f"{ROOT}/state/doctor-digest.json": "{corrupt",
        }
    )
    digest = f"{ROOT}/DIGEST.md"
    doc.main(["--root", ROOT, "--home", HOME, "--digest", digest], probe=p)
    assert p.files[digest].count("\n") == 1
    assert (
        json.loads(p.files[f"{ROOT}/state/doctor-digest.json"])["signature"]
        == "heartbeat"
    )


def test_rewrite_cli_apply_with_nothing_to_change_still_writes_the_sidecar(capsys):
    p = FakeProbe(
        files={
            f"{HOME}/.claude.json": json.dumps(
                {"mcpServers": {"d": {"command": "node", "args": ["x.js"]}}}
            )
        }
    )
    code = doc.main(
        [
            "rewrite-mcp",
            "--config",
            f"{HOME}/.claude.json",
            "--apply",
            "--npx-cache",
            NPX_CACHE,
            "--npm-prefix",
            NPM_PREFIX,
            "--uv-tools",
            UV_TOOLS,
        ],
        probe=p,
    )
    assert code == 0
    assert "(no changes)" in capsys.readouterr().out
    assert f"{HOME}/.claude.json.rewritten.json" in p.written


# ------------------------------------------------------------ browser-policy


def test_browser_policy_generates_reg_rollback_and_verify_files():
    p = FakeProbe()
    written = doc.browser_policy(
        p,
        "C:/out",
        chrome_limit_mb=4096,
        edge_limit_mb=3072,
        sleeping_tabs_seconds=300,
        hive="HKLM",
    )
    assert set(written) == {
        "C:/out/browser-discard-policies.reg",
        "C:/out/browser-discard-policies.ROLLBACK.reg",
        "C:/out/verify-browser-policies.ps1",
    }
    reg = p.files["C:/out/browser-discard-policies.reg"]
    assert reg.startswith("Windows Registry Editor Version 5.00\r\n")
    assert "[HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Google\\Chrome]" in reg
    assert '"TotalMemoryLimitMb"=dword:00001000' in reg  # 4096
    assert '"HighEfficiencyModeEnabled"=dword:00000001' in reg
    assert '"MemorySaverModeSavings"=dword:00000002' in reg
    assert '"BackgroundModeEnabled"=dword:00000000' in reg
    assert "[HKEY_LOCAL_MACHINE\\SOFTWARE\\Policies\\Microsoft\\Edge]" in reg
    assert '"TotalMemoryLimitMb"=dword:00000c00' in reg  # 3072
    assert '"SleepingTabsEnabled"=dword:00000001' in reg
    assert '"SleepingTabsTimeout"=dword:0000012c' in reg  # 300
    assert '"StartupBoostEnabled"=dword:00000000' in reg
    # Edge's energy-saver knobs are deliberately absent: CPU levers, not memory.
    # (Chrome's Memory Saver policy is confusingly NAMED HighEfficiencyModeEnabled and
    # IS a memory lever, hence the quoted-name checks rather than a substring.)
    assert '"EfficiencyMode"' not in reg and '"EfficiencyModeEnabled"' not in reg
    rollback = p.files["C:/out/browser-discard-policies.ROLLBACK.reg"]
    assert (
        '"TotalMemoryLimitMb"=-' in rollback and '"SleepingTabsTimeout"=-' in rollback
    )
    verify = p.files["C:/out/verify-browser-policies.ps1"]
    assert "chrome://policy" in verify and "edge://policy" in verify
    assert "unmanaged" in verify.lower() or "enrolled" in verify.lower()
    assert "Get-ItemProperty" in verify


def test_browser_policy_clamps_limits_and_supports_hkcu():
    p = FakeProbe()
    doc.browser_policy(
        p,
        "C:/out",
        chrome_limit_mb=512,
        edge_limit_mb=100,
        sleeping_tabs_seconds=10,
        hive="HKCU",
    )
    reg = p.files["C:/out/browser-discard-policies.reg"]
    assert "[HKEY_CURRENT_USER\\SOFTWARE\\Policies\\Google\\Chrome]" in reg
    assert (
        reg.count('"TotalMemoryLimitMb"=dword:00000400') == 2
    )  # both clamped to the 1024 minimum
    assert '"SleepingTabsTimeout"=dword:0000012c' in reg  # 300 s floor


def test_browser_policy_cli(capsys):
    p = FakeProbe()
    code = doc.main(["browser-policy", "--emit", "C:/out", "--hive", "HKCU"], probe=p)
    assert code == 0
    out = capsys.readouterr().out
    assert (
        "browser-discard-policies.reg" in out and "verify-browser-policies.ps1" in out
    )
    assert "never kills" in out.lower() or "discard" in out.lower()
    code = doc.main(["browser-policy", "--emit", "C:/out", "--hive", "HKXX"], probe=p)
    assert code == 2


def test_quick_mode_runs_only_the_heartbeat_check_and_spawns_nothing(capsys):
    p = probe(files={f"{ROOT}/state/heartbeat.json": heartbeat(NOW - 3 * 3600)})
    code = doc.main(["--root", ROOT, "--home", HOME, "--quick", "--json"], probe=p)
    out = json.loads(capsys.readouterr().out)
    assert code == 1
    assert [f["id"] for f in out["findings"]] == ["heartbeat"]
    assert p.calls == []  # no `claude --version` etc. every five minutes
