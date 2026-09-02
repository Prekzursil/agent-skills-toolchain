#!/usr/bin/env python3
"""Write remaining shard-18 production modules."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def put(rel: str, body: str) -> None:
    path = REPO / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if not body.endswith("\n"):
        body += "\n"
    path.write_text(body.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print("W", rel, path.stat().st_size)


FUSION = r'''"""Capability-loss detector for fusions (IMP-0191)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FAILURE_CLASS = "capability-loss"
FAILURE_CLASS_ID = "fusion.capability-loss"


def load_library(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def index_workflows(library: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in library.get("workflows") or []:
        out[str(row["id"])] = row
    return out


def _tokens(stage: dict[str, Any]) -> set[str]:
    toks: set[str] = set()
    for cap in stage.get("capabilities") or []:
        toks.add(str(cap))
    for gate in stage.get("gates") or []:
        toks.add("gate:" + str(gate))
    for tool in stage.get("tools") or []:
        toks.add("tool:" + str(tool))
    for rule in stage.get("stop_rules") or []:
        toks.add("stop:" + str(rule))
    for rec in stage.get("recovery") or []:
        toks.add("recovery:" + str(rec))
    return toks


def capability_vector(workflow: dict[str, Any]) -> list[str]:
    toks: set[str] = set()
    for stage in workflow.get("stages") or []:
        toks |= _tokens(stage)
    return sorted(toks)


def resolve_sources(fusion: dict[str, Any], catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [catalog[str(sid)] for sid in fusion.get("sources") or [] if str(sid) in catalog]


def lost_capabilities(fusion: dict[str, Any], sources: list[dict[str, Any]]) -> list[str]:
    union: set[str] = set()
    for src in sources:
        union |= set(capability_vector(src))
    lost = union - set(capability_vector(fusion))
    return sorted(lost)


def detect_capability_loss(fusion: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    lost = lost_capabilities(fusion, sources)
    fired = bool(lost)
    return {
        "fired": fired,
        "lost": lost,
        "set_difference_empty": not fired,
        "failure_class": FAILURE_CLASS if fired else None,
        "failure_class_id": FAILURE_CLASS_ID if fired else None,
        "fusion_vector": capability_vector(fusion),
        "source_union": sorted({t for s in sources for t in capability_vector(s)}),
    }


def evaluate_admitted(library: dict[str, Any]) -> dict[str, Any]:
    catalog = index_workflows(library)
    admitted = library.get("admitted_fusion_ids") or [
        wid for wid, wf in catalog.items() if wf.get("kind") == "fusion" and wf.get("admitted")
    ]
    results = []
    empty_all = True
    for fid in admitted:
        fusion = catalog[str(fid)]
        sources = resolve_sources(fusion, catalog)
        det = detect_capability_loss(fusion, sources)
        rec = {
            "fusion_id": fid,
            "fired": det["fired"],
            "lost": det["lost"],
            "fusion_vector": det["fusion_vector"],
            "source_union": det["source_union"],
        }
        results.append(rec)
        if det["fired"]:
            empty_all = False
    return {
        "admitted_count": len(results),
        "set_difference_empty_for_all": empty_all,
        "results": results,
    }


def plant_dropped_stage(fusion: dict[str, Any], stage_id: str) -> dict[str, Any]:
    planted = json.loads(json.dumps(fusion))
    planted["stages"] = [s for s in planted.get("stages") or [] if str(s.get("id")) != stage_id]
    planted.pop("capability_vector", None)
    return planted
'''

MARSHALLER = r'''"""Quoting-safe command marshaller with file-based payload transport."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MAX_QUOTE_ATTEMPTS = 2


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unsafe_reasons(payload: bytes) -> list[str]:
    reasons: list[str] = []
    if b"\x00" in payload:
        reasons.append("nul")
    if b"'" in payload:
        reasons.append("apostrophe")
    if b"\nEOF\n" in payload or payload.endswith(b"\nEOF") or b"\nEOF" in payload:
        reasons.append("heredoc-eof")
    if b"$( " in payload or b"`" in payload or b"; touch " in payload or b"&&" in payload:
        reasons.append("injection")
    if b"rm -rf" in payload and b"mention" not in payload[:40]:
        # mention-only bodies still quote rm but are classified separately by corpus
        pass
    if any(ch < 32 and ch not in (9, 10, 13) for ch in payload):
        if "nul" not in reasons and b"\x00" in payload:
            pass
        elif b"\x00" not in payload:
            reasons.append("control-byte")
    return reasons


def corpus(canary: Path) -> list[dict[str, Any]]:
    touch = f"touch {canary.as_posix()}".encode("ascii")
    entries = [
        {"id": "plain-ascii", "payload": b"hello-world", "expect_unsafe": False, "shape": "plain"},
        {"id": "apostrophe", "payload": b"it's a test", "expect_unsafe": True, "shape": "apostrophe"},
        {"id": "heredoc-eof-line", "payload": b"alpha\nEOF\nomega", "expect_unsafe": True, "shape": "heredoc"},
        {"id": "injection-canary", "payload": b"ok'; " + touch + b"; echo 'x", "expect_unsafe": True, "shape": "injection"},
        {"id": "destructive-mention", "payload": b"the docs say never run `rm -rf /` on a host", "expect_unsafe": True, "shape": "mention"},
        {"id": "control-nul", "payload": b"pre\x00post", "expect_unsafe": True, "shape": "nul"},
        {"id": "double-quote", "payload": b'say "hi"', "expect_unsafe": False, "shape": "dquote"},
        {"id": "spaces", "payload": b"one two three", "expect_unsafe": False, "shape": "spaces"},
        {"id": "newlines", "payload": b"line1\nline2", "expect_unsafe": True, "shape": "newline"},
    ]
    return entries


@dataclass
class Envelope:
    mode: str
    path: Path | None = None
    reasons: list[str] = field(default_factory=list)
    argv: list[str] = field(default_factory=list)

    def payload_leaked_into_argv(self, payload: bytes) -> bool:
        blob = payload.decode("utf-8", errors="replace")
        return any(blob in arg for arg in self.argv)


@dataclass
class DeliveryResult:
    ok: bool
    round_trip: bool
    reason: str = ""
    quoting_attempts: int = 0
    switched_to_file: bool = False
    received: bytes = b""


def _python_echo_file(path: Path) -> list[str]:
    return [sys.executable, "-c", "import pathlib,sys; sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_bytes())", str(path)]


def deliver(payload: bytes, workdir: Path) -> tuple[Envelope, DeliveryResult]:
    workdir.mkdir(parents=True, exist_ok=True)
    reasons = unsafe_reasons(payload)
    if reasons:
        dest = workdir / (sha256_hex(payload)[:16] + ".payload")
        dest.write_bytes(payload)
        argv = _python_echo_file(dest)
        env = Envelope(mode="file", path=dest, reasons=reasons, argv=argv)
        proc = subprocess.run(argv, capture_output=True)
        received = proc.stdout
        ok = proc.returncode == 0 and received == payload
        return env, DeliveryResult(ok=ok, round_trip=ok, reason="" if ok else "file-echo", received=received)
    argv = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.argv[1].encode('utf-8'))", payload.decode("utf-8")]
    env = Envelope(mode="inline-argv", reasons=[], argv=argv)
    proc = subprocess.run(argv, capture_output=True)
    received = proc.stdout
    ok = proc.returncode == 0 and received == payload
    return env, DeliveryResult(ok=ok, round_trip=ok, reason="" if ok else "inline-echo", received=received)


def run_naive(transport: str, payload: bytes) -> tuple[int, bytes, str]:
    text = payload.decode("utf-8", errors="surrogateescape")
    shell = "bash"
    if transport.startswith("dash_"):
        shell = "dash"
        kind = transport[len("dash_"):]
    elif transport.startswith("bash_"):
        kind = transport[len("bash_"):]
    else:
        kind = transport
    if kind == "single_quote":
        cmd = f"printf '%s' '{text}'"
    elif kind == "double_quote":
        cmd = f'printf "%s" "{text}"'
    elif kind == "heredoc":
        cmd = f"cat <<EOF\n{text}\nEOF"
    else:
        return 2, b"", f"unknown-transport:{transport}"
    try:
        proc = subprocess.run([shell, "-c", cmd], capture_output=True, timeout=8)
    except FileNotFoundError:
        return 127, b"", f"missing-shell:{shell}"
    except subprocess.TimeoutExpired:
        return 124, b"", "timeout"
    return proc.returncode, proc.stdout, "ok" if proc.returncode == 0 else "naive-fail"


def try_naive_then_file(payload: bytes, workdir: Path, transport: str, meta: dict[str, Any] | None = None) -> DeliveryResult:
    attempts = 0
    for _ in range(MAX_QUOTE_ATTEMPTS):
        attempts += 1
        rc, out, reason = run_naive(transport, payload)
        if rc == 0 and out == payload:
            return DeliveryResult(ok=True, round_trip=True, quoting_attempts=attempts, switched_to_file=False, received=out)
    env, result = deliver(payload, workdir)
    result.quoting_attempts = attempts
    result.switched_to_file = env.mode == "file"
    return result


def run_matrix(workdir: Path, canary: Path) -> dict[str, Any]:
    entries = corpus(canary)
    cells: list[dict[str, Any]] = []
    transports = ["marshaller", "bash_single_quote", "bash_heredoc", "bash_double_quote"]
    by: dict[str, dict[str, int]] = {t: {"ok": 0, "fail": 0} for t in transports}
    for entry in entries:
        if canary.exists():
            canary.unlink()
        inv, res = deliver(entry["payload"], workdir)
        leaked = inv.payload_leaked_into_argv(entry["payload"]) if inv.mode == "file" else False
        cell = {
            "transport": "marshaller",
            "payload_id": entry["id"],
            "ok": res.ok and res.round_trip,
            "round_trip": res.round_trip,
            "leaked_into_argv": leaked,
            "canary_created": canary.is_file(),
            "mode": inv.mode,
        }
        cells.append(cell)
        by["marshaller"]["ok" if cell["ok"] else "fail"] += 1
        if canary.exists():
            canary.unlink()
        for tr in transports[1:]:
            if canary.exists():
                canary.unlink()
            rc, out, reason = run_naive(tr, entry["payload"])
            ok = rc == 0 and out == entry["payload"]
            cells.append(
                {
                    "transport": tr,
                    "payload_id": entry["id"],
                    "ok": ok,
                    "round_trip": ok,
                    "leaked_into_argv": False,
                    "canary_created": canary.is_file(),
                    "reason": reason,
                }
            )
            by[tr]["ok" if ok else "fail"] += 1
    return {
        "cells": cells,
        "payload_count": len(entries),
        "cell_count": len(cells),
        "by_transport": by,
        "destructive_mention_present": any(e["id"] == "destructive-mention" for e in entries),
    }
'''

TOMBSTONES = r'''"""Capability tombstones, redirects, and cycle detection."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

RESOLVED = "RESOLVED"
CYCLE = "CYCLE"
DEAD = "DEAD"
LIVE = "LIVE"


class DeadSelectionError(Exception):
    pass


@dataclass(frozen=True)
class Root:
    name: str
    path: Path
    kind: str


@dataclass
class Capability:
    capability_id: str
    path: Path
    kind: str


@dataclass
class Tombstone:
    old_id: str
    new_id: str | None
    path: Path


@dataclass
class ResolveResult:
    status: str
    terminal_id: str | None
    defect: str | None = None
    hops: list[str] | None = None


def default_roots(*, repo: Path, home: Path | None = None) -> list[Root]:
    home = home or Path.home()
    cands = [
        Root("repo-skills", repo / "skills", "skill"),
        Root("agents-skills", repo / ".agents" / "skills", "skill"),
        Root("claude-skills", home / ".claude" / "skills", "skill"),
    ]
    return cands


def _skill_id(path: Path) -> str:
    name = path.parent.name if path.name.upper() == "SKILL.MD" else path.stem
    if name.startswith("skill."):
        return name
    return "skill." + name


def _read_front(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta: dict[str, Any] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    meta[k.strip()] = v.strip().strip('"').strip("'")
    for key in ("tombstone", "redirect", "replaced-by", "superseded-by"):
        if key in meta:
            meta["new_id"] = meta[key]
    return meta


def discover(roots: Iterable[Root], *, repo: Path | None = None) -> tuple[list[Capability], list[Tombstone]]:
    live: list[Capability] = []
    tombs: list[Tombstone] = []
    for root in roots:
        base = Path(root.path)
        if not base.is_dir():
            continue
        table = base / "tombstones.json"
        if table.is_file():
            doc = json.loads(table.read_text(encoding="utf-8"))
            rows = doc if isinstance(doc, list) else doc.get("tombstones") or doc.get("redirects") or []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                old = str(row.get("old_id") or row.get("from") or "")
                new = row.get("new_id") or row.get("to")
                if old:
                    tombs.append(Tombstone(old_id=old, new_id=str(new) if new else None, path=table))
        for md in base.rglob("SKILL.md"):
            meta = _read_front(md)
            cid = str(meta.get("id") or _skill_id(md))
            new_id = meta.get("new_id") or meta.get("redirect")
            if meta.get("tombstone") in {True, "true", "yes"} or new_id:
                tombs.append(Tombstone(old_id=cid, new_id=str(new_id) if new_id else None, path=md))
            else:
                live.append(Capability(capability_id=cid, path=md, kind=root.kind))
    return live, tombs


def index_from_records(live: list[Capability], tombs: list[Tombstone]) -> tuple[set[str], dict[str, str | None]]:
    live_ids = {c.capability_id for c in live}
    by_old: dict[str, str | None] = {}
    for t in tombs:
        by_old[t.old_id] = t.new_id
    return live_ids, by_old


def is_tombstone(cid: str, by_old: dict[str, str | None]) -> bool:
    return cid in by_old


def resolve(cid: str, live_ids: set[str], by_old: dict[str, str | None]) -> ResolveResult:
    hops = [cid]
    cur = cid
    seen: set[str] = set()
    while cur in by_old:
        if cur in seen:
            return ResolveResult(status=CYCLE, terminal_id=None, defect="tombstone-cycle", hops=hops)
        seen.add(cur)
        nxt = by_old[cur]
        if not nxt:
            return ResolveResult(status=DEAD, terminal_id=None, defect="missing-target", hops=hops)
        hops.append(nxt)
        cur = nxt
    if cur in live_ids:
        status = RESOLVED if cid in by_old else LIVE
        return ResolveResult(status=status, terminal_id=cur, defect=None, hops=hops)
    if cid in by_old:
        return ResolveResult(status=DEAD, terminal_id=None, defect="missing-target", hops=hops)
    return ResolveResult(status=DEAD, terminal_id=None, defect="missing-target", hops=hops)


def route_selection(cid: str, live_ids: set[str], by_old: dict[str, str | None]) -> str:
    result = resolve(cid, live_ids, by_old)
    if result.status in {CYCLE, DEAD} or not result.terminal_id:
        raise DeadSelectionError(f"{cid} {result.status} {result.defect}")
    return result.terminal_id


def tombstone_table(live: list[Capability], tombs: list[Tombstone]) -> list[dict[str, Any]]:
    live_ids, by_old = index_from_records(live, tombs)
    rows = []
    for t in tombs:
        result = resolve(t.old_id, live_ids, by_old)
        rows.append(
            {
                "old_id": t.old_id,
                "new_id": t.new_id,
                "resolution": result.status,
                "terminal_id": result.terminal_id,
                "defect": result.defect,
                "hops": result.hops,
            }
        )
    return rows


def scan_roots(*, repo: Path, home: Path | None = None) -> dict[str, Any]:
    roots = default_roots(repo=repo, home=home)
    live, tombs = discover(roots, repo=repo)
    table = tombstone_table(live, tombs)
    root_rows = [{"name": r.name, "path": str(r.path), "exists": r.path.is_dir()} for r in roots]
    return {
        "roots": root_rows,
        "live_count": len(live),
        "redirect_tombstone_count": sum(1 for r in table if r.get("new_id")),
        "tombstone_table": table,
    }
'''


def main() -> None:
    put("tools/fusion/__init__.py", '"""Fusion tools."""\n')
    put("tools/fusion/capability_loss.py", FUSION)
    put("tools/dispatch/__init__.py", '"""Dispatch tools."""\n')
    put("tools/dispatch/quote_safe_marshaller.py", MARSHALLER)
    put("tools/router/tombstones.py", TOMBSTONES)
    put("router/tombstones.py", TOMBSTONES)
    put("router/__init__.py", '"""Router package."""\n')


if __name__ == "__main__":
    main()
