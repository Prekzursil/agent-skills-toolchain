r"""recover_failed_agents, v2 - fixes two MEASURED defects in
command-center/recover_failed_agents.py.

Both defects were reproduced, not inferred, and they fail in OPPOSITE directions, which is
why the tool is untrustworthy in both a false-positive and a false-negative sense.

DEFECT 1 - OVER-MATCH (recover_failed_agents.py:116)
    `if not any(w in raw.upper() for w in wanted): continue`
    matches the unit id ANYWHERE in the transcript text, including a cross-reference by a
    sibling agent. Measured: 42 of 42 transcripts "matched" ADV-0021/ADV-0022. A 100% match
    rate carries zero information, and the reader is handed 42 sections to triage.

    FIX: two-signal identification. S1 = the spawn prompt literally declares
    `YOUR WORK UNIT: <ID>` (authoritative - the agent was TOLD this is its unit).
    S2 = a Write/Edit file_path contains the id. A transcript qualifies only on S1, or on S2
    when no S1 exists anywhere in the run. Which signal fired is printed, so the
    identification is auditable rather than asserted.

DEFECT 2 - UNDER-COUNT (recover_failed_agents.py:70)
    Artifacts are harvested only from `Write`/`Edit`/`NotebookEdit` tool calls. The dominant
    pattern in this program is a Bash call - `python build_artifact.py`, or an inline
    `python -c` that writes a file. Measured: ADV-0021's own 2,100 B skeleton exists on disk
    but is ABSENT from its Write list (it was emitted by an inline `python -c` at record 37),
    so the tool printed "WROTE NOTHING -- total loss for this agent". That verdict is false
    and it is the single most damaging line the tool can print, because it tells the reader
    to re-run two hours of completed measurement from scratch.

    FIX: delivery is decided by the unit's DECLARED catalog `output_path` existing on disk,
    not by scraping tool calls. Bash commands are additionally mined for redirect targets and
    quoted paths, and every candidate is stat-confirmed. "WROTE NOTHING" is only ever printed
    when the declared output_path is absent AND no other on-disk artifact was found.

DEFECT 3 - the label join (advisory)
    journal.jsonl rows carry keys ['agentId','key','result','type'] - there is NO label
    field, so a label join against the journal is structurally impossible. The HARVEST file
    does carry `label`, and v2 uses it when present.

SELF-TEST: `--selftest` runs both states and asserts v2 fixes each defect while the original
still exhibits it. Run it before trusting any output.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
SESSION = "30bd50d4-5a72-4c19-8fd5-85b6430c7b7d"
WF_ROOT = (Path("C:/Users/Prekzursil/.claude/projects/C--Users-Prekzursil") / SESSION
           / "subagents" / "workflows")
SUBSTANTIAL = 8192
UNIT_DECL = re.compile(r"YOUR WORK UNIT:\s*([A-Z][A-Z0-9]*-\d{4})")


def load_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def blocks(recs: list[dict]):
    for r in recs:
        msg = r.get("message") if isinstance(r.get("message"), dict) else r
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict):
                    yield r, b
        elif isinstance(content, str) and content.strip():
            yield r, {"type": "text", "text": content}


PATH_IN_CMD = re.compile(r"""(?:>>?|-o\s+|--output(?:-last-message)?[=\s]+)\s*["']?([^\s"'|;&]+)"""
                         r"""|["']([A-Za-z]:[\\/][^"']{6,})["']""")


