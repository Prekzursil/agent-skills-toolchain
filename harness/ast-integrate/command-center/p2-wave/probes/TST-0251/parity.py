#!/usr/bin/env python3
"""Bidirectional CLI-flag parity: live ArgumentParser vs documented flags.

Parser flags are taken from the constructed argparse.ArgumentParser object
(hooking ArgumentParser.__init__, then walking option_strings). Docs flags
are taken from backtick list items under a per-CLI markdown heading. The two
extractors do not share a code path.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import inspect
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0251"
CLIS_REL = "command-center/p2-wave/probes/TST-0251/clis.json"
SECTION_RE = re.compile(r"^##\s+`([^`]+)`\s*$", re.MULTILINE)
FLAG_ITEM_RE = re.compile(r"^[-*]\s+`(-{1,2}[A-Za-z][\w-]*)`", re.MULTILINE)


def load_spec(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    return json.loads((root / CLIS_REL).read_text(encoding="utf-8"))


def flags_from_parser(parser: argparse.ArgumentParser) -> frozenset[str]:
    out: set[str] = set()
    for action in parser._actions:
        for token in action.option_strings or []:
            out.add(token)
    return frozenset(out)


def flags_from_docs_text(text: str) -> dict[str, frozenset[str]]:
    """Map CLI path -> flag set from markdown sections headed ``## `path` ``."""
    matches = list(SECTION_RE.finditer(text))
    per: dict[str, frozenset[str]] = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        per[match.group(1)] = frozenset(FLAG_ITEM_RE.findall(body))
    return per


def flags_from_docs_file(path: Path) -> dict[str, frozenset[str]]:
    if not path.is_file():
        return {}
    return flags_from_docs_text(path.read_text(encoding="utf-8"))


def remove_flag_line(text: str, cli_path: str, flag: str) -> str:
    """Drop the list item for `flag` under the named CLI section only."""
    matches = list(SECTION_RE.finditer(text))
    for i, match in enumerate(matches):
        if match.group(1) != cli_path:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        new_body, n = re.subn(
            rf"^[-*]\s+`{re.escape(flag)}`\s*$",
            "",
            body,
            count=1,
            flags=re.MULTILINE,
        )
        if n != 1:
            raise ValueError(f"flag {flag!r} not found under {cli_path}")
        return text[:start] + new_body + text[end:]
    raise ValueError(f"no docs section for {cli_path}")


def _hook_parsers() -> tuple[list[argparse.ArgumentParser], Any]:
    orig_init = argparse.ArgumentParser.__init__
    captured: list[argparse.ArgumentParser] = []

    def hooked(self: argparse.ArgumentParser, *a: Any, **k: Any) -> None:
        orig_init(self, *a, **k)
        captured.append(self)

    argparse.ArgumentParser.__init__ = hooked  # type: ignore[method-assign]
    return captured, orig_init


def load_cli_parser(repo: Path, spec: dict[str, Any]) -> argparse.ArgumentParser:
    """Import the CLI module and return its live ArgumentParser."""
    rel = spec["path"]
    path = repo / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    tools_cc = str(repo / "tools" / "command-center")
    if tools_cc not in sys.path:
        sys.path.insert(0, tools_cc)
    captured, orig_init = _hook_parsers()
    try:
        name = "tst0251_" + rel.replace("/", "_").replace(".", "_")
        module_spec = importlib.util.spec_from_file_location(name, path)
        if module_spec is None or module_spec.loader is None:
            raise ImportError(rel)
        mod = importlib.util.module_from_spec(module_spec)
        sys.modules[name] = mod
        module_spec.loader.exec_module(mod)
        how = spec.get("parser") or "main"
        if how == "build_parser" or hasattr(mod, "build_parser"):
            if hasattr(mod, "build_parser"):
                return mod.build_parser()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                if how == "main_noargv" or not inspect.signature(mod.main).parameters:
                    old = sys.argv
                    sys.argv = [rel, "--help"]
                    try:
                        mod.main()
                    finally:
                        sys.argv = old
                else:
                    mod.main(["--help"])
            except SystemExit:
                pass
        if not captured:
            raise RuntimeError(f"no ArgumentParser constructed for {rel}")
        return captured[-1]
    finally:
        argparse.ArgumentParser.__init__ = orig_init  # type: ignore[method-assign]


def diff_sets(
    parser_flags: frozenset[str],
    docs_flags: frozenset[str],
    waivers: frozenset[str] | None = None,
) -> dict[str, Any]:
    waived = waivers or frozenset()
    parser_not_docs = sorted((parser_flags - docs_flags) - waived)
    docs_not_parser = sorted((docs_flags - parser_flags) - waived)
    return {
        "parser": sorted(parser_flags),
        "docs": sorted(docs_flags),
        "parser_not_docs": parser_not_docs,
        "docs_not_parser": docs_not_parser,
        "waived": sorted(waived),
        "empty_both_directions": not parser_not_docs and not docs_not_parser,
    }


