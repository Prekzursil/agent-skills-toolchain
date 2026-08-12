"""Lane A3 deliverable-existence probe.

Walks the two program trees + the repo once, indexing every file by basename,
then reports presence for each contracted deliverable name my items own.
Includes a detector control: a KNOWN-PRESENT name and a KNOWN-ABSENT sentinel.
"""
import json
import os

ROOTS = {
    "platform-redesign": r"C:\Users\Prekzursil\.claude\platform-redesign-2026-07-19",
    "harness-restore": r"C:\Users\Prekzursil\.claude\harness-restore-20260806",
    "repo": r"C:\Users\Prekzursil\source\ast-integrate",
}

TARGETS = [
    # detector controls
    "14-NO-REGRESSION-CONTRACT.md",              # KNOWN PRESENT
    "ZZ-A3-SENTINEL-MUST-NOT-EXIST.md",          # KNOWN ABSENT
    "16-GRILL-QUEUE.md",                         # KNOWN PRESENT (R-A27)
    # R-A23
    "15-IMPLEMENTATION-PRECONDITIONS.md",
    # R-A24
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    # R-H02
    "09-RECONCILED-BACKLOG.json",
    "09-RECONCILED-BACKLOG.md",
    "06-PROGRAM-B-SCOPE-DOSSIER.json",
    "06-PROGRAM-B-SCOPE-DOSSIER.md",
    # R-H03
    "10-DEPENDENCY-GRAPH.json",
    "10-DEPENDENCY-GRAPH.md",
    "11-CAPABILITY-PRESERVATION-GRAPH.json",
    # R-H04
    "12-ORDER-PLAN-A-THEN-B.md",
    "13-ORDER-PLAN-B-THEN-A.md",
    "14-OWNER-DECISION-PACKET.md",
    # R-H05
    "EVIDENCE.jsonl",
    "RUNS.jsonl",
    "DEPLOYMENTS.jsonl",
    "EVENTS.jsonl",
    "PRS.jsonl",
    "RESUME.json",
    # R-H06 / R-H07
    "FINAL-INDEPENDENT-AUDIT.md",
    "UNIFIED-PROGRAM-RECEIPT.json",
    "UNRESOLVED-OWNER-ACTIONS.md",
    "PROGRAM-A-RECEIPT.json",
    "PROGRAM-B-RECEIPT.json",
]

PREFIXES = [
    "05-ECO-",          # R-A24 shards
    "C16",              # R-A28
    "H-20",             # R-A29
    "H20",
    "INCREMENT1",       # R-A30
    "POST-WAVE2",       # R-A31
    "PROMPT-2.1",       # R-A32
    "PROMPT-21",
    "DATABRICKS-ENVELOPE",   # R-H08
    "SKILL-RECONCILIATION",  # R-H09
]

DIAGRAM_EXT = {".mmd", ".drawio", ".svg", ".excalidraw", ".puml", ".dot", ".graphml"}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"}


def main():
    out = {"roots": {}, "targets": {}, "prefix_hits": {}, "diagrams": {}, "dir_hits": {}}
    index = {}   # basename -> list of "root:relpath"
    dirnames_idx = {}  # dirname -> list
    for label, root in ROOTS.items():
        n = 0
        if not os.path.isdir(root):
            out["roots"][label] = {"exists": False}
            continue
        diag = []
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for d in dns:
                try:
                    rd = os.path.relpath(os.path.join(dp, d), root)
                except ValueError:
                    rd = os.path.join(dp, d)
                dirnames_idx.setdefault(d, []).append(label + ":" + rd)
            for fn in fns:
                n += 1
                try:
                    rel = os.path.relpath(os.path.join(dp, fn), root)
                except ValueError:
                    rel = os.path.join(dp, fn)
                index.setdefault(fn, []).append(label + ":" + rel)
                ext = os.path.splitext(fn)[1].lower()
                if ext in DIAGRAM_EXT:
                    diag.append(rel)
        out["roots"][label] = {"exists": True, "files": n}
        out["diagrams"][label] = {"count": len(diag), "sample": sorted(diag)[:15]}

    for t in TARGETS:
        out["targets"][t] = index.get(t, [])

    for p in PREFIXES:
        hits = sorted(v for k, vs in index.items() if k.startswith(p) for v in vs)
        dhits = sorted(v for k, vs in dirnames_idx.items() if k.startswith(p) for v in vs)
        out["prefix_hits"][p] = {"files": hits[:25], "n_files": len(hits),
                                 "dirs": dhits[:25], "n_dirs": len(dhits)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
