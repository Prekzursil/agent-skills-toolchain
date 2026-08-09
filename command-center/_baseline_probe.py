"""Baseline enumerator + detector control for Prompt Two Phase 0.

Read-only. Writes nothing outside a system temp scratch dir (used ONLY for the
detector-control 'fires on known-present sentinel' test, then removed).
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile

SENTINEL = "__CONTROL-SHOULD-NOT-EXIST__.md"

HOME = os.path.expanduser("~")
REPO = r"C:\Users\Prekzursil\source\ast-integrate"

PAIRS = [
    ("skills", os.path.join(HOME, ".agents", "skills"), os.path.join(REPO, "skills")),
    ("hooks", os.path.join(HOME, ".claude", "hooks"), os.path.join(REPO, "hooks")),
    ("rules", os.path.join(HOME, ".claude", "rules"), os.path.join(REPO, "rules")),
]

# Directory names excluded from the harness-tree walk: caches / vendored VCS.
EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache", "node_modules"}


RESERVED = {
    "NUL",
    "CON",
    "AUX",
    "PRN",
    *("COM%d" % i for i in range(1, 10)),
    *("LPT%d" % i for i in range(1, 10)),
}
RESERVED_HITS = []


def enumerate_tree(root):
    r"""Return {relpath_with_forward_slashes: size_bytes}. Empty dict if root absent.

    NOTE r-string: relpath is computed by PREFIX STRIPPING, not os.path.relpath: a file literally
    named NUL/CON/AUX/... makes os.path.relpath raise
    ``ValueError: path is on mount '\\\\.\\NUL'`` because Windows resolves the name
    to a device. Sizing such a file also needs the \\?\ extended-length prefix.
    """
    out = {}
    if not os.path.isdir(root):
        return out
    base = os.path.abspath(root).rstrip("\\/")
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            # relpath from the DIRECTORY (a normal path) + the filename. Never
            # abspath() the full path: Windows collapses a reserved stem such as
            # NUL to the device \\.\NUL, which yields an empty/garbage relpath.
            reldir = (
                os.path.abspath(dirpath)[len(base) :].strip("\\/").replace("\\", "/")
            )
            rel = ("%s/%s" % (reldir, fn)) if reldir else fn
            stem = fn.split(".")[0].upper()
            if stem in RESERVED:
                RESERVED_HITS.append({"root": base.replace("\\", "/"), "rel": rel})
                try:
                    out[rel] = os.path.getsize("\\\\?\\" + os.path.abspath(full))
                except OSError as exc:
                    out[rel] = "ERROR:%s" % exc
                continue
            try:
                out[rel] = os.path.getsize(full)
            except OSError as exc:
                out[rel] = "ERROR:%s" % exc
    return out


def safe_path(path):
    """Extended-length form, so a reserved device name is read as a FILE."""
    ap = os.path.abspath(path)
    stem = os.path.basename(ap).split(".")[0].upper()
    return ("\\\\?\\" + ap) if stem in RESERVED else ap


def sha256(path):
    h = hashlib.sha256()
    with open(safe_path(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    result = {"detector_control": {}, "trees": {}, "live_vs_repo": {}}

    # ---------------- DETECTOR CONTROL ----------------
    dc = result["detector_control"]

    # (a) known-PRESENT: a file we independently confirmed exists via `ls -la`.
    hooks_live = os.path.join(HOME, ".claude", "hooks")
    hooks_map = enumerate_tree(hooks_live)
    known_present_rel = "_dispatch/manifest.json"
    dc["known_present_probe"] = "enumerate_tree(%s) must contain %r" % (
        hooks_live,
        known_present_rel,
    )
    dc["known_present_found"] = known_present_rel in hooks_map
    dc["known_present_size"] = hooks_map.get(known_present_rel)

    # (b) known-ABSENT sentinel must not appear in ANY of the three live trees
    #     nor in any of the three repo trees.
    absent_hits = []
    for label, live, repo in PAIRS:
        for scope, root in (("live", live), ("repo", repo)):
            for rel in enumerate_tree(root):
                if os.path.basename(rel) == SENTINEL:
                    absent_hits.append("%s/%s:%s" % (label, scope, rel))
    dc["known_absent_sentinel"] = SENTINEL
    dc["known_absent_hits"] = absent_hits
    dc["known_absent_ok"] = len(absent_hits) == 0

    # (c) BOTH-STATES test: the same enumerator must FIRE when the sentinel IS
    #     present. Proves (b)'s silence is meaningful, not a name-blind detector.
    scratch = tempfile.mkdtemp(prefix="baseline_ctrl_")
    try:
        nested = os.path.join(scratch, "sub", "deep")
        os.makedirs(nested)
        with open(os.path.join(nested, SENTINEL), "w", encoding="utf-8") as fh:
            fh.write("control\n")
        ctrl_map = enumerate_tree(scratch)
        dc["both_states_probe"] = (
            "same enumerate_tree() over a temp dir seeded with the sentinel"
        )
        dc["both_states_fired"] = "sub/deep/%s" % SENTINEL in ctrl_map
        dc["both_states_seen"] = sorted(ctrl_map)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    dc["verdict"] = (
        "PASS"
        if (
            dc["known_present_found"]
            and dc["known_absent_ok"]
            and dc["both_states_fired"]
        )
        else "FAIL"
    )

    # ---------------- TREE COUNTS + DIFF ----------------
    for label, live, repo in PAIRS:
        live_map = enumerate_tree(live)
        repo_map = enumerate_tree(repo)
        result["trees"][label] = {
            "live_path": live.replace("\\", "/"),
            "live_exists": os.path.isdir(live),
            "live_file_count": len(live_map),
            "live_total_bytes": sum(v for v in live_map.values() if isinstance(v, int)),
            "repo_path": repo.replace("\\", "/"),
            "repo_exists": os.path.isdir(repo),
            "repo_file_count": len(repo_map),
            "repo_total_bytes": sum(v for v in repo_map.values() if isinstance(v, int)),
        }

        live_only = sorted(set(live_map) - set(repo_map))
        repo_only = sorted(set(repo_map) - set(live_map))
        both = sorted(set(live_map) & set(repo_map))

        differing = []
        identical = 0
        for rel in both:
            lp = os.path.join(live, rel.replace("/", os.sep))
            rp = os.path.join(repo, rel.replace("/", os.sep))
            try:
                lh, rh = sha256(lp), sha256(rp)
            except OSError as exc:
                differing.append({"path": rel, "error": str(exc)})
                continue
            if lh == rh:
                identical += 1
            else:
                # Distinguish EOL-only drift from real content drift.
                with open(safe_path(lp), "rb") as fh:
                    lb = fh.read()
                with open(safe_path(rp), "rb") as fh:
                    rb = fh.read()
                eol_only = lb.replace(b"\r\n", b"\n") == rb.replace(b"\r\n", b"\n")
                differing.append(
                    {
                        "path": rel,
                        "live_bytes": live_map[rel],
                        "repo_bytes": repo_map[rel],
                        "eol_only": eol_only,
                    }
                )
        result["live_vs_repo"][label] = {
            "identical_count": identical,
            "differing_count": len(differing),
            "differing_content_count": sum(
                1 for d in differing if not d.get("eol_only")
            ),
            "differing_eol_only_count": sum(1 for d in differing if d.get("eol_only")),
            "differing": differing,
            "live_only_count": len(live_only),
            "live_only": live_only,
            "repo_only_count": len(repo_only),
            "repo_only": repo_only,
        }

    # ---------------- HOOK DISPATCH MANIFEST ----------------
    mpath = os.path.join(HOME, ".claude", "hooks", "_dispatch", "manifest.json")
    man = {"path": mpath.replace("\\", "/")}
    try:
        with open(mpath, encoding="utf-8") as fh:
            data = json.load(fh)
        man["top_level_keys"] = sorted(data.keys())
        by_event = {}
        total = 0
        # Structure discovery: count leaf registration entries per event key.
        for k, v in data.items():
            if isinstance(v, list):
                by_event[k] = len(v)
                total += len(v)
            elif isinstance(v, dict):
                n = sum(len(x) if isinstance(x, list) else 1 for x in v.values())
                by_event[k] = n
                total += n
        man["by_event"] = by_event
        man["registration_count"] = total
        man["raw_structure_sample"] = json.dumps(data)[:400]
    except Exception as exc:  # noqa: BLE001
        man["error"] = "%s: %s" % (type(exc).__name__, exc)
        man["registration_count"] = "NOT-CHECKED"
    result["hook_dispatch_manifest"] = man
    seen = set()
    uniq = []
    for h in RESERVED_HITS:
        k = (h["root"], h["rel"])
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    result["reserved_device_name_files"] = uniq
    # Characterise the live-only surface by top-level skill directory.
    from collections import Counter

    for lbl in result["live_vs_repo"]:
        c = Counter(p.split("/")[0] for p in result["live_vs_repo"][lbl]["live_only"])
        result["live_vs_repo"][lbl]["live_only_top_dirs"] = c.most_common(15)
        c2 = Counter(p.split("/")[0] for p in result["live_vs_repo"][lbl]["repo_only"])
        result["live_vs_repo"][lbl]["repo_only_top_dirs"] = c2.most_common(15)

    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