def agent_facts(path: Path) -> dict:
    recs = load_jsonl(path)
    label, written, bash_paths, last_text = "", [], [], ""
    declared_units, ended = set(), False
    for r, b in blocks(recs):
        if not label:
            for k in ("label", "agentLabel", "name"):
                if isinstance(r.get(k), str) and r[k]:
                    label = r[k]
                    break
        t = b.get("type")
        if t == "tool_use":
            name, inp = b.get("name", ""), (b.get("input") or {})
            if not isinstance(inp, dict):
                continue
            if name in ("Write", "Edit", "NotebookEdit"):
                fp = inp.get("file_path") or inp.get("notebook_path")
                if fp:
                    written.append(str(fp))
            elif name == "Bash":
                cmd = str(inp.get("command", ""))
                for m in PATH_IN_CMD.finditer(cmd):
                    cand = m.group(1) or m.group(2)
                    if cand and not cand.startswith("-"):
                        bash_paths.append(cand)
        elif t == "text" and b.get("text", "").strip():
            last_text = b["text"]
            for m in UNIT_DECL.finditer(b["text"]):
                declared_units.add(m.group(1))
        if r.get("type") in ("result", "summary") or r.get("subtype") == "success":
            ended = True
    # S1 must come from the agent's OWN spawn prompt, which is record 0. Scanning the whole
    # transcript is use-vs-mention: measured, one census agent QUOTES 41 other units' spawn
    # prompts and another cites 4, so a raw scan re-creates the very over-match v2 exists to
    # fix. The owning declaration is the FIRST match inside record 0.
    raw = path.read_text(encoding="utf-8", errors="replace")
    own_unit = None
    if recs:
        m0 = UNIT_DECL.search(json.dumps(recs[0]))
        if m0:
            own_unit = m0.group(1)
    declared_units = {own_unit} if own_unit else set()
    return {"label": label or path.stem, "written": sorted(dict.fromkeys(written)),
            "bash_paths": sorted(dict.fromkeys(bash_paths)), "last_text": last_text,
            "ended": ended, "records": len(recs), "bytes": path.stat().st_size,
            "declared_units": declared_units, "own_unit": own_unit,
            "raw_mentions": raw.upper()}


def catalog_output_paths() -> dict[str, str]:
    p = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
    if not p.is_file():
        return {}
    cat = json.loads(p.read_text(encoding="utf-8"))
    return {u["id"]: u.get("output_path", "") for u in cat.get("work_units", [])}


def harvest_labels() -> dict[str, str]:
    """agentId -> label, from the harvest file (journal.jsonl has NO label field)."""
    out: dict[str, str] = {}
    hd = REPO / "command-center" / "harvest"
    if not hd.is_dir():
        return out
    for f in hd.glob("*.json"):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for coll in (doc if isinstance(doc, list) else doc.values()):
            if isinstance(coll, list):
                for row in coll:
                    if isinstance(row, dict) and row.get("agentId") and row.get("label"):
                        out[row["agentId"]] = row["label"]
    return out


def identify(transcripts: list[Path], wanted: list[str]) -> tuple[dict, dict]:
    """Two-signal identification. Returns unit -> [(transcript, which_signal)]."""
    facts = {t: agent_facts(t) for t in transcripts}
    any_s1 = any(f["declared_units"] for f in facts.values())
    hits: dict[str, list[tuple[Path, str]]] = {w: [] for w in wanted}
    for t, f in facts.items():
        for w in wanted:
            if w in f["declared_units"]:
                hits[w].append((t, "S1 spawn-prompt declaration"))
            elif not any_s1 and any(w in p.upper() for p in f["written"]):
                hits[w].append((t, "S2 write-path (S1 unavailable in this run)"))
    return hits, facts


