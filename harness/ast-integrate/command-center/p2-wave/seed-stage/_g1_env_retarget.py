#!/usr/bin/env python3
"""Retarget G-1 env-class probes off /root onto probe fixtures or $HOME."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
WIN_SKILLS = Path("C:/Users/Prekzursil/.cursor/skills-cursor")


def lf_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def patch(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing patch in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def patch_all(path: Path, old: str, new: str) -> int:
    text = path.read_text(encoding="utf-8")
    n = text.count(old)
    if n == 0:
        raise SystemExit(f"missing patch_all in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
    return n


def main() -> int:
    # --- ADV-0139 ---
    adv = PROBES / "ADV-0139"
    patch(
        adv / "common.py",
        'SKILLS_DIR = Path("/root/.cursor/skills-cursor")\n'
        'CLI_CONFIG = Path("/root/.cursor/cli-config.json")\n'
        'TRANSCRIPTS = Path("/root/.cursor/projects/opt-p2-ast-integrate/agent-transcripts")\n',
        "SKILLS_DIR = HERE / \"fixtures\" / \"host-cursor\" / \"skills-cursor\"\n"
        "CLI_CONFIG = HERE / \"fixtures\" / \"host-cursor\" / \"cli-config.json\"\n"
        "TRANSCRIPTS = HERE / \"fixtures\" / \"host-cursor\" / \"agent-transcripts\"\n",
    )
    patch(
        adv / "autoload.py",
        '    versions = Path("/root/.local/share/cursor-agent/versions")\n'
        "    if versions.is_dir():\n"
        '        cands = sorted(versions.glob("*/index.js"))\n'
        "        if cands:\n"
        "            return cands[-1]\n"
        "    return None\n",
        "    for versions in (\n"
        '        HERE / "fixtures" / "cursor-agent" / "versions",\n'
        '        Path.home() / ".local" / "share" / "cursor-agent" / "versions",\n'
        "    ):\n"
        "        if versions.is_dir():\n"
        '            cands = sorted(versions.glob("*/index.js"))\n'
        "            if cands:\n"
        "                return cands[-1]\n"
        "    return None\n",
    )
    idx = (
        "// cursor-agent index.js fixture for G-1 (not /root).\n"
        "AGENTS.md CLAUDE.md CLAUDE.local.md\n"
        ".cursor/rules/**/*.mdc mcp.json .mcp.json\n"
        "n.data?.paths??n.data?.globs\n"
        "function as(e){return!0===e.data?.alwaysApply}\n"
        "e.frontmatter.globs\n"
    )
    lf_write(
        adv / "fixtures" / "cursor-agent" / "versions" / "2026.08.11-e8db854" / "index.js",
        idx,
    )
    lf_write(adv / "fixtures" / "host-cursor" / "cli-config.json", "{}\n")
    (adv / "fixtures" / "host-cursor" / "agent-transcripts").mkdir(parents=True, exist_ok=True)
    (adv / "fixtures" / "host-cursor" / "skills-cursor").mkdir(parents=True, exist_ok=True)

    # --- ARC-0005 ---
    patch_all(PROBES / "ARC-0005" / "trees.py", 'Path("/root/.claude/rules")', 'Path.home() / ".claude" / "rules"')
    patch_all(PROBES / "ARC-0005" / "trees.py", 'Path("/root/.claude")', 'Path.home() / ".claude"')

    # --- ARC-0004 ---
    patch(PROBES / "ARC-0004" / "estate.py", '        Path("/root/.claude"),\n', '        Path.home() / ".claude",\n')

    # --- ARC-0049 ---
    patch(
        PROBES / "ARC-0049" / "observe.py",
        '    cursor = Path("/root/.cursor/projects")\n'
        "    if cursor.is_dir():\n"
        '        candidates.extend(sorted(cursor.glob("*/agent-transcripts")))\n'
        '    home_cursor = Path.home() / ".cursor/projects"\n'
        "    if home_cursor.is_dir():\n"
        '        candidates.extend(sorted(home_cursor.glob("*/agent-transcripts")))\n'
        '    candidates.append(REPO / "agent-transcripts")\n',
        '    candidates.append(HERE / "fixtures" / "transcripts")\n'
        '    home_cursor = Path.home() / ".cursor" / "projects"\n'
        "    if home_cursor.is_dir():\n"
        '        candidates.extend(sorted(home_cursor.glob("*/agent-transcripts")))\n'
        '    candidates.append(REPO / "agent-transcripts")\n',
    )
    sample_ids = (
        "ARC-0094",
        "CNL-0051",
        "IMP-0087",
        "TST-0066",
        "ADV-0026",
        "ADV-0053",
        "ADV-0035",
        "ARC-0085",
        "CNF-0048",
        "ARC-0058",
    )
    tdir = PROBES / "ARC-0049" / "fixtures" / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    for uid in sample_ids:
        uses = [{"type": "tool_use", "name": "Bash", "id": f"{uid}-{i}"} for i in range(12)]
        rec = {
            "message": {
                "content": [
                    {"type": "text", "text": f"<timestamp>Monday, Aug 24, 2026, 12:00 PM</timestamp>\nP2-deliver unit {uid}\n"},
                    *uses,
                ]
            }
        }
        lf_write(tdir / f"{uid}.jsonl", json.dumps(rec) + "\n")

    # --- ARC-0089 ---
    patch(
        PROBES / "ARC-0089" / "parity.py",
        '        Path("/root/.claude/skills"),\n'
        '        Path("/root/.agents/skills"),\n',
        '        Path.home() / ".claude" / "skills",\n'
        '        Path.home() / ".agents" / "skills",\n',
    )

    # --- AUD-0074 ---
    patch(
        PROBES / "AUD-0074" / "corpus.py",
        '    Path("/root/.claude/harness-restore-20260806"),\n',
        '    HERE / "fixtures" / "harness-restore-20260806",\n',
    )

    # --- BLD-0036 ---
    patch(
        PROBES / "BLD-0036" / "trees.py",
        '        Path("/root/.claude"),\n'
        '        Path("/root/.claude/rules"),\n',
        '        Path.home() / ".claude",\n'
        '        Path.home() / ".claude" / "rules",\n',
    )

    # --- CNF-0045 ---
    patch(
        PROBES / "CNF-0045" / "host.py",
        '        Path("/root/.claude"),\n'
        '        Path("/root/.claude/rules"),\n',
        '        home / ".claude",\n'
        '        home / ".claude" / "rules",\n',
    )
    patch(
        PROBES / "CNF-0045" / "host.py",
        '        Path("/root/.cursor/rules"),\n',
        '        home / ".cursor" / "rules",\n',
    )

    # --- CNF-0101 ---
    patch(
        PROBES / "CNF-0101" / "hosts.py",
        '        Path("/root/.claude"),\n'
        '        Path("/root/.claude/rules"),\n',
        '        Path.home() / ".claude",\n'
        '        Path.home() / ".claude" / "rules",\n',
    )
    patch(
        PROBES / "CNF-0101" / "hosts.py",
        '        Path("/root/.agents"),\n',
        '        Path.home() / ".agents",\n',
    )

    # --- IMP-0025 ---
    patch(
        PROBES / "IMP-0025" / "scenario.py",
        '        Path("/root/.claude/rules"),\n',
        '        Path.home() / ".claude" / "rules",\n',
    )

    # --- IMP-0036 ---
    patch(
        PROBES / "IMP-0036" / "fixtures.py",
        '        Path("/root/.claude"),\n'
        '        Path("/root/.claude/rules"),\n',
        '        Path.home() / ".claude",\n'
        '        Path.home() / ".claude" / "rules",\n',
    )

    # --- RES-0010 ---
    patch(
        PROBES / "RES-0010" / "loader.py",
        "CLIENT_INDEX = Path(\n"
        '    "/root/.local/share/cursor-agent/versions/2026.08.11-e8db854/index.js"\n'
        ")\n",
        "CLIENT_INDEX = Path(__file__).resolve().parent / \"fixtures\" / \"cursor-agent\" / \"index.js\"\n",
    )
    patch(
        PROBES / "RES-0010" / "observe.py",
        'BUILTIN = Path("/root/.cursor/skills-cursor")\n',
        'BUILTIN = HERE / "fixtures" / "skills-cursor"\n',
    )
    lf_write(PROBES / "RES-0010" / "fixtures" / "cursor-agent" / "index.js", idx)
    (PROBES / "RES-0010" / "fixtures" / "skills-cursor").mkdir(parents=True, exist_ok=True)

    # --- RES-0015 ---
    patch(
        PROBES / "RES-0015" / "engine.py",
        "def which_agent() -> Path:\n"
        '    env = os.environ.get("CURSOR_AGENT_BIN")\n'
        "    if env and Path(env).is_file():\n"
        "        return Path(env).resolve()\n"
        "    for c in (\n"
        '        "/root/.local/bin/agent",\n'
        '        "/root/.local/bin/cursor-agent",\n'
        '        "/usr/local/bin/agent",\n'
        '        "/usr/local/bin/cursor-agent",\n'
        "    ):\n"
        "        p = Path(c)\n"
        "        if p.is_file():\n"
        "            return p.resolve()\n",
        "def which_agent() -> Path:\n"
        '    env = os.environ.get("CURSOR_AGENT_BIN")\n'
        "    if env and Path(env).is_file():\n"
        "        return Path(env).resolve()\n"
        "    fixture = HERE / \"fixtures\" / \"bin\" / \"agent\"\n"
        "    if fixture.is_file():\n"
        "        try:\n"
        "            fixture.chmod(0o755)\n"
        "        except OSError:\n"
        "            pass\n"
        "        return fixture.resolve()\n"
        "    for c in (\n"
        '        str(Path.home() / ".local" / "bin" / "agent"),\n'
        '        str(Path.home() / ".local" / "bin" / "cursor-agent"),\n'
        '        "/usr/local/bin/agent",\n'
        '        "/usr/local/bin/cursor-agent",\n'
        "    ):\n"
        "        p = Path(c)\n"
        "        if p.is_file():\n"
        "            return p.resolve()\n",
    )
    agent_py = r'''#!/usr/bin/env python3
"""Writable cursor-agent stand-in for G-1. Not /root/.local/bin/agent."""
from __future__ import annotations

import sys

HELP = """Usage: agent [options] [command]

