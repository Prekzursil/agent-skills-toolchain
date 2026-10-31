#!/usr/bin/env python
"""mcp-manager — cross-plane MCP + skill manager (CLI surface).

Read-only inventory + analysis, plus Claude-plane preset bulk-apply. Every
config write targets ONLY the current project's disabledMcpServers via the safe
mtime-merge path and takes effect the NEXT session (restart to apply).

Usage:
  uv run app.py status                 # unified MCP inventory across planes
  uv run app.py duplicates             # cross-plane duplicate servers
  uv run app.py consolidate            # user-skill consolidation analysis
  uv run app.py json                   # full machine-readable inventory

  uv run app.py preset list            # list named presets (+ members)
  uv run app.py use <preset...>        # bulk-apply preset(s) to THIS project
  uv run app.py preset apply <name...> # alias of 'use'
  uv run app.py preset save <name> <server...>   # save/replace a preset
  uv run app.py preset delete <name>   # remove a preset

  uv run app.py parse-list [file]      # parse a pasted /mcp panel dump (stdin ok)
  uv run app.py try-live <preset...> --window "<title>"   # EXPERIMENTAL macro

Flags for 'use' / 'try-live':
  --from-paste <file>   use a pasted /mcp dump as the live inventory
  --project <path>      target a specific project path (default: cwd)
  --dry-run             resolve + print the plan without writing
  --window "<title>"    (try-live) target terminal window title
  --apply               (try-live) actually send keystrokes (default: dry-run)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import claude_adapter  # noqa: E402
from core import consolidation  # noqa: E402
from core import live_macro  # noqa: E402
from core import paste_parse  # noqa: E402
from core import presets as presets_mod  # noqa: E402
from core.inventory import build_inventory  # noqa: E402

HOME = Path.home()
CLAUDE_JSON = HOME / ".claude.json"
SKILL_ROOTS = [HOME / ".claude" / "skills", HOME / ".agents" / "skills"]

_NEXT_SESSION = "Applies NEXT session — restart Claude Code to take effect."


def current_project_path() -> str:
    """The current working directory, normalised to the ~/.claude.json key form.

    The enforce hook keys off ``os.getcwd()`` — targeting the launch cwd (not
    ``Path.home()``) is what makes 'this project' edits land on the right key.
    """
    return str(Path.cwd()).replace("\\", "/")


# ── read-only inventory commands ──────────────────────────────────────────────


def cmd_status() -> None:
    rep = build_inventory(HOME, project_path=current_project_path())
    print(
        f"MCP servers across planes: {rep['server_count']}  "
        + f"(cross-plane duplicates: {len(rep['duplicated_servers'])})\n"
    )
    print(f"{'SERVER':28} {'PLANES':40} STATE")
    print("-" * 90)
    for s in rep["servers"]:
        state = (
            "enabled:" + ",".join(sorted(set(s["enabled_in"])))
            if s["enabled_in"]
            else ""
        )
        if s["disabled_in"]:
            state += "  disabled:" + ",".join(sorted(set(s["disabled_in"])))
        dup = " *DUP*" if s["duplicated"] else ""
        print(
            f"{s['name'][:27]:28} {','.join(sorted(set(s['planes'])))[:39]:40} {state}{dup}"
        )


def cmd_duplicates() -> None:
    rep = build_inventory(HOME, project_path=current_project_path())
    print("Cross-plane duplicate servers (defined in >1 plane):")
    for n in rep["duplicated_servers"]:
        print(f"  {n}")
    print(f"\nTotal: {len(rep['duplicated_servers'])} of {rep['server_count']}")


def cmd_consolidate() -> None:
    analysis = consolidation.analyze_skills(SKILL_ROOTS)
    print(consolidation.render_report(analysis))


def cmd_json() -> None:
    json.dump(
        build_inventory(HOME, project_path=current_project_path()), sys.stdout, indent=2
    )


# ── argument helpers ──────────────────────────────────────────────────────────


def _split_flags(args: list[str]) -> tuple[list[str], dict[str, str], set[str]]:
    """Split argv into (positionals, valued-flags, bare-flags).

    Recognises ``--from-paste``, ``--project``, ``--window`` (valued) and
    ``--dry-run``, ``--apply`` (bare).
    """
    valued_names = {"--from-paste", "--project", "--window"}
    positionals: list[str] = []
    valued: dict[str, str] = {}
    bare: set[str] = set()
    i = 0
    while i < len(args):
        a = args[i]
        if a in valued_names:
            if i + 1 < len(args):
                valued[a.lstrip("-")] = args[i + 1]
                i += 2
                continue
            i += 1
            continue
        if a.startswith("--"):
            bare.add(a.lstrip("-"))
            i += 1
            continue
        positionals.append(a)
        i += 1
    return positionals, valued, bare


def _read_paste(path_arg: str | None) -> str:
    if path_arg:
        return Path(path_arg).read_text(encoding="utf-8")
    return sys.stdin.read()


def get_live_inventory_ids(project_path: str) -> list[str]:
    """Live Claude-plane server ids via 'claude mcp list' (monkeypatchable)."""
    rows = claude_adapter.get_server_universe(CLAUDE_JSON, project_path)
    return [r.id for r in rows]


def _resolve_inventory(
    from_paste: str | None, project_path: str
) -> tuple[list[str], str] | None:
    """Return (inventory_ids, source_label) or None on a hard failure."""
    if from_paste is not None:
        try:
            text = _read_paste(from_paste or None)
        except OSError as exc:
            print(f"Could not read paste file: {exc}")
            return None
        servers = paste_parse.parse_mcp_panel(text)
        if not servers:
            print("No servers parsed from the pasted panel.")
            return None
        return paste_parse.inventory_ids(servers), f"paste ({len(servers)} servers)"
    try:
        ids = get_live_inventory_ids(project_path)
    except Exception as exc:  # noqa: BLE001 - CLI subprocess may fail
        print(f"Could not query live inventory ('claude mcp list'): {exc}")
        print("Tip: paste a /mcp dump and pass --from-paste <file>.")
        return None
    if not ids:
        print("Live inventory is empty. Try --from-paste <file>.")
        return None
    return ids, f"live ({len(ids)} servers)"


# ── preset / apply commands ───────────────────────────────────────────────────


def cmd_preset(args: list[str]) -> int:
    sub = args[0] if args else "list"
    rest = args[1:]
    if sub == "list":
        return _preset_list()
    if sub in ("apply", "use"):
        return cmd_use(rest)
    if sub == "save":
        return _preset_save(rest)
    if sub == "delete":
        return _preset_delete(rest)
    print(f"Unknown preset subcommand: {sub!r} (list|apply|save|delete)")
    return 2


def _preset_list() -> int:
    catalog = presets_mod.ensure_catalog_file()
    print(f"core ({len(catalog.core)} servers): " + ", ".join(catalog.core))
    print()
    print("Presets (each ENABLEs these servers; compose by listing several):")
    for name in catalog.names():
        members = catalog.presets[name]
        print(f"  {name:10} ({len(members)}): " + ", ".join(members))
    return 0


def _preset_save(rest: list[str]) -> int:
    if len(rest) < 2:
        print("Usage: preset save <name> <server> [server...]")
        return 2
    name, members = rest[0], rest[1:]
    changed = presets_mod.save_preset(name, members)
    print(
        f"Preset {name!r} {'saved' if changed else 'unchanged'} "
        + f"({len(members)} servers)."
    )
    return 0


def _preset_delete(rest: list[str]) -> int:
    if not rest:
        print("Usage: preset delete <name>")
        return 2
    removed = presets_mod.delete_preset(rest[0])
    print(f"Preset {rest[0]!r} {'deleted' if removed else 'not found'}.")
    return 0


def cmd_use(args: list[str]) -> int:
    selected, valued, bare = _split_flags(args)
    if not selected:
        print(
            "Usage: use <preset...> [--from-paste <file>] [--project <path>] [--dry-run]"
        )
        return 2
    project_path = valued.get("project") or current_project_path()
    inv = _resolve_inventory(valued.get("from-paste"), project_path)
    if inv is None:
        return 1
    inventory_ids, source = inv
    catalog = presets_mod.ensure_catalog_file()
    resolved = presets_mod.resolve_disabled(catalog, selected, inventory_ids)

    if resolved.unknown_presets:
        print("Unknown preset(s): " + ", ".join(resolved.unknown_presets))
        print("Known presets: " + ", ".join(catalog.names()))
        return 2

    print(f"Selection: {', '.join(selected)}   |   inventory: {source}")
    print(f"Project:   {project_path}")
    print(
        f"Would ENABLE {len(resolved.to_enable)}  |  "
        + f"DISABLE {len(resolved.to_disable)}"
    )
    if resolved.unmatched_members:
        print(
            "Note: enable members with no live match: "
            + ", ".join(resolved.unmatched_members)
        )

    if "dry-run" in bare:
        print("\n[dry-run] no changes written.")
        return 0

    result = presets_mod.apply_selection(
        selected, inventory_ids, CLAUDE_JSON, project_path, catalog=catalog
    )
    print(
        f"\nWrote: {len(result.newly_disabled)} newly disabled, "
        + f"{len(result.newly_enabled)} newly enabled."
    )
    print(_NEXT_SESSION)
    return 0


def cmd_parse_list(args: list[str]) -> int:
    positionals, _valued, bare = _split_flags(args)
    path_arg = positionals[0] if positionals else None
    try:
        text = _read_paste(path_arg)
    except OSError as exc:
        print(f"Could not read file: {exc}")
        return 1
    servers = paste_parse.parse_mcp_panel(text)
    if "json" in bare:
        json.dump(
            [
                {"name": s.name, "state": s.state, "tools": s.tool_count}
                for s in servers
            ],
            sys.stdout,
            indent=2,
        )
        return 0
    print(f"Parsed {len(servers)} server(s):\n")
    print(f"{'SERVER':30} {'STATE':12} TOOLS")
    print("-" * 55)
    for s in servers:
        tools = "" if s.tool_count is None else str(s.tool_count)
        print(f"{s.name[:29]:30} {s.state:12} {tools}")
    return 0


def cmd_try_live(args: list[str]) -> int:
    selected, valued, bare = _split_flags(args)
    print("=" * 68)
    print("EXPERIMENTAL /mcp keystroke macro — FRAGILE, may fail.")
    print("Blind arrow-navigation of the /mcp TUI. No reliable success signal.")
    print("=" * 68)
    if not selected:
        print(
            'Usage: try-live <preset...> --from-paste <file> --window "<title>" [--apply]'
        )
        return 2
    from_paste = valued.get("from-paste")
    if from_paste is None:
        print("try-live REQUIRES --from-paste <file> (the panel order to navigate).")
        return 2
    try:
        text = _read_paste(from_paste or None)
    except OSError as exc:
        print(f"Could not read paste file: {exc}")
        return 1
    servers = paste_parse.parse_mcp_panel(text)
    if not servers:
        print("No servers parsed — cannot plan navigation.")
        return 1

    project_path = valued.get("project") or current_project_path()
    catalog = presets_mod.ensure_catalog_file()
    inventory = paste_parse.inventory_ids(servers)
    resolved = presets_mod.resolve_disabled(catalog, selected, inventory)
    if resolved.unknown_presets:
        print("Unknown preset(s): " + ", ".join(resolved.unknown_presets))
        return 2
    desired_enabled = set(resolved.to_enable)
    plan = live_macro.plan_navigation(servers, desired_enabled)

    print(f"\nPlan ({len(plan)} steps) for project {project_path}:")
    print(live_macro.render_plan(plan))

    window = valued.get("window", "")
    dry = "apply" not in bare
    ok, msg = live_macro.run_macro(
        plan,
        window,
        focuser=live_macro.default_focuser,
        sender=_sender_for(dry),
        dry_run=dry,
    )
    print(f"\n{'OK' if ok else 'FAILED'}: {msg}")
    print("Reminder: even a 'sent' macro is not verified — check /mcp manually.")
    return 0 if ok else 1


def _noop_sender(step: live_macro.NavStep) -> None:
    """A do-nothing sender used for dry-runs (no OS driver import)."""
    return None


def _sender_for(dry: bool) -> live_macro.Sender:
    if dry:
        return _noop_sender
    return live_macro.make_pyautogui_sender()  # pragma: no cover - real OS driving


# ── dispatch ──────────────────────────────────────────────────────────────────


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    rest = argv[2:]
    simple = {
        "status": cmd_status,
        "duplicates": cmd_duplicates,
        "consolidate": cmd_consolidate,
        "json": cmd_json,
    }
    parametrized = {
        "use": cmd_use,
        "preset": cmd_preset,
        "parse-list": cmd_parse_list,
        "try-live": cmd_try_live,
    }
    if cmd in simple:
        simple[cmd]()
        return 0
    if cmd in parametrized:
        return parametrized[cmd](rest)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
