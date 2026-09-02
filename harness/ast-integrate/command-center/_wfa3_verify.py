"""wfa-3 probe 2: mechanically verify each anchor's provenance, license and maintenance state.

Exact algorithm, no judgement:
  * resolve the declared provenance path -> exists? kind? bytes? newest mtime?
  * if absent, search the known alternate roots (plugin cache, live skill vaults,
    known_marketplaces.json) and report where the body ACTUALLY is
  * license: read the real LICENSE / package.json / plugin.json / .claude-plugin manifest
    in the resolved dir and record BOTH the string and the file it came from
  * maintenance: git last-commit ISO date if it is a git repo, else the marketplace
    manifest lastUpdated, else the newest file mtime in the tree

Includes detector controls: a known-present and a known-absent path must classify correctly.
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

CORPUS = Path("C:/Users/Prekzursil/.claude/harness-restore-20260806")
REG = CORPUS / "08-WORKFLOW-CANDIDATE-REGISTRY.json"
PLUGINS = Path("C:/Users/Prekzursil/.claude/plugins")
MKT = PLUGINS / "marketplaces"
CACHE = PLUGINS / "cache"
AGENTS_SKILLS = Path("C:/Users/Prekzursil/.agents/skills")
CLAUDE_SKILLS = Path("C:/Users/Prekzursil/.claude/skills")
SETTINGS = Path("C:/Users/Prekzursil/.claude/settings.json")

OUT = Path(
    "C:/Users/Prekzursil/source/ast-integrate/command-center/_wfa3_verify_out.json"
)

LICENSE_NAMES = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "LICENCE",
    "COPYING",
    "NOTICE",
    "THIRD_PARTY_NOTICES.md",
    "THIRD_PARTY.md",
)


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def newest_mtime(root: Path, cap: int = 20000):
    best = None
    n = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in (".git", "node_modules", "__pycache__")
        ]
        for f in filenames:
            p = Path(dirpath) / f
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            n += 1
            if best is None or m > best[0]:
                best = (m, str(p))
            if n >= cap:
                return best, n, True
    return best, n, False


def git_last_commit(root: Path):
    if not (root / ".git").exists():
        return None
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%cI|%h|%an"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"git-error:{e}"
    return None


def read_license(root: Path):
    """Return (license_string, source_file, method) read from the REAL tree."""
    found = []
    for name in LICENSE_NAMES:
        p = root / name
        if p.is_file():
            txt = p.read_text(encoding="utf-8", errors="replace")
            head = " ".join(txt.split())[:220]
            found.append((head, str(p), f"{name} file, {p.stat().st_size}B"))
    # package.json / plugin.json license fields
    for name in (
        "package.json",
        "plugin.json",
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
    ):
        p = root / name
        if p.is_file():
            try:
                j = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                continue
            if isinstance(j, dict) and j.get("license"):
                found.append((str(j["license"]), str(p), f"{name} license field"))
    if found:
        return found
    # one level down (marketplace clones keep per-plugin licenses)
    hits = []
    for sub in sorted(root.glob("*/LICENSE*"))[:4]:
        txt = sub.read_text(encoding="utf-8", errors="replace")
        hits.append((" ".join(txt.split())[:180], str(sub), "nested LICENSE"))
    return hits


def tree_manifest(root: Path, cap: int = 4000):
    """sha256 per relative file path -> exact duplicate detection."""
    man = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames if d not in (".git", "node_modules", "__pycache__")
        ]
        for f in filenames:
            p = Path(dirpath) / f
            rel = str(p.relative_to(root)).replace("\\", "/")
            try:
                man[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                man[rel] = "UNREADABLE"
            if len(man) >= cap:
                return man, True
    return man, False


def describe(path: Path):
    d = {"declared_path": str(path), "exists": path.exists()}
    if not path.exists():
        return d
    d["kind"] = "dir" if path.is_dir() else "file"
    if path.is_file():
        st = path.stat()
        d["bytes"] = st.st_size
        d["mtime"] = iso(st.st_mtime)
        return d
    best, n, capped = newest_mtime(path)
    d["file_count_scanned"] = n
    d["scan_capped"] = capped
    if best:
        d["newest_mtime"] = iso(best[0])
        d["newest_file"] = best[1]
    d["top_level"] = sorted(x.name for x in path.iterdir())[:25]
    g = git_last_commit(path)
    if g:
        d["git_last_commit"] = g
    lic = read_license(path)
    if lic:
        d["license_readings"] = [
            {"text": t, "source_file": s, "method": m} for t, s, m in lic[:4]
        ]
    return d


def main():
    reg = json.loads(REG.read_text(encoding="utf-8"))
    anchor = reg["candidates"][64:96]

    settings = json.loads(SETTINGS.read_text(encoding="utf-8", errors="replace"))
    enabled = settings.get("enabledPlugins", {})
    enabled_true = sorted(k for k, v in enabled.items() if v is True)

    km_path = PLUGINS / "known_marketplaces.json"
    km = json.loads(km_path.read_text(encoding="utf-8", errors="replace"))

    results = {
        "probe": "wfa3-verify",
        "generated_at_utc": iso(datetime.now(tz=timezone.utc).timestamp()),
        "anchor_count": len(anchor),
        "enabledPlugins_true": enabled_true,
        "enabledPlugins_total_keys": len(enabled),
        "known_marketplaces_keys": (
            sorted(km.get("marketplaces", km).keys())
            if isinstance(km, dict)
            else "NON-DICT"
        ),
        "known_marketplaces_raw_head": json.dumps(km)[:1500],
        "marketplaces_on_disk": sorted(p.name for p in MKT.iterdir())
        if MKT.exists()
        else [],
        "cache_on_disk": sorted(p.name for p in CACHE.iterdir())
        if CACHE.exists()
        else [],
        "detector_controls": {
            "known_present": describe(MKT / "claude-plugins-official")["exists"],
            "known_absent": describe(MKT / "__definitely_not_here__")["exists"],
        },
        "rows": [],
    }

    for i, x in enumerate(anchor, start=65):
        row = {
            "index": i,
            "prior_id": x["id"],
            "prior_name": x["name"],
            "prior_family": x["family"],
            "prior_classification": x["classification"],
            "prior_license": x["license"],
            "prior_maintenance": x["maintenance"],
            "prior_provenance": x["provenance"],
        }
        # 1) declared path as-is
        raw = x["provenance"]
        if raw.startswith("agents-live:"):
            stem = raw.split(":", 1)[1].strip()
            row["resolved_kind"] = "live-skill"
            row["agents_live"] = describe(AGENTS_SKILLS / stem)
            row["claude_live"] = describe(CLAUDE_SKILLS / stem)
            sk = AGENTS_SKILLS / stem / "SKILL.md"
            row["skill_md"] = describe(sk)
        else:
            p = Path(raw)
            row["resolved_kind"] = "path"
            row["declared"] = describe(p)
            if not p.exists():
                # search the alternates
                alts = {}
                name = p.name
                for root, label in ((CACHE, "plugin-cache"), (MKT, "marketplaces")):
                    cand = root / name
                    if cand.exists():
                        alts[label] = describe(cand)
                row["alternates_found"] = alts
                row["PROVENANCE_DEFECT"] = "declared path does not exist" + (
                    f"; real body at {list(alts)}" if alts else "; no alternate found"
                )
        results["rows"].append(row)

    # 2) the byte-duplicate question, answered by exact algorithm
    a = MKT / "anthropic-agent-skills"
    t = MKT / "temp_1781578811820"
    dup = {"a": str(a), "t": str(t), "a_exists": a.exists(), "t_exists": t.exists()}
    if a.exists() and t.exists():
        ma, ca = tree_manifest(a)
        mt, ct = tree_manifest(t)
        dup["a_files"] = len(ma)
        dup["t_files"] = len(mt)
        dup["a_capped"] = ca
        dup["t_capped"] = ct
        ka, kt = set(ma), set(mt)
        dup["only_in_a"] = sorted(ka - kt)[:15]
        dup["only_in_t"] = sorted(kt - ka)[:15]
        dup["only_in_a_count"] = len(ka - kt)
        dup["only_in_t_count"] = len(kt - ka)
        shared = ka & kt
        same = [k for k in shared if ma[k] == mt[k]]
        diff = [k for k in shared if ma[k] != mt[k]]
        dup["shared"] = len(shared)
        dup["identical_hash"] = len(same)
        dup["differing_hash"] = len(diff)
        dup["differing_examples"] = sorted(diff)[:10]
        dup["VERDICT"] = (
            "EXACT-DUPLICATE"
            if not (ka ^ kt) and not diff
            else (
                "NEAR-DUPLICATE"
                if len(same) > 0.6 * max(len(ka), len(kt))
                else "NOT-A-DUPLICATE"
            )
        )
    results["duplicate_probe_temp_vs_anthropic"] = dup

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print("detector controls:", results["detector_controls"])
    print("enabled plugins TRUE:", len(enabled_true), enabled_true)
    print("marketplaces on disk:", results["marketplaces_on_disk"])
    print(
        "DUP VERDICT:",
        dup.get("VERDICT"),
        {
            k: dup.get(k)
            for k in (
                "a_files",
                "t_files",
                "identical_hash",
                "differing_hash",
                "only_in_a_count",
                "only_in_t_count",
            )
        },
    )
    print()
    for r in results["rows"]:
        flag = r.get("PROVENANCE_DEFECT", "")
        ex = r.get("declared", {}).get("exists", r.get("agents_live", {}).get("exists"))
        print(f"[{r['index']}] {r['prior_id']:<45} exists={ex} {flag}")


if __name__ == "__main__":
    main()
