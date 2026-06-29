#!/usr/bin/env python
"""stale_anchor.py - PreToolUse hook: stop/warn when a tool call USES a stale RE anchor.

The user's costliest recurring failure is the wrong-but-consistent anchor: a bad
base/offset/pid silently poisons every downstream finding, discovered hours later.
The TMS (tms_core) tracks the justification graph; when a premise is retracted or a
source drifts, every dependent flips OUT. This hook reads that materialized OUT set
and, before a tool call, checks whether the call references an OUT anchor:

  SOFT (exit 0 + additionalContext):  any OUT node's value/version/symbol token
        appears in the tool_input. Injects "STALE ANCHOR ... re-derive before using".
  HARD (exit 2):  a recognized RE *write/patch to a live target* (ida/ghidra/binja/
        cheatengine/frida) whose target address/offset == an OUT node of kind
        address|offset. This is the ONLY case that blocks. Re-derive to clear it.
  SILENT (exit 0): nothing matched.

FAIL-OPEN is absolute: a missing/corrupt DB, no OUT nodes, or ANY exception ->
exit 0 (allow). Only the explicit stale-anchor HARD case may exit 2.

Soft injects are throttled/deduped (WINDOW seconds). Hard blocks are never throttled
(the write must keep failing until the anchor is re-derived and re-asserted).

Opt-out: TMS_STALE_ANCHOR=off in env, or a .disabled file in this directory.
DB source-drift is surfaced once `tms.py recheck` has refreshed it (the hook stays
read-only and never re-hashes large RE binaries inline).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
sys.path.insert(0, str(THIS))

WINDOW = 300  # seconds: dedup window for soft injects
DEC_MIN = 256  # ignore decimal tokens below this (line numbers / tiny counts)

# A tool whose op-name implies writing to a target (cheatengine write_*/auto_assemble,
# binja/ida patch_bytes, generic poke/store).
_WRITE_OP = re.compile(r"(write|patch|poke|assemble|store|wbyte)", re.I)
# Frida runs writes inside a script string, so detect the exec tool + a write primitive.
_FRIDA_EXEC = re.compile(r"(execute_in_session|create_simple_hook|create_interactive_session|spawn)", re.I)
_FRIDA_WRITE = re.compile(
    r"(patchCode|writeByteArray|writePointer|writeFloat|writeDouble|writeS8|writeU8|"
    r"writeU16|writeU32|writeU64|writeInt|writeLong|writeShort|writeAnsiString|"
    r"writeUtf8String|writeUtf16String|\.write\s*\()", re.I)

_HEX = re.compile(r"0x[0-9a-fA-F]+")
_SUB = re.compile(r"\bsub_([0-9a-fA-F]{4,})\b")
_BAREHEX = re.compile(r"\b[0-9a-fA-F]{5,}\b")
_DEC = re.compile(r"\b\d+\b")
_VER = re.compile(r"\b\d+(?:\.\d+){1,}\b")
_SYM = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{5,}\b")
_ADDR_KEY = re.compile(r"(addr|address|target|location|offset|ptr|pointer|dest)", re.I)


# --------------------------------------------------------------------------- #
# token extraction
# --------------------------------------------------------------------------- #
def _ints_from(text: str, with_dec: bool = True) -> set[int]:
    out: set[int] = set()
    for m in _HEX.findall(text):
        out.add(int(m, 16))
    for m in _SUB.findall(text):
        out.add(int(m, 16))
    for m in _BAREHEX.findall(text):
        if any(c in "abcdefABCDEF" for c in m):  # has a hex letter -> treat as hex
            out.add(int(m, 16))
    if with_dec:
        for m in _DEC.findall(text):
            v = int(m)
            if v >= DEC_MIN:
                out.add(v)
    return out


def node_ints(node: dict) -> set[int]:
    text = f"{node['id']} {node['statement']}"
    with_dec = node["kind"] in ("offset", "pid", "address")
    return _ints_from(text, with_dec=with_dec)


def node_versions(node: dict) -> list[str]:
    if node["kind"] != "version":
        return []
    return _VER.findall(f"{node['id']} {node['statement']}")


def node_symbols(node: dict) -> set[str]:
    syms = set()
    for tok in _SYM.findall(f"{node['id']} {node['statement']}"):
        looks_symbolic = "_" in tok or any(c.isdigit() for c in tok) or (
            tok != tok.lower() and tok != tok.upper())
        if looks_symbolic:
            syms.add(tok)
    return syms


def target_address_ints(tool_input) -> set[int]:
    """Ints found in address-like keys of the tool_input (the write *target*)."""
    ints: set[int] = set()

    def walk(obj, key=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, str(k))
        elif isinstance(obj, list):
            for v in obj:
                walk(v, key)
        elif _ADDR_KEY.search(key):
            ints.update(_ints_from(str(obj)))

    walk(tool_input)
    return ints


# --------------------------------------------------------------------------- #
# matching / decision
# --------------------------------------------------------------------------- #
def find_refs(out_nodes: list[dict], input_text: str) -> list[tuple[dict, str, list]]:
    """OUT nodes referenced by input_text: [(node, match_type, hits), ...]."""
    in_ints = _ints_from(input_text)
    refs: list[tuple[dict, str, list]] = []
    for n in out_nodes:
        shared = sorted(node_ints(n) & in_ints)
        if shared:
            refs.append((n, "value", shared))
            continue
        vhit = [v for v in node_versions(n) if v in input_text]
        if vhit:
            refs.append((n, "version", vhit))
            continue
        shit = sorted(s for s in node_symbols(n) if s in input_text)
        if shit:
            refs.append((n, "symbol", shit))
    return refs


def decide(tool_name: str, tool_input, out_nodes: list[dict]) -> dict | None:
    input_text = json.dumps(tool_input, ensure_ascii=False, default=repr)
    refs = find_refs(out_nodes, input_text)
    if not refs:
        return None
    op = tool_name.split("__")[-1]
    is_frida_write = bool(_FRIDA_EXEC.search(op) and _FRIDA_WRITE.search(input_text))
    write = bool(_WRITE_OP.search(op)) or is_frida_write
    target_ints = target_address_ints(tool_input)
    if not target_ints and is_frida_write:
        target_ints = _ints_from(input_text)
    hard = None
    if write:
        for n, _mtype, hits in refs:
            if n["kind"] in ("address", "offset") and (node_ints(n) & target_ints):
                hard = (n, sorted(node_ints(n) & target_ints))
                break
    return {"refs": refs, "write": write, "hard": hard}


# --------------------------------------------------------------------------- #
# messaging
# --------------------------------------------------------------------------- #
def _fmt_val(hits) -> str:
    if hits and isinstance(hits[0], int):
        return "0x%x" % hits[0]
    return str(hits[0]) if hits else "?"


def _premise_clause(conn, tms, node_id: str) -> str:
    causes = tms.root_causes(conn, node_id)
    if not causes:
        return "an OUT premise (re-run tms.py explain)"
    cid, why = causes[0]
    extra = f" (+{len(causes) - 1} more)" if len(causes) > 1 else ""
    if cid == node_id:
        return f"itself ({why}){extra}"
    return f"premise '{cid}' which was {why}{extra}"


def soft_msg(conn, tms, refs) -> str:
    n, mtype, hits = _primary(refs)
    val = _fmt_val(hits)
    clause = _premise_clause(conn, tms, n["id"])
    more = f"  [+{len(refs) - 1} more OUT ref(s)]" if len(refs) > 1 else ""
    return (f"STALE ANCHOR: {val} (node '{n['id']}', match={mtype}) is OUT - it rests on "
            f"{clause} - re-derive before using.{more} "
            f"(TMS soft warning; not blocking. `python ~/.claude/hooks/tms/tms.py explain {n['id']}`)")


def hard_msg(conn, tms, node, hits) -> str:
    val = _fmt_val(hits)
    clause = _premise_clause(conn, tms, node["id"])
    return (f"STALE ANCHOR (BLOCKED): refusing write/patch to {val} - it targets node "
            f"'{node['id']}' ({node['kind']}) which is OUT because it rests on {clause}. "
            f"A bad anchor poisons every downstream finding. Re-derive it, then "
            f"`python ~/.claude/hooks/tms/tms.py assert {node['id']} --statement ... --kind "
            f"{node['kind']} [--premises ...]` to clear OUT, and retry. "
            f"(TMS hard gate - the only case that blocks; set TMS_STALE_ANCHOR=off to disable.)")


def _primary(refs):
    """Prefer an address/offset value match for the headline."""
    for r in refs:
        if r[0]["kind"] in ("address", "offset") and r[1] == "value":
            return r
    return refs[0]


# --------------------------------------------------------------------------- #
# throttle
# --------------------------------------------------------------------------- #
def _state_path(tms) -> str:
    return os.path.join(os.path.dirname(tms.db_path()), ".stale_anchor_state.json")


def _throttled(tms, key: str) -> bool:
    p = _state_path(tms)
    now = time.time()
    try:
        state = json.loads(Path(p).read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except Exception:
        state = {}
    state = {k: v for k, v in state.items() if isinstance(v, (int, float)) and now - v < WINDOW * 4}
    recent = (now - state.get(key, 0)) < WINDOW
    state[key] = now
    try:
        Path(p).write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass
    return recent


# --------------------------------------------------------------------------- #
# entry
# --------------------------------------------------------------------------- #
def main() -> int:
    try:
        if DISABLED.exists() or os.environ.get("TMS_STALE_ANCHOR", "").lower() in ("off", "0", "false"):
            return 0
        data = json.loads(sys.stdin.read() or "{}")
        tool_name = str(data.get("tool_name") or "")
        tool_input = data.get("tool_input") or {}

        import tms_core as tms
        try:
            conn = tms.connect(create=False, readonly=True)
            out_nodes = [dict(r) for r in conn.execute("SELECT * FROM nodes WHERE status='OUT'")]
        except Exception:
            return 0  # missing / corrupt DB -> fail-open

        if not out_nodes:
            return 0
        verdict = decide(tool_name, tool_input, out_nodes)
        if not verdict:
            return 0

        if verdict["hard"]:
            node, hits = verdict["hard"]
            sys.stderr.write(hard_msg(conn, tms, node, hits))
            return 2  # the only blocking path

        key = "soft:%s:%s" % (tool_name, ",".join(sorted(r[0]["id"] for r in verdict["refs"])))
        if _throttled(tms, key):
            return 0
        msg = soft_msg(conn, tms, verdict["refs"])
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": msg}}))
        return 0
    except Exception:
        return 0  # fail-open: a TMS failure must never block legitimate work


if __name__ == "__main__":
    sys.exit(main())