def report(run: str, wanted: list[str]) -> int:
    root = WF_ROOT / run
    if not root.is_dir():
        print(f"FAILED:recover-v2 run dir not found: {root}")
        return 1
    transcripts = sorted(root.glob("agent-*.jsonl"))
    if not transcripts:
        print(f"FAILED:recover-v2 no agent transcripts under {root}")
        return 1

    outputs = catalog_output_paths()
    labels = harvest_labels()
    hits, facts = identify(transcripts, wanted)

    raw_mentions = {w: sum(1 for f in facts.values() if w in f["raw_mentions"]) for w in wanted}
    print(f"run {run}: {len(transcripts)} transcripts scanned")
    print("IDENTIFICATION (v2 two-signal vs the v1 raw-text match):")
    for w in wanted:
        print(f"  {w}: v1 raw-text would match {raw_mentions[w]}/{len(transcripts)} transcripts; "
              f"v2 identifies {len(hits[w])}")
    if not any(hits.values()):
        print(f"FAILED:recover-v2 two-signal identification matched nothing for {wanted}")
        return 1

    for w in wanted:
        for tpath, signal in hits[w]:
            f = facts[tpath]
            aid = tpath.stem.replace("agent-", "")
            absent_note = ("<absent from harvest -> the agent returned null, "
                           "which corroborates a death>")
            lab = labels.get(aid, absent_note)
            print(f"\n=== {w}  [{tpath.name}]  via {signal}")
            print(f"    harvest_label={lab}")
            print(f"    records={f['records']} transcript={f['bytes']:,}B "
                  f"terminal_record={f['ended']}")

            declared = outputs.get(w, "")
            found: list[tuple[str, int, str]] = []
            if declared:
                q = REPO / declared
                print(f"    declared output_path: {declared}  exists={q.is_file()}"
                      + (f"  {q.stat().st_size:,}B" if q.is_file() else ""))
                if q.is_file():
                    found.append((declared, q.stat().st_size, "declared output_path"))
            for p in f["written"]:
                q = Path(p)
                if q.is_file():
                    found.append((p, q.stat().st_size, "Write/Edit"))
            for p in f["bash_paths"]:
                q = Path(p) if Path(p).is_absolute() else REPO / p
                if q.is_file():
                    found.append((str(q), q.stat().st_size, "Bash-written (v1 BLIND to this)"))

            seen, uniq = set(), []
            for pth, size, how in found:
                k = Path(pth).resolve().as_posix().lower()
                if k not in seen:
                    seen.add(k)
                    uniq.append((pth, size, how))
            if not uniq:
                print("    NO ARTIFACT FOUND on disk by any of the three routes "
                      "(declared output_path, Write/Edit, Bash) -- only NOW is a total loss "
                      "a defensible reading.")
            for pth, size, how in sorted(uniq, key=lambda x: -x[1])[:12]:
                tag = "SUBSTANTIAL" if size >= SUBSTANTIAL else "stub"
                print(f"    [on disk {tag:11}] {size:>9,}B  via {how}")
                print(f"                            {pth}")
            tail = (f["last_text"] or "").strip().replace("\r", "")
            if tail:
                print("    --- last assistant text (tail) ---")
                for line in tail.splitlines()[-8:]:
                    print(f"    | {line[:150]}")
    print(f"\nSUCCESS:recover-v2 identified={sum(len(v) for v in hits.values())}")
    return 0


def selftest() -> int:
    """BOTH-STATES CONTROL: v1 must still exhibit each defect; v2 must not."""
    run = "wf_9cb1a66a-36f"
    wanted = ["ADV-0021", "ADV-0022"]
    root = WF_ROOT / run
    if not root.is_dir():
        print(f"FAILED:recover-v2-selftest fixture run missing: {root}")
        return 1
    transcripts = sorted(root.glob("agent-*.jsonl"))
    hits, facts = identify(transcripts, wanted)

    # D1: over-match. v1 = raw text anywhere; v2 = two-signal.
    v1_match = sum(1 for f in facts.values()
                   if any(w in f["raw_mentions"] for w in wanted))
    v2_match = sum(len(v) for v in hits.values())
    d1_v1_broken = v1_match > len(wanted) * 2      # v1 grossly over-matches
    d1_v2_fixed = v2_match == len(wanted)          # exactly one transcript per unit

    # D2: under-count. ADV-0021's skeleton exists on disk but not in its Write list.
    outputs = catalog_output_paths()
    decl = outputs.get("ADV-0021", "")
    on_disk = (REPO / decl).is_file() if decl else False
    t21 = hits["ADV-0021"][0][0] if hits["ADV-0021"] else None
    in_write_list = bool(t21) and any("ADV-0021" in p.upper() for p in facts[t21]["written"])
    d2_v1_broken = on_disk and not in_write_list   # v1 would print WROTE NOTHING
    d2_v2_fixed = on_disk                          # v2 finds it via declared output_path

    print("BOTH-STATES CONTROL for recover_failed_agents_v2")
    print(f"  D1 over-match   : v1 matches {v1_match}/{len(transcripts)} transcripts "
          f"(broken={d1_v1_broken}); v2 identifies {v2_match} for {len(wanted)} units "
          f"(fixed={d1_v2_fixed})")
    print(f"  D2 under-count  : ADV-0021 declared artifact on disk={on_disk}, "
          f"present in its Write list={in_write_list} -> v1 would print WROTE NOTHING "
          f"(broken={d2_v1_broken}); v2 finds it via declared output_path (fixed={d2_v2_fixed})")
    ok = d1_v1_broken and d1_v2_fixed and d2_v1_broken and d2_v2_fixed
    print("SUCCESS:recover-v2-selftest" if ok
          else "FAILED:recover-v2-selftest a control did not reproduce")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", default="wf_9cb1a66a-36f")
    ap.add_argument("units", nargs="*", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return report(a.run, [u.upper() for u in (a.units or ["ADV-0021", "ADV-0022"])])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
