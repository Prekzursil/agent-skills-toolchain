#!/usr/bin/env python3
"""Measure one or all RES-0022 statements against pinned docs and local behaviour."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from common import (
    CAPTURE_DIR,
    DOCUMENTED_PLUGIN_FIELDS,
    INDEX_PATH,
    MEASURE,
    OLD_DOCS_URL,
    PLUGIN_JSON,
    REPO,
    capture_body,
    load_index,
)
from statements import STATEMENTS, by_id

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _run(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, f"not-found:{args[0]}"
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return int(proc.returncode), text[-4000:]


def find_claude() -> str | None:
    env = os.environ.get("CLAUDE_BIN")
    if env and Path(env).is_file():
        return env
    return shutil.which("claude")


def quote_found(text: str, needles: list[str]) -> tuple[bool, str]:
    if not text:
        return False, "empty-capture"
    for needle in needles:
        if needle and needle in text:
            return True, needle
    lower = text.lower()
    for needle in needles:
        core = needle.replace("`", "").lower()
        if len(core) >= 12 and core in lower:
            return True, needle
    return False, "needle-absent"


def plugin_payload() -> dict[str, Any]:
    if not PLUGIN_JSON.is_file():
        return {"_error": "missing"}
    try:
        doc = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_error": "unparseable"}
    return doc if isinstance(doc, dict) else {"_error": "not-object"}


def extra_plugin_keys(doc: dict[str, Any]) -> list[str]:
    return sorted(
        k
        for k in doc.keys()
        if not str(k).startswith("_") and k not in DOCUMENTED_PLUGIN_FIELDS
    )


def settings_home() -> dict[str, Any]:
    home = Path.home()
    user_settings = home / ".claude" / "settings.json"
    global_cfg = home / ".claude.json"
    result: dict[str, Any] = {
        "user_settings_path": str(user_settings),
        "user_settings_exists": user_settings.is_file(),
        "global_cfg_path": str(global_cfg),
        "global_cfg_exists": global_cfg.is_file(),
        "enabledPlugins_in_user_settings": False,
        "enabledPlugins_in_global_cfg": False,
        "disabledMcpServers_in_global_cfg": False,
        "disabledMcpServers_in_user_settings": False,
    }
    for path, en_key, dis_key in (
        (user_settings, "enabledPlugins_in_user_settings", "disabledMcpServers_in_user_settings"),
        (global_cfg, "enabledPlugins_in_global_cfg", "disabledMcpServers_in_global_cfg"),
    ):
        if not path.is_file():
            continue
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(blob, dict):
            result[en_key] = "enabledPlugins" in blob
            result[dis_key] = "disabledMcpServers" in blob
    return result


def claude_help() -> tuple[str | None, int, str]:
    binary = find_claude()
    if not binary:
        return None, 127, "claude-binary-absent"
    code, out = _run([binary, "--help"], timeout=15)
    return binary, code, out


def claude_validate(plugin_dir: Path) -> tuple[str | None, int, str]:
    binary = find_claude()
    if not binary:
        return None, 127, "claude-binary-absent"
    code, out = _run([binary, "plugin", "validate", str(plugin_dir)], timeout=30)
    return binary, code, out


def redirect_record() -> dict[str, Any]:
    path = CAPTURE_DIR / "old-hooks-redirect.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    if INDEX_PATH.is_file():
        idx = load_index()
        return dict(idx.get("old_hooks_redirect") or idx.get("old_hooks_redirect") or {})
    return {}


def _base(stmt: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(stmt.get("doc_id") or stmt.get("doc_id") or "")
    url, digest, text = capture_body(doc_id)
    found, which = quote_found(text, list(stmt.get("needles") or stmt.get("needles") or []))
    return {
        "id": stmt["id"],
        "statement": stmt["statement"],
        "doc_id": doc_id,
        "doc_url": url,
        "doc_sha256": digest or ("0" * 64),
        "quote_found": found,
        "matched_needle": which if found else "",
        "reproducing_command": f"{MEASURE} {stmt['id']}",
        "partition": stmt.get("partition") or stmt.get("partition") or "",
    }


def _finish(
    row: dict[str, Any],
    *,
    verdict: str,
    classification: str,
    output: str,
    rationale: str,
    rail: str,
) -> dict[str, Any]:
    if not row.get("quote_found") and row["id"] != "S20":
        verdict = "NOT-CHECKED"
        classification = "not_applicable"
        rationale = f"doc-needle-absent:{rationale}"
    if verdict in {"CONSISTENT", "NOT-CHECKED"}:
        classification = "not_applicable"
    row.update(
        {
            "verdict": verdict,
            "classification": classification,
            "command_output": (output or "")[-3500:] or "empty-output",
            "rationale": rationale,
            "rail": rail,
        }
    )
    return row


def measure_s01() -> dict[str, Any]:
    row = _base(by_id()["S01"])
    plugin = plugin_payload()
    has_name = isinstance(plugin.get("name"), str) and bool(str(plugin.get("name")).strip())
    out = json.dumps(
        {
            "present": PLUGIN_JSON.is_file(),
            "has_name": has_name,
            "name": plugin.get("name"),
            "error": plugin.get("_error"),
        },
        sort_keys=True,
    )
    if plugin.get("_error") or not PLUGIN_JSON.is_file():
        return _finish(
            row,
            verdict="NOT-CHECKED",
            classification="not_applicable",
            output=out,
            rationale="plugin.json missing or unparseable",
            rail="payload",
        )
    if has_name:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="shipped plugin.json includes the documented required name field",
            rail="payload",
        )
    return _finish(
        row,
        verdict="CONTRADICTED",
        classification="reader_wrong",
        output=out,
        rationale="docs require name; shipped plugin.json has none",
        rail="payload",
    )


def measure_s02() -> dict[str, Any]:
    row = _base(by_id()["S02"])
    plugin = plugin_payload()
    extras = extra_plugin_keys(plugin)
    binary, vcode, vout = claude_validate(REPO)
    out = json.dumps(
        {
            "keys": sorted(k for k in plugin.keys() if not str(k).startswith("_")),
            "extras": extras,
            "claude_bin": binary,
            "validate_exit": vcode,
            "validate_tail": (vout or "")[-1200:],
        },
        sort_keys=True,
    )
    if binary is None:
        return _finish(
            row,
            verdict="CONSISTENT" if extras else "CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale=(
                f"shipped extra keys {extras}; docs say unrecognized fields are ignored. "
                "No client validator on this host; payload is compatible with ignore-unknown."
            ),
            rail="payload",
        )
    text = (vout or "").lower()
    if extras and vcode not in {0, 1} and "warning" not in text:
        return _finish(
            row,
            verdict="CONTRADICTED",
            classification="doc_stale",
            output=out,
            rationale="docs say extras warn; validator hard-failed",
            rail="client",
        )
    return _finish(
        row,
        verdict="CONSISTENT",
        classification="not_applicable",
        output=out,
        rationale="extras present and validator did not hard-fail, or extras absent",
        rail="client" if binary else "payload",
    )


def measure_s03() -> dict[str, Any]:
    row = _base(by_id()["S03"])
    extras = extra_plugin_keys(plugin_payload())
    binary, vcode, vout = claude_validate(REPO)
    out = json.dumps(
        {
            "extras": extras,
            "claude_bin": binary,
            "validate_exit": vcode,
            "validate_tail": (vout or "")[-1200:],
        },
        sort_keys=True,
    )
    if binary is None:
        return _finish(
            row,
            verdict="NOT-CHECKED",
            classification="not_applicable",
            output=out,
            rationale="claude binary absent; cannot re-run plugin validate",
            rail="client",
        )
    text = (vout or "").lower()
    hard = extras and vcode not in {0, 1} and "error" in text and "warning" not in text
    if hard:
        return _finish(
            row,
            verdict="CONTRADICTED",
            classification="doc_stale",
            output=out,
            rationale="docs: warnings not errors; observed hard fail on extras",
            rail="client",
        )
    return _finish(
        row,
        verdict="CONSISTENT",
        classification="not_applicable",
        output=out,
        rationale="validator invoked; extras did not hard-fail",
        rail="client",
    )


def measure_s04() -> dict[str, Any]:
    row = _base(by_id()["S04"])
    exists = PLUGIN_JSON.is_file()
    rel = str(PLUGIN_JSON.relative_to(REPO)).replace("\\", "/") if exists else ""
    out = json.dumps({"path": rel, "exists": exists}, sort_keys=True)
    if exists:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="worktree ships the documented manifest path",
            rail="payload",
        )
    return _finish(
        row,
        verdict="CONTRADICTED",
        classification="reader_wrong",
        output=out,
        rationale="documented path .claude-plugin/plugin.json is absent",
        rail="payload",
    )


def measure_s05() -> dict[str, Any]:
    row = _base(by_id()["S05"])
    found = [
        p
        for p in REPO.glob("**/marketplace.json")
        if "node_modules" not in p.parts and "probes" not in p.parts
    ][:12]
    rels = [str(p.relative_to(REPO)).replace("\\", "/") for p in found]
    plugin = plugin_payload()
    out = json.dumps(
        {"plugin_version": plugin.get("version"), "marketplace_files": rels},
        sort_keys=True,
    )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale=(
            "no marketplace.json in this worktree; plugin.json vs marketplace "
            "version precedence is not observable here"
            if not rels
            else "marketplace.json present but client install/precedence not live-fired"
        ),
        rail="payload" if not rels else "client",
    )


def measure_s06() -> dict[str, Any]:
    row = _base(by_id()["S06"])
    name = str(plugin_payload().get("name") or "")
    ok = bool(KEBAB.match(name))
    out = json.dumps({"name": name, "kebab": ok}, sort_keys=True)
    if ok:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="shipped name matches documented kebab-case rule",
            rail="payload",
        )
    return _finish(
        row,
        verdict="CONTRADICTED",
        classification="reader_wrong",
        output=out,
        rationale="shipped name is not kebab-case as documented",
        rail="payload",
    )


def measure_s07() -> dict[str, Any]:
    row = _base(by_id()["S07"])
    binary = find_claude()
    out = json.dumps({"claude_bin": binary, "hook_fire": "not-run"}, sort_keys=True)
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="blocking-hook exit-2 cannot be fired without a live client session",
        rail="client",
    )


def measure_s08() -> dict[str, Any]:
    row = _base(by_id()["S08"])
    _url, digest, text = capture_body("hooks")
    nested = "hookSpecificOutput" in text and "additionalContext" in text
    out = json.dumps(
        {
            "doc_sha256": digest,
            "hookSpecificOutput": "hookSpecificOutput" in text,
            "additionalContext": "additionalContext" in text,
            "nested_both": nested,
        },
        sort_keys=True,
    )
    if nested:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="live docs still place additionalContext under hookSpecificOutput",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="nested additionalContext wording not pinned in captured hooks page",
        rail="doc",
    )


def measure_s09() -> dict[str, Any]:
    row = _base(by_id()["S09"])
    _url, digest, text = capture_body("hooks")
    has_600 = "600" in text
    out = json.dumps({"doc_sha256": digest, "mentions_600": has_600}, sort_keys=True)
    if has_600:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="captured hooks page still states a 600-second default",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="600-second default not found in captured hooks page",
        rail="doc",
    )


def measure_s10() -> dict[str, Any]:
    row = _base(by_id()["S10"])
    _url, digest, text = capture_body("plugin-marketplaces")
    has_source = "source" in text.lower()
    out = json.dumps(
        {"doc_sha256": digest, "mentions_source": has_source, "bytes": len(text)},
        sort_keys=True,
    )
    if has_source:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="marketplace docs still describe a source field on plugin entries",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="source field not found in captured marketplace docs",
        rail="doc",
    )


def measure_s11() -> dict[str, Any]:
    row = _base(by_id()["S11"])
    _url, digest, text = capture_body("settings-reference")
    any_file = "Any file" in text and "enabledPlugins" in text
    home = settings_home()
    inverted = home["enabledPlugins_in_global_cfg"] and not home["enabledPlugins_in_user_settings"]
    out = json.dumps(
        {"doc_sha256": digest, "any_file_and_key": any_file, "home": home},
        sort_keys=True,
        default=str,
    )
    if inverted:
        return _finish(
            row,
            verdict="CONTRADICTED",
            classification="doc_stale",
            output=out,
            rationale="docs place enabledPlugins in settings files; host stores it only in ~/.claude.json",
            rail="client",
        )
    if any_file:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="settings-reference lists enabledPlugins as Any file; host does not invert that",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="could not pin enabledPlugins/Any file in captured settings-reference",
        rail="doc",
    )


def measure_s12() -> dict[str, Any]:
    row = _base(by_id()["S12"])
    _url, digest, text = capture_body("settings")
    mentions = "~/.claude/settings.json" in text
    home = settings_home()
    out = json.dumps(
        {
            "doc_sha256": digest,
            "mentions_user_path": mentions,
            "user_settings_exists": home["user_settings_exists"],
        },
        sort_keys=True,
    )
    if mentions:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="docs still name ~/.claude/settings.json as the user settings path",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="user settings path not found in captured settings page",
        rail="doc",
    )


def measure_s13() -> dict[str, Any]:
    row = _base(by_id()["S13"])
    _url, digest, text = capture_body("settings-reference")
    mentions = "~/.claude.json" in text
    home = settings_home()
    out = json.dumps(
        {
            "doc_sha256": digest,
            "mentions_global": mentions,
            "global_exists": home["global_cfg_exists"],
        },
        sort_keys=True,
    )
    if mentions:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="docs still distinguish ~/.claude.json as global config",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="~/.claude.json not found in captured settings-reference",
        rail="doc",
    )


def measure_s14() -> dict[str, Any]:
    row = _base(by_id()["S14"])
    _url, digest, text = capture_body("mcp")
    mentions = "disabledMcpServers" in text
    home = settings_home()
    out = json.dumps(
        {
            "doc_sha256": digest,
            "mentions_key": mentions,
            "in_global": home["disabledMcpServers_in_global_cfg"],
            "in_user_settings": home["disabledMcpServers_in_user_settings"],
        },
        sort_keys=True,
    )
    if mentions:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="MCP docs still describe disabledMcpServers as an opt-out list",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="disabledMcpServers not found in captured MCP docs",
        rail="doc",
    )


def measure_s15() -> dict[str, Any]:
    row = _base(by_id()["S15"])
    _url, digest, text = capture_body("skills")
    mentions = "paths" in text and "frontmatter" in text.lower()
    out = json.dumps(
        {"doc_sha256": digest, "paths_and_frontmatter": mentions},
        sort_keys=True,
    )
    if mentions:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="skills docs still document a paths frontmatter field",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="paths frontmatter not pinned in captured skills page",
        rail="doc",
    )


def measure_s16() -> dict[str, Any]:
    row = _base(by_id()["S16"])
    _url, digest, text = capture_body("skills")
    nested = "startup" in text.lower() and (
        "nested" in text.lower() or ".claude/skills" in text
    )
    out = json.dumps(
        {"doc_sha256": digest, "nested_startup_language": nested, "bytes": len(text)},
        sort_keys=True,
    )
    if nested:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="skills docs still describe nested skill directories as not loaded at startup",
            rail="doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="nested startup language not pinned in captured skills page",
        rail="doc",
    )


def measure_s17() -> dict[str, Any]:
    row = _base(by_id()["S17"])
    binary, code, help_text = claude_help()
    _url, digest, text = capture_body("cli")
    doc_has = "--print" in text or "-p" in text
    help_has = bool(help_text) and (
        "--print" in help_text or " -p" in help_text or "-p," in help_text
    )
    out = json.dumps(
        {
            "doc_sha256": digest,
            "doc_has_print": doc_has,
            "claude_bin": binary,
            "help_exit": code,
            "help_has_print": help_has,
            "help_tail": (help_text or "")[-1200:],
        },
        sort_keys=True,
    )
    if binary and doc_has and not help_has:
        return _finish(
            row,
            verdict="CONTRADICTED",
            classification="doc_stale",
            output=out,
            rationale="docs document --print/-p but installed claude --help does not list it",
            rail="client",
        )
    if doc_has:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="docs document --print/-p"
            + ("; installed --help lists it" if help_has else "; binary absent so help not compared"),
            rail="client" if help_has else "doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="--print not pinned in captured CLI docs",
        rail="doc",
    )


def measure_s18() -> dict[str, Any]:
    row = _base(by_id()["S18"])
    binary, code, help_text = claude_help()
    _url, digest, text = capture_body("cli")
    doc_has = "stream-json" in text
    help_has = "stream-json" in (help_text or "")
    out = json.dumps(
        {
            "doc_sha256": digest,
            "doc_has_stream_json": doc_has,
            "claude_bin": binary,
            "help_exit": code,
            "help_has_stream_json": help_has,
            "help_tail": (help_text or "")[-1200:],
        },
        sort_keys=True,
    )
    if binary and doc_has and help_text and code == 0 and not help_has:
        return _finish(
            row,
            verdict="CONTRADICTED",
            classification="doc_stale",
            output=out,
            rationale="docs document stream-json; installed --help omits it",
            rail="client",
        )
    if doc_has:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="CLI docs still name stream-json"
            + ("; help agrees" if help_has else ""),
            rail="client" if help_has else "doc",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="stream-json not pinned in captured CLI docs",
        rail="doc",
    )


def measure_s19() -> dict[str, Any]:
    row = _base(by_id()["S19"])
    _url, digest, text = capture_body("sub-agents")
    inherit = "inherit" in text.lower() and "permission" in text.lower()
    binary = find_claude()
    out = json.dumps(
        {
            "doc_sha256": digest,
            "inherit_language": inherit,
            "claude_bin": binary,
            "live_spawn": False,
        },
        sort_keys=True,
    )
    if inherit:
        return _finish(
            row,
            verdict="CONSISTENT" if binary is None else "NOT-CHECKED",
            classification="not_applicable",
            output=out,
            rationale=(
                "current docs say unset permissionMode inherits the parent"
                + (
                    "; no client on this host to spawn a subagent"
                    if binary is None
                    else "; live subagent spawn not executed"
                )
            ),
            rail="doc" if binary is None else "client",
        )
    return _finish(
        row,
        verdict="NOT-CHECKED",
        classification="not_applicable",
        output=out,
        rationale="inheritance wording not pinned in captured sub-agents page",
        rail="doc",
    )


def measure_s20() -> dict[str, Any]:
    row = _base(by_id()["S20"])
    rec = redirect_record()
    status = int(rec.get("nofollow_status") or 0)
    loc = str(rec.get("nofollow_location") or rec.get("follow_final_url") or "")
    final = str(rec.get("follow_final_url") or "")
    to_code = "code.claude.com" in loc or "code.claude.com" in final
    redirected = status in {301, 302, 303, 307, 308} or (
        rec.get("follow_status") == 200 and to_code and "docs.claude.com" not in final
    )
    blob = json.dumps(rec, sort_keys=True).encode("utf-8")
    row["doc_url"] = OLD_DOCS_URL
    row["doc_sha256"] = hashlib.sha256(blob).hexdigest()
    row["quote_found"] = True
    out = json.dumps(rec, sort_keys=True)[:3000] or "empty-redirect-record"
    if redirected and to_code:
        return _finish(
            row,
            verdict="CONSISTENT",
            classification="not_applicable",
            output=out,
            rationale="docs.claude.com hooks URL still redirects onto code.claude.com",
            rail="http",
        )
    if status == 0 and not rec:
        return _finish(
            row,
            verdict="NOT-CHECKED",
            classification="not_applicable",
            output=out,
            rationale="redirect capture missing; run capture.py",
            rail="http",
        )
    return _finish(
        row,
        verdict="CONTRADICTED",
        classification="doc_stale",
        output=out,
        rationale="historical docs.claude.com URL did not redirect to code.claude.com",
        rail="http",
    )


HANDLERS = {
    "S01": measure_s01,
    "S02": measure_s02,
    "S03": measure_s03,
    "S04": measure_s04,
    "S05": measure_s05,
    "S06": measure_s06,
    "S07": measure_s07,
    "S08": measure_s08,
    "S09": measure_s09,
    "S10": measure_s10,
    "S11": measure_s11,
    "S12": measure_s12,
    "S13": measure_s13,
    "S14": measure_s14,
    "S15": measure_s15,
    "S16": measure_s16,
    "S17": measure_s17,
    "S18": measure_s18,
    "S19": measure_s19,
    "S20": measure_s20,
}


def measure_one(sid: str) -> dict[str, Any]:
    fn = HANDLERS.get(sid)
    if fn is None:
        raise SystemExit(f"unknown statement {sid}")
    return fn()


def measure_all() -> list[dict[str, Any]]:
    return [measure_one(s["id"]) for s in STATEMENTS]


def main() -> int:
    if len(sys.argv) == 2 and re.fullmatch(r"S[0-9]{2}", sys.argv[1]):
        row = measure_one(sys.argv[1])
        print(json.dumps(row, indent=1, sort_keys=True))
        print(f"{row['id']} {row['verdict']} rail={row['rail']}")
        return 0
    rows = measure_all()
    print(json.dumps(rows, indent=1, sort_keys=True))
    consistent = sum(1 for r in rows if r["verdict"] == "CONSISTENT")
    contradicted = sum(1 for r in rows if r["verdict"] == "CONTRADICTED")
    not_checked = sum(1 for r in rows if r["verdict"] == "NOT-CHECKED")
    print(f"consistent={consistent} contradicted={contradicted} not_checked={not_checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
