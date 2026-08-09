"""Deep mechanical scan of candidates 1-32 -- v2, ONE git spawn via cat-file --batch.

v1 spawned one `git cat-file` per tree file and exceeded 600s on Windows
(process-spawn bound, not code bound). This version resolves every blob in a
single batched pipe.

Emits: line counts, phases, agent sites, schemas, models, isolation, stop-rule
and failure-handling token counts, tree enumerations, body hashes for
material-distinctness, and a cross-check of the prior doc's line-count claims.
"""

import hashlib
import json
import re
import subprocess
import sys
from collections import defaultdict

MIRROR = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"
READ_EXT = (".md", ".py", ".mjs", ".js", ".ps1", ".sh", ".json", ".yaml", ".yml", ".txt")
MAX_FILES_PER_TREE = 12
MAX_BYTES_PER_FILE = 200_000

with open("command-center/_wfa1_range_probe.json", encoding="utf-8") as fh:
    probe = json.load(fh)
rows, raw = probe["rows"], probe["raw"]


def git_text(*args):
    r = subprocess.run(
        ["git", "--git-dir", MIRROR, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (r.stdout or ""), r.returncode


def git_bytes(*args, stdin=b""):
    return subprocess.run(
        ["git", "--git-dir", MIRROR, *args], input=stdin, capture_output=True
    )


# ---------- pass 1: enumerate trees / classify each anchor ----------------
plan = []  # (row_index, kind, tree_files or None)
wanted_blobs = {}  # "ref:path" -> None
for i, row in enumerate(rows):
    kind, tree_files = None, None
    if row["fs_exists"] and row["fs_bytes"]:
        kind = "file-live"
    elif row["mirror_exists"]:
        t, _ = git_text("cat-file", "-t", f"{REF}:{row['mirror_path']}")
        t = t.strip()
        kind = f"mirror-{t}"
        if t == "blob":
            wanted_blobs[f"{REF}:{row['mirror_path']}"] = None
        elif t == "tree":
            ls, _ = git_text("ls-tree", "-r", "-l", REF, "--", row["mirror_path"] + "/")
            tree_files = []
            for ln in ls.splitlines():
                if "\t" not in ln:
                    continue
                meta, path = ln.split("\t", 1)
                parts = meta.split()
                tree_files.append(
                    {"path": path, "bytes": int(parts[3]) if parts[3].isdigit() else 0}
                )
            # pick READMEs first, then largest readable files
            readable = [t2 for t2 in tree_files if t2["path"].lower().endswith(READ_EXT)]
            readable.sort(
                key=lambda t2: (0 if "readme" in t2["path"].lower() else 1, -t2["bytes"])
            )
            for t2 in readable[:MAX_FILES_PER_TREE]:
                if t2["bytes"] <= MAX_BYTES_PER_FILE:
                    wanted_blobs[f"{REF}:{t2['path']}"] = None
            t2sel = [t2["path"] for t2 in readable[:MAX_FILES_PER_TREE]]
            row["_selected"] = t2sel
    plan.append((i, kind, tree_files))

print(f"anchors: {len(rows)}  blobs to fetch: {len(wanted_blobs)}")

# ---------- pass 2: ONE batched blob read --------------------------------
keys = list(wanted_blobs)
if keys:
    payload = ("\n".join(keys) + "\n").encode("utf-8")
    proc = git_bytes("cat-file", "--batch", stdin=payload)
    buf = proc.stdout
    pos = 0
    for k in keys:
        nl = buf.find(b"\n", pos)
        if nl < 0:
            break
        header = buf[pos:nl].decode("utf-8", "replace")
        parts = header.split()
        if len(parts) < 3 or parts[-1] == "missing":
            pos = nl + 1
            continue
        size = int(parts[2])
        body = buf[nl + 1 : nl + 1 + size]
        wanted_blobs[k] = body.decode("utf-8", "replace")
        pos = nl + 1 + size + 1  # trailing newline
print("batched read complete; resolved:", sum(1 for v in wanted_blobs.values() if v is not None))

PATTERNS = {
    "phase_sites": r"\bphase\s*\(",
    "agent_sites": r"\bagent\s*\(",
    "parallel_sites": r"\bparallel\s*\(",
    "schema_keys": r"\bschema\s*:",
    "model_opus": r"model\s*:\s*['\"]opus",
    "model_sonnet": r"model\s*:\s*['\"]sonnet",
    "isolation_worktree": r"isolation\s*:\s*['\"]worktree",
    "filter_boolean": r"filter\s*\(\s*Boolean\s*\)",
    "longrun": r"longrun",
    "timeout": r"\btimeout\b",
    "codex_ref": r"\bcodex\b",
    "retry": r"\bretr(?:y|ies|ying)\b",
    "rounds": r"max_?rounds|maxRounds|rounds\s*[:=]",
    "gate_token": r"\bgate\b",
    "unit_complete": r"UNIT-COMPLETE|unit_complete|UNIT_COMPLETE",
    "shadow": r"\bSHADOW\b|shadow[_-]mode",
    "verdict": r"\bverdict\b",
    "unverified": r"UNVERIFIED",
    "band_lexicon": r"almost-certain|roughly-even|Sherman",
    "evidence_anchor": r"EVIDENCE|file:line",
    "stop_rule": r"stop(?:ping)?[_ -]?(?:rule|condition|criteri)",
    "consensus": r"consensus|unanimity|majority|quorum",
    "both_states": r"both-states|both_states|known-broken",
    "mutation": r"mutation|mutant",
    "terminal_state": r"SUCCESS:|FAILED:",
}

results = []
for (i, kind, tree_files), row, rawc in zip(plan, rows, raw):
    out = dict(row)
    out["kind"] = kind
    text = None
    if kind == "file-live":
        with open(row["provenance_claim"], encoding="utf-8", errors="replace") as f:
            text = f.read()
    elif kind == "mirror-blob":
        text = wanted_blobs.get(f"{REF}:{row['mirror_path']}")
    elif kind == "mirror-tree":
        chunks = []
        for p in row.get("_selected", []):
            v = wanted_blobs.get(f"{REF}:{p}")
            if v:
                chunks.append(f"\n===== {p} =====\n{v}")
        text = "\n".join(chunks) if chunks else None
    out["tree_files"] = tree_files
    out["tree_file_count"] = len(tree_files) if tree_files else None
    out["tree_total_bytes"] = sum(t["bytes"] for t in tree_files) if tree_files else None
    out["tree_paths"] = [t["path"] for t in tree_files][:40] if tree_files else None
    if text:
        out["measured_lines"] = text.count("\n") + (0 if text.endswith("\n") else 1)
        out["measured_chars"] = len(text)
        out["body_sha256"] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]
        norm = re.sub(r"\s+", " ", text).strip().lower()
        out["norm_sha256"] = hashlib.sha256(norm.encode()).hexdigest()[:16]
        out["scan"] = {k: len(re.findall(p, text, re.I)) for k, p in PATTERNS.items()}
        out["phase_names"] = re.findall(r"phase\s*\(\s*['\"]([^'\"]{2,70})['\"]", text)[:14]
        m = re.search(r"description\s*:\s*['\"]([^'\"]{5,300})['\"]", text)
        out["description_in_body"] = m.group(1) if m else None
        out["body_head"] = text[:1400]
    else:
        out["measured_lines"] = None
        out["scan"] = None
        out["body_head"] = None
    for f in ("evidence", "mechanisms", "does", "license", "maintenance", "runtime", "origin", "notes"):
        out["prior_" + f] = rawc.get(f, "")
    results.append(out)

print("\n=== LINE-COUNT CROSS-CHECK (prior doc claim vs measured) ===")
mism = 0
for r in results:
    m = re.search(r"(\d+)\s+lines", r["prior_evidence"] or "")
    if m and r["measured_lines"]:
        claimed, measured = int(m.group(1)), r["measured_lines"]
        if claimed != measured:
            mism += 1
            print(f"DIFF {r['id']:<44} claimed={claimed:<6} measured={measured}")
        else:
            print(f"OK   {r['id']:<44} claimed={claimed:<6} measured={measured}")
print(f"-> {mism} mismatches of {sum(1 for r in results if re.search(r'(\\d+) lines', r['prior_evidence'] or '') and r['measured_lines'])} comparable")

print("\n=== MATERIAL DISTINCTNESS ===")
by_body, by_norm = defaultdict(list), defaultdict(list)
for r in results:
    if r.get("body_sha256"):
        by_body[r["body_sha256"]].append(r["id"])
        by_norm[r["norm_sha256"]].append(r["id"])
dupb = {k: v for k, v in by_body.items() if len(v) > 1}
dupn = {k: v for k, v in by_norm.items() if len(v) > 1}
scanned = sum(1 for r in results if r.get("body_sha256"))
print(f"exact body-hash collisions      : {len(dupb)} {dupb}")
print(f"whitespace-normalised collisions: {len(dupn)} {dupn}")
print(f"distinct bodies                 : {len(by_body)} of {scanned} scanned")
print(f"anchors with NO readable body   : {len(results) - scanned}")

print("\n=== TREES ===")
for r in results:
    if r["tree_file_count"]:
        print(f"{r['id']:<28} files={r['tree_file_count']:<4} bytes={r['tree_total_bytes']:<9} read={len(r.get('_selected') or [])}")

with open("command-center/_wfa1_deep_scan.json", "w", encoding="utf-8") as fh:
    json.dump(results, fh, indent=2, ensure_ascii=False)
print("\nwrote command-center/_wfa1_deep_scan.json")
sys.stdout.flush()