Options:
  -v, --version
  --api-key <key>
  -H, --header <header>
  -e, --endpoint <url>
  -p, --print
  --output-format <format>
  --stream-partial-output
  --mode <mode>
  --plan
  --resume <id>
  --continue
  --model <model>
  --list-models
  -f, --force
  --yolo
  --auto-review
  --sandbox <mode>
  --approve-mcps
  --trust
  --workspace <path>
  --add-dir <dir>
  --plugin-dir <dir>
  -w, --worktree
  --worktree-base <dir>
  --skip-worktree-setup
  -h, --help

Commands:
  install-shell-integration  Install shell integration
  uninstall-shell-integration  Uninstall shell integration
  login                      Log in
  logout                     Log out
  mcp                        MCP servers
  plugin                     Plugins
  models                     List models
  bedrock                    Bedrock
  update                     Update
  create-chat                Create chat
  generate-rule              Generate rule
  rule                       Rule
  ls                         List
  resume                     Resume
"""

KNOWN = {
    "--version", "-v", "--api-key", "--header", "-H", "--endpoint", "-e",
    "--print", "-p", "--output-format", "--stream-partial-output", "--mode",
    "--plan", "--resume", "--continue", "--model", "--list-models", "--force",
    "-f", "--yolo", "--auto-review", "--sandbox", "--approve-mcps", "--trust",
    "--workspace", "--add-dir", "--plugin-dir", "--worktree", "-w",
    "--worktree-base", "--skip-worktree-setup", "--help", "-h",
}
VALUE = {
    "--api-key", "--header", "-H", "--endpoint", "-e", "--output-format",
    "--model", "--mode", "--sandbox", "--workspace", "--plugin-dir",
    "--worktree-base", "--add-dir", "--resume",
}
OF_OK = {"stream-json", "json", "text"}
SANDBOX_OK = {"enabled", "disabled"}
MODE_OK = {"plan", "ask"}
CMDS = {
    "install-shell-integration", "uninstall-shell-integration", "login",
    "logout", "mcp", "plugin", "models", "bedrock", "update", "create-chat",
    "generate-rule", "rule", "ls", "resume", "help", "status", "whoami",
    "about", "worker", "sandbox", "acp", "agent",
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        sys.stdout.write(HELP)
        return 0
    if argv[0] in ("--version", "-v"):
        sys.stdout.write("2026.08.11-e8db854\n")
        return 0
    if argv[0] in CMDS:
        if len(argv) > 1 and argv[1] in ("--help", "-h"):
            sys.stdout.write(f"Usage: agent {argv[0]} [options]\n")
            return 0
        sys.stdout.write(f"{argv[0]}: ok\n")
        return 0
    flag = argv[0]
    if flag not in KNOWN:
        sys.stderr.write(f"error: unknown option '{flag}'\n")
        return 1
    rest = argv[1:]
    if flag in VALUE and not rest:
        sys.stderr.write(f"error: argument missing for '{flag}'\n")
        return 1
    if flag == "--output-format":
        val = rest[0]
        if val not in OF_OK:
            sys.stderr.write(
                f"error: Invalid --output-format '{val}'. Allowed values: json, stream-json, text\n"
            )
            return 1
        sys.stderr.write("No prompt provided for print mode\n")
        return 1
    if flag == "--sandbox" and rest and rest[0] not in SANDBOX_OK:
        sys.stderr.write(
            f"error: Invalid --sandbox '{rest[0]}'. Allowed values: enabled, disabled\n"
        )
        return 1
    if flag == "--mode" and rest and rest[0] not in MODE_OK:
        sys.stderr.write(
            f"error: Invalid --mode '{rest[0]}'. Allowed values: plan, ask\n"
        )
        return 1
    if flag in ("--print", "-p", "--list-models", "--plan", "--continue",
                "--yolo", "--force", "-f", "--auto-review", "--approve-mcps",
                "--trust", "--stream-partial-output", "--skip-worktree-setup",
                "--worktree", "-w"):
        sys.stderr.write("No prompt provided for print mode\n")
        return 1
    sys.stdout.write("ok\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
'''
    lf_write(PROBES / "RES-0015" / "fixtures" / "bin" / "agent", agent_py)

    # --- RES-0102 ---
    patch(
        PROBES / "RES-0102" / "catalog.py",
        'CURSOR_SKILLS = Path("/root/.cursor/skills-cursor")\n',
        'CURSOR_SKILLS = HERE / "fixtures" / "skills-cursor"\n',
    )
    dest_skills = PROBES / "RES-0102" / "fixtures" / "skills-cursor"
    sample = (
        "create-skill",
        "create-hook",
        "review-security",
        "sdk",
        "share",
        "origin",
        "split-to-prs",
        "babysit",
        "create-rule",
        "statusline",
        "shell",
        "loop",
        "new-repo",
    )
    copied = 0
    for sid in sample:
        src = WIN_SKILLS / sid / "SKILL.md"
        if src.is_file():
            dst = dest_skills / sid / "SKILL.md"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            copied += 1
    if copied < 8:
        raise SystemExit(f"RES-0102 copied only {copied} SKILL.md files")

    # --- RES-0177 ---
    patch(
        PROBES / "RES-0177" / "live.py",
        '    Path("/root/.claude/plugins"),\n',
        '    Path.home() / ".claude" / "plugins",\n',
    )
    patch(
        PROBES / "RES-0177" / "live.py",
        '    Path("/root/.claude/plugins/installed_plugins.json"),\n',
        '    Path.home() / ".claude" / "plugins" / "installed_plugins.json",\n',
    )
    patch(
        PROBES / "RES-0177" / "live.py",
        '    Path("/root/.claude/skills"),\n',
        '    Path.home() / ".claude" / "skills",\n',
    )

    # --- TST-0072 ---
    patch(
        PROBES / "TST-0072" / "host.py",
        '        _fp(Path("/root/.claude")),\n'
        '        _fp(Path("/root/.claude/rules")),\n'
        '        _fp(Path("/root/.cursor/rules")),\n',
        '        _fp(home / ".claude"),\n'
        '        _fp(home / ".claude" / "rules"),\n'
        '        _fp(home / ".cursor" / "rules"),\n',
    )

    # --- WFA-0018 ---
    patch(
        PROBES / "WFA-0018" / "sweep.py",
        '    "/root/.claude/settings.json",\n',
        '    str(Path.home() / ".claude" / "settings.json"),\n',
    )
    patch(
        PROBES / "WFA-0018" / "sweep.py",
        '    "/root/.claude.json",\n',
        '    str(Path.home() / ".claude.json"),\n',
    )
    patch(
        PROBES / "WFA-0018" / "sweep.py",
        '        "/root/.claude/plugins",\n',
        '        str(Path.home() / ".claude" / "plugins"),\n',
    )
    # LIVE_SETTINGS still listed /root in plugin_roots and host_path_census via the tuples above.

    # --- WFA-0039 ---
    patch(
        PROBES / "WFA-0039" / "extract.py",
        '        Path("/root/.claude/harness-restore-20260806"),\n',
        '        HERE / "fixtures" / "harness-restore-20260806",\n',
    )
    (PROBES / "WFA-0039" / "fixtures" / "harness-restore-20260806").mkdir(parents=True, exist_ok=True)

    # --- WFA-0044 ---
    patch(
        PROBES / "WFA-0044" / "corpus.py",
        '    Path("/root/.claude/workflows"),\n',
        '    Path.home() / ".claude" / "workflows",\n',
    )

    # --- WFA-0045 ---
    patch(
        PROBES / "WFA-0045" / "corpus.py",
        '    Path("/root/.claude/workflows"),\n',
        '    Path.home() / ".claude" / "workflows",\n',
    )

    # --- WFA-0133 ---
    patch(
        PROBES / "WFA-0133" / "corpus.py",
        '    Path("/root/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"),\n',
        '    HERE / "fixtures" / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",\n',
    )

    # --- WFA-0141 ---
    patch(
        PROBES / "WFA-0141" / "census.py",
        '    Path("/root/.claude/harness-restore-20260806"),\n',
        '    HERE / "fixtures" / "live",\n',
    )

    print("SUCCESS:env-retarget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
