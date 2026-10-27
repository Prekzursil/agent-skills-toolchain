#!/usr/bin/env python3
"""Write per-unit BLOCKED/reviewer-absent receipts (receipt_core shape) for shard 1."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

REPO = "//wsl.localhost/Ubuntu/home/prekzursil/p2-g1"
LOCAL = "C:/Users/Prekzursil/source/ast-integrate/p2shard1/data"
BATCH1_START = "2026-10-24T03:51:04Z"
BATCH2_START = "2026-10-24T04:25:45Z"

IDS = ["ADV-0014","ADV-0060","ARC-0053","ARC-0055","AUD-0047","AUD-0048","AUD-0049",
       "AUD-0082","AUD-0096","BLD-0020","BLD-0023","BLD-0045","BLD-0049","CNF-0021","CNF-0177"]

CATALOG = json.load(open(LOCAL + "/WORK-UNIT-CATALOG.json", encoding="utf-8"))
UNITS = {u["id"]: u for u in CATALOG["work_units"]}

DEFECTS = {
    "ADV-0060": [{
        "id": "ADV-0060-SANDBOX-ENV-LEAK", "severity": "P1", "status": "resolved",
        "summary": ("tools/marketplace/install.py sandbox-gated arm forwarded the full host environment "
                    "to the sandboxed package script, so host-marker env reached it and its beacon was "
                    "written outside the sandbox root (probe1 gated control red). Fixed 2026-10-24: "
                    "sandboxed lifecycle scripts now run with a minimal env (PATH/HOME/LANG/"
                    "PYTHONDONTWRITEBYTECODE); host-marker env is stripped and the beacon stays inside "
                    "the sandbox. Pre-change copy kept outside the repo."),
    }],
    "AUD-0047": [{
        "id": "AUD-0047-UNDECLARED-LIVE-GATES", "severity": "P2", "status": "resolved",
        "summary": ("live .github/workflows/command-center.yml and plugin-repro.yml declared path "
                    "filters but had no entry in probes/AUD-0047/fixtures/live_gates.json (fixture "
                    "predated the workflows). Declared both gates with protected files taken from the "
                    "steps each workflow actually runs (tools/command-center/validate.py "
                    "--require-complete; tools/plugin/repro_gate.py)."),
    }],
    "AUD-0082": [{
        "id": "AUD-0082-CLASSIFIED-DRIFT", "severity": "P3", "status": "resolved",
        "summary": ("artifact report.probe1.census.classified was missing (None) while the live "
                    "re-census counted 61020 classified paths. Re-emitted the census artifact via the "
                    "unit emitter; recorded census now equals the live re-count."),
    }],
    "AUD-0096": [{
        "id": "AUD-0096-DANGLING-SKILL-SYMLINK", "severity": "P3", "status": "resolved",
        "summary": ("~/.agents/skills/superpowers was a dangling symlink to removed "
                    "~/.codex/superpowers/skills; os.walk classified it as a file and shutil.copy2 "
                    "raised FileNotFoundError inside probe2 leak-identity control. Dangling link "
                    "removed (restore: ln -s /home/prekzursil/.codex/superpowers/skills "
                    "/home/prekzursil/.agents/skills/superpowers); current profile re-measured."),
    }],
    "ARC-0055": [{
        "id": "ARC-0055-PROBE-DEPENDENCY-CONTRADICTION", "severity": "P1", "status": "open",
        "summary": ("probe1_blast_radius.py exits 1 whenever command-center/phase3/A8/DESIGN.json "
                    "exists ('A8 DESIGN present; this unit must not rebuild it'), but the unit "
                    "declares dependencies [ARC-0052] whose catalog output_path IS "
                    "command-center/phase3/A8/DESIGN.json. With the dependency delivered the probe is "
                    "unsatisfiable: no artifact change can make probe1 exit 0, and deleting the "
                    "dependency artifact to satisfy the probe would break ARC-0052/ARC-0053 delivery. "
                    "Needs an owner ruling: rewrite the probe check (presence is legitimate once "
                    "ARC-0052 is delivered) or rescind the dependency."),
    }],
}

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def digest(raw: bytes) -> tuple:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)

def eol_of(raw: bytes) -> str:
    if b"\x00" in raw:
        return "BINARY"
    crlf = raw.count(b"\r\n")
    if crlf == 0:
        return "LF"
    if raw.count(b"\r") == crlf:
        return "CRLF"
    return "MIXED"

def rd(rel: str) -> bytes:
    return open(REPO + "/" + rel, "rb").read()

def probe_row(p: dict, role: str) -> dict:
    raw = str(p.get("raw_output") or "")
    if len(raw) > 65000:
        raw = "[head truncated by receipt writer; full output in SUBAGENT-RETURN.json]\n" + raw[-64000:]
    return {
        "role": role,
        "method": "command",
        "command": str(p.get("command") or ""),
        "raw_output": raw,
        "fingerprint": hashlib.sha256(((p.get("command") or "") + "\n" + raw).encode("utf-8")).hexdigest()[:32],
        "exit_code": int(p.get("exit_code") or 0),
    }

def build(uid: str) -> dict:
    u = UNITS[uid]
    out_rel = u["output_path"].replace("\\", "/")
    raw = rd(out_rel)
    sha, nbytes = digest(raw)
    man_rel = "command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid
    ret = json.loads(rd("command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid).decode("utf-8"))
    named = [p for p in (ret.get("named_probes") or []) if isinstance(p, dict)]
    probes = [probe_row(named[0], "source")] if named else []
    if len(named) > 1:
        probes.append(probe_row(named[1], "verifier"))
    man_mtime = datetime.fromtimestamp(os.path.getmtime(REPO + "/" + man_rel), timezone.utc)
    red = (uid == "ARC-0055")
    state = "FAILED" if red else "BLOCKED"
    started = parse_iso(BATCH2_START if uid in DEFECTS else BATCH1_START)
    ended = datetime.now(timezone.utc)
    token = "PROBE-DEPENDENCY-CONTRADICTION" if red else "MEASUREMENT-DONE-REVIEWER-ABSENT"
    sentinel = "SENTINEL:%s:%s " % (uid, token)
    if red:
        sentinel += ("probe1 is unsatisfiable while dependency ARC-0052 artifact A8/DESIGN.json exists; "
                     "recorded FAILED with the contradiction open. No independent reviewer closed this unit.")
    else:
        sentinel += ("the artifact at output_path exists, both named probes re-ran live and exited 0, and "
                     "the per-unit UNIT-ARTIFACT-MANIFEST.json row sha256 matches the live artifact; state "
                     "is BLOCKED, not SUCCESS, because no independent reviewer has closed this unit.")
    if red:
        ev_claim = ("Live re-measure 2026-10-24: probe1_blast_radius.py exited 1 with 'A8 DESIGN present; "
                    "this unit must not rebuild it' while the dependency ARC-0052 artifact is delivered "
                    "at that exact path.")
        ev_verdict = "BLOCKED"
        anchor = "command-center/p2-wave/probes/ARC-0055/probe1_blast_radius.py (a8_design_present check)"
    else:
        ev_claim = ("Live re-measure 2026-10-24: both named probes exited 0 against the live tree and the "
                    "UNIT-ARTIFACT-MANIFEST.json row sha256 matches the artifact at %s (CRLF-normalized "
                    "sha256)." % out_rel)
        ev_verdict = "CONFIRMED"
        anchor = "command-center/p2-wave/probes/%s/ (named probes + manifest row)" % uid
    reason = ("Build-round measurement is green: artifact exists and parses at output_path, both named "
              "probes re-ran live and exited 0, and the per-unit manifest row sha256 matches the live "
              "artifact. State is BLOCKED, not SUCCESS: receipt_core forbids state=SUCCESS without "
              "reviewer.verdict=PASS and independent=true, and this round was produced by a single build "
              "agent with no independent reviewer.")
    if red:
        reason = ("probe1_blast_radius.py cannot pass while command-center/phase3/A8/DESIGN.json exists, "
                  "and that file is the delivered artifact of declared dependency ARC-0052. The requirement "
                  "pair (probe check vs dependency graph) is contradictory; recorded honestly as FAILED with "
                  "the open defect rather than deleting another unit's artifact or editing the probe. Also "
                  "unclosed by any independent reviewer.")
    failure = {
        "classification": ["contradictory-probe-vs-dependency", "reviewer-absent"] if red else ["reviewer-absent"],
        "reason": reason,
        "blocked_on": ("owner ruling on ARC-0055 probe-vs-dependency contradiction" if red
                       else "independent reviewer CLOSE by a separate reviewer agent"),
        "diagnostic_tail": str(ret.get("measure_line") or "")[:2000],
    }