def live_report(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    spec = load_spec(root)
    docs_rel = spec["docs"][0]
    docs_path = root / docs_rel
    docs_text = docs_path.read_text(encoding="utf-8") if docs_path.is_file() else ""
    docs_map = flags_from_docs_text(docs_text) if docs_text else {}
    catalog_docs = []
    for rel in spec.get("catalog_docs") or []:
        p = root / rel
        catalog_docs.append({"path": rel, "present": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0})
    per_cli: list[dict[str, Any]] = []
    all_empty = True
    for cli in spec["clis"]:
        parser = load_cli_parser(root, cli)
        parser_flags = flags_from_parser(parser)
        docs_flags = docs_map.get(cli["path"], frozenset())
        row = {
            "id": cli["id"],
            "path": cli["path"],
            "parser_source": "argparse.ArgumentParser.option_strings",
            "docs_source": docs_rel,
            **diff_sets(parser_flags, docs_flags),
        }
        if not row["empty_both_directions"]:
            all_empty = False
        per_cli.append(row)
    return {
        "unit_id": UNIT,
        "docs_path": docs_rel,
        "docs_present": docs_path.is_file(),
        "catalog_docs": catalog_docs,
        "excluded": spec.get("excluded") or [],
        "clis": per_cli,
        "bidirectional_empty": all_empty,
        "cli_count": len(per_cli),
    }


def detector_control_live(repo: Path | None = None) -> dict[str, Any]:
    """Remove one unique documented flag and require the differ to name it."""
    root = repo or REPO
    spec = load_spec(root)
    docs_path = root / spec["docs"][0]
    text = docs_path.read_text(encoding="utf-8")
    target_cli = "tools/command-center/seed.py"
    target_flag = "--overlay"
    mutant = remove_flag_line(text, target_cli, target_flag)
    if target_flag in flags_from_docs_text(mutant).get(target_cli, frozenset()):
        raise RuntimeError("mutant still lists the removed flag")
    parser = load_cli_parser(root, next(c for c in spec["clis"] if c["path"] == target_cli))
    parser_flags = flags_from_parser(parser)
    mutant_docs = flags_from_docs_text(mutant).get(target_cli, frozenset())
    d = diff_sets(parser_flags, mutant_docs)
    named = target_flag in d["parser_not_docs"]
    live_docs = flags_from_docs_text(text).get(target_cli, frozenset())
    live = diff_sets(parser_flags, live_docs)
    return {
        "target_cli": target_cli,
        "removed_flag": target_flag,
        "live_empty": live["empty_both_directions"],
        "mutant_parser_not_docs": d["parser_not_docs"],
        "detector_named_removed_flag": named,
        "live_docs_untouched": docs_path.read_text(encoding="utf-8") == text,
    }


def detector_control_toy() -> dict[str, Any]:
    toy_parser_path = HERE / "fixtures" / "toy_parser.py"
    name = "tst0251_toy_parser"
    spec = importlib.util.spec_from_file_location(name, toy_parser_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    parser_flags = flags_from_parser(mod.build_parser())
    good_text = (HERE / "fixtures" / "toy_docs.md").read_text(encoding="utf-8")
    good_docs = flags_from_docs_text(good_text)["toy-cli"]
    good = diff_sets(parser_flags, good_docs)
    mutant_text = remove_flag_line(good_text, "toy-cli", "--beta")
    mutant_docs = flags_from_docs_text(mutant_text)["toy-cli"]
    bad = diff_sets(parser_flags, mutant_docs)
    return {
        "good_empty": good["empty_both_directions"],
        "removed_flag": "--beta",
        "bad_parser_not_docs": bad["parser_not_docs"],
        "detector_named_removed_flag": "--beta" in bad["parser_not_docs"],
        "good_docs_not_parser": good["docs_not_parser"],
        "good_parser_not_docs": good["parser_not_docs"],
    }


def write_inventory_from_parsers(repo: Path | None = None) -> Path:
    """Write CLI-FLAGS.md from live ArgumentParser option_strings.

    Docs extraction (markdown backticks) is a different code path from this
    writer, so probe1 is still a round-trip rather than a same-function echo.
    """
    root = repo or REPO
    spec = load_spec(root)
    docs_rel = spec["docs"][0]
    lines: list[str] = [
        "# Command-center CLI flags",
        "",
        "Operator argparse flags for the CLIs scoped by TST-0251.",
        "Each heading is a repo-relative CLI path. List items are option strings.",
        "",
    ]
    for cli in spec["clis"]:
        parser = load_cli_parser(root, cli)
        flags = sorted(flags_from_parser(parser))
        lines.append(f"## `{cli['path']}`")
        lines.append("")
        for flag in flags:
            lines.append(f"- `{flag}`")
        lines.append("")
    path = root / docs_rel
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def receipt_flag_parity(doc: dict[str, Any]) -> dict[str, Any]:
    """Locate the per-CLI flag-parity block in a schema-valid receipt."""
    for container in (doc, doc.get("extensions") or {}, doc.get("report") or {}):
        if not isinstance(container, dict):
            continue
        for key in ("flag_parity", "measurement"):
            block = container.get(key)
            if isinstance(block, dict) and isinstance(block.get("clis"), list):
                return block
    return {}


def receipt_detector_control(doc: dict[str, Any]) -> dict[str, Any]:
    """Locate the detector-control block in a schema-valid receipt."""
    for container in (doc, doc.get("extensions") or {}, doc.get("report") or {}):
        if not isinstance(container, dict):
            continue
        block = container.get("detector_control")
        if isinstance(block, dict):
            return block
    return {}
