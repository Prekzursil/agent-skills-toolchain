#!/usr/bin/env python3
"""AUD-0025 Probe 1: constraint-syntax classification per declaration.

Classes (catalog): exact | compatible | caret | tilde | wildcard | none
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-constraint-census.json"
OUT_RAW = PROBE / "probe1-constraint-census.raw.txt"

SKIP_DIR_NAMES = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "dist", "build", ".tox", ".mypy_cache", ".ruff_cache", "coverage",
}
OTHER_PROBE_PREFIX = "command-center/p2-wave/probes/"
FLOATING = {"compatible", "caret", "tilde", "wildcard", "none"}
NPM_EXACT = re.compile(r"^v?\d+\.\d+\.\d+([+-][0-9A-Za-z.-]+)?$")
SHA_FULL = re.compile(r"^[0-9a-fA-F]{40}$")
SHA_SHORTISH = re.compile(r"^[0-9a-fA-F]{7,39}$")


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def classify_npm(constraint: str) -> str:
    c = (constraint or "").strip()
    if c == "" or c in {"*", "x", "X"}:
        return "wildcard"
    low = c.lower()
    if low in {"latest", "next", "canary", "unstable"}:
        return "wildcard"
    if c.startswith("^"):
        return "caret"
    if c.startswith("~"):
        return "tilde"
    if any(ch in c for ch in ("*", "x", "X")) and not c.startswith("git"):
        return "wildcard"
    if c.startswith((">=", "<=", ">", "<")):
        return "compatible"
    if c.startswith("=") and NPM_EXACT.match(c[1:].strip()):
        return "exact"
    if "||" in c or " - " in c or "," in c:
        return "compatible"
    if c.startswith(("workspace:", "file:", "link:", "portal:", "git+", "github:", "http:", "https:", "npm:")):
        return "exact"
    if NPM_EXACT.match(c):
        return "exact"
    if re.match(r"^v?\d+(\.\d+)?$", c):
        return "compatible"
    return "compatible"


def classify_pip(spec: str) -> str:
    s = (spec or "").strip()
    if not s:
        return "none"
    if ";" in s:
        s = s.split(";", 1)[0].strip()
    if "[" in s:
        name, rest = s.split("[", 1)
        if "]" in rest:
            s = name + rest.split("]", 1)[1]
        else:
            s = name
    s = s.strip()
    if s.startswith(("git+", "http://", "https://", "file:", "svn+", "hg+", "bzr+")) or "://" in s:
        return "exact"
    if re.match(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$", s):
        return "none"
    if "==" in s:
        m = re.search(r"==\s*([^\s,;]+)", s)
        if not m:
            return "none"
        ver = m.group(1)
        if any(ch in ver for ch in "*xX"):
            return "wildcard"
        return "exact"
    if "~=" in s:
        return "compatible"
    if s.startswith("^") or re.search(r"(^|[, ])\^", s):
        return "caret"
    if re.search(r"(^|[, ])~(?!=)", s):
        return "tilde"
    if any(op in s for op in (">=", "<=", ">", "<", "!=")):
        return "compatible"
    if "*" in s:
        return "wildcard"
    return "compatible"


def classify_action_ref(ref: str) -> str:
    r = (ref or "").strip()
    if not r:
        return "none"
    if SHA_FULL.match(r):
        return "exact"
    if r.startswith("sha256:"):
        return "exact"
    if r in {"main", "master", "head", "latest", "dev", "devel"}:
        return "wildcard"
    if re.match(r"^v?\d+(\.\d+){0,2}$", r):
        return "compatible"
    if SHA_SHORTISH.match(r):
        return "compatible"
    return "compatible"


def classify_docker_tag(tag: str | None, digest: str | None) -> str:
    if digest:
        return "exact"
    if tag is None or tag == "":
        return "none"
    if tag.lower() == "latest":
        return "wildcard"
    return "compatible"


def add_row(rows, *, path, ecosystem, name, constraint, classification, dep_class, planted=False):
    rows.append({
        "path": path,
        "ecosystem": ecosystem,
        "name": name,
        "constraint": constraint,
        "classification": classification,
        "dep_class": dep_class,
        "floating": classification in FLOATING,
        "planted_negative_control": planted,
        "in_other_unit_probe_scratch": (
            path.startswith(OTHER_PROBE_PREFIX)
            and not path.startswith("command-center/p2-wave/probes/AUD-0025/")
        ),
    })


def scan_package_json(path: Path, rows: list) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    planted = "AUD-0025/fixtures/planted-unpinned" in rel(path)
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        deps = data.get(key)
        if not isinstance(deps, dict):
            continue
        for name, ver in deps.items():
            constraint = "" if ver is None else str(ver)
            add_row(rows, path=rel(path), ecosystem="npm", name=str(name), constraint=constraint,
                    classification=classify_npm(constraint), dep_class=key, planted=planted)


def scan_requirements(path: Path, rows: list) -> None:
    planted = "AUD-0025/fixtures/planted-unpinned" in rel(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or raw.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._+-]*)(.*)$", raw)
        if not m:
            continue
        name, rest = m.group(1), m.group(2).strip()
        add_row(rows, path=rel(path), ecosystem="pip", name=name,
                constraint=rest if rest else "(none)", classification=classify_pip(raw),
                dep_class="requirements", planted=planted)


def scan_pyproject(path: Path, rows: list) -> None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    planted = "AUD-0025/fixtures/planted-unpinned" in rel(path)
    project = data.get("project") or {}
    if not isinstance(project, dict):
        return
    req_py = project.get("requires-python")
    if isinstance(req_py, str) and req_py.strip():
        cls = "exact" if re.match(r"^==\s*\d", req_py.strip()) else "compatible"
        if re.match(r"^\d", req_py.strip()) and not any(op in req_py for op in "><=!,~"):
            cls = "exact"
        add_row(rows, path=rel(path), ecosystem="pip", name="requires-python", constraint=req_py,
                classification=cls, dep_class="requires-python", planted=planted)
    deps = project.get("dependencies") or []
    if isinstance(deps, list):
        for item in deps:
            if not isinstance(item, str):
                continue
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._+-]*)", item.strip())
            name = m.group(1) if m else item
            add_row(rows, path=rel(path), ecosystem="pip", name=name, constraint=item,
                    classification=classify_pip(item), dep_class="project.dependencies", planted=planted)
    opt = project.get("optional-dependencies") or {}
    if isinstance(opt, dict):
        for extra, items in opt.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, str):
                    continue
                m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._+-]*)", item.strip())
                name = m.group(1) if m else item
                add_row(rows, path=rel(path), ecosystem="pip", name=name, constraint=item,
                        classification=classify_pip(item),
                        dep_class=f"optional-dependencies.{extra}", planted=planted)


def scan_actions(path: Path, rows: list) -> None:
    planted = "AUD-0025/fixtures/planted-unpinned" in rel(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for m in re.finditer(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)", text):
        uses = m.group(1).strip().strip("'\"")
        if "@" in uses:
            action, ref = uses.rsplit("@", 1)
        else:
            action, ref = uses, ""
        add_row(rows, path=rel(path), ecosystem="github-actions", name=action,
                constraint=ref or "(none)", classification=classify_action_ref(ref),
                dep_class="uses", planted=planted)


def scan_dockerfile(path: Path, rows: list) -> None:
    planted = "AUD-0025/fixtures/planted-unpinned" in rel(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    for m in re.finditer(r"(?im)^(?:FROM)\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+\S+)?", text):
        image = m.group(1)
        digest = None
        tag = None
        name = image
        if "@" in image:
            name, digest = image.split("@", 1)
        last_slash = name.rfind("/")
        last_colon = name.rfind(":")
        if last_colon > last_slash:
            name, tag = name[:last_colon], name[last_colon + 1:]
        add_row(rows, path=rel(path), ecosystem="docker", name=name,
                constraint=digest or (tag if tag is not None else "(none)"),
                classification=classify_docker_tag(tag, digest),
                dep_class="FROM", planted=planted)


def iter_files() -> list:
    found = []
    for p in REPO.rglob("*"):
        if not p.is_file() or should_skip(p):
            continue
        name = p.name
        rp = rel(p)
        if name == "package.json":
            found.append(p)
        elif name.startswith("requirements") and name.endswith(".txt"):
            found.append(p)
        elif name == "pyproject.toml":
            found.append(p)
        elif name.startswith("Dockerfile"):
            found.append(p)
        elif p.suffix in {".yml", ".yaml"} and (".github/workflows" in rp or "AUD-0025/fixtures" in rp):
            found.append(p)
    return sorted(found, key=lambda x: rel(x))


def main() -> int:
    rows = []
    files = iter_files()
    for path in files:
        if path.name == "package.json":
            scan_package_json(path, rows)
        elif path.name.startswith("requirements") and path.name.endswith(".txt"):
            scan_requirements(path, rows)
        elif path.name == "pyproject.toml":
            scan_pyproject(path, rows)
        elif path.suffix in {".yml", ".yaml"}:
            scan_actions(path, rows)
        elif path.name.startswith("Dockerfile"):
            scan_dockerfile(path, rows)

    by_class = Counter(r["classification"] for r in rows)
    by_eco = Counter(r["ecosystem"] for r in rows)
    floating_rows = [r for r in rows if r["floating"]]
    exact_rows = [r for r in rows if r["classification"] == "exact"]
    planted = [r for r in rows if r["planted_negative_control"]]
    planted_floating = [r for r in planted if r["floating"]]
    prod_rows = [r for r in rows if not r["in_other_unit_probe_scratch"]]
    prod_floating = [r for r in prod_rows if r["floating"]]
    planted_ok = len(planted_floating) >= 8

    summary = {
        "unit": "AUD-0025",
        "probe": 1,
        "files_scanned": len(files),
        "declaration_count": len(rows),
        "floating_count": len(floating_rows),
        "exact_count": len(exact_rows),
        "by_classification": dict(sorted(by_class.items())),
        "by_ecosystem": dict(sorted(by_eco.items())),
        "production_scope_declaration_count": len(prod_rows),
        "production_scope_floating_count": len(prod_floating),
        "planted_negative_control_rows": len(planted),
        "planted_floating_caught": len(planted_floating),
        "planted_negative_control_ok": planted_ok,
        "ok": planted_ok,
    }
    floating_sample = [
        {
            "path": r["path"], "ecosystem": r["ecosystem"], "name": r["name"],
            "constraint": r["constraint"], "classification": r["classification"],
            "planted_negative_control": r["planted_negative_control"],
        }
        for r in floating_rows
        if (not r["in_other_unit_probe_scratch"]) or r["planted_negative_control"]
    ]
    doc = {**summary, "floating_declarations": floating_sample, "planted_rows": planted,
           "all_rows_count": len(rows), "rows": rows}
    OUT_JSON.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "AUD-0025 NAMED PROBE 1: constraint-syntax classification per declaration",
        "catalog_verbatim=Probe 1: constraint-syntax classification per declaration (exact, compatible, caret, tilde, wildcard, none).",
        "unit=AUD-0025",
        f"files_scanned={len(files)}",
        f"declaration_count={len(rows)}",
        f"floating_count={len(floating_rows)}",
        f"exact_count={len(exact_rows)}",
        f"by_classification={json.dumps(summary['by_classification'], sort_keys=True)}",
        f"by_ecosystem={json.dumps(summary['by_ecosystem'], sort_keys=True)}",
        f"production_scope_floating_count={len(prod_floating)}",
        f"planted_floating_caught={len(planted_floating)}",
        f"planted_negative_control_ok={planted_ok}",
        "PLANTED-FLOATING-BEGIN",
    ]
    for r in planted_floating:
        lines.append(f"PLANTED\t{r['ecosystem']}\t{r['name']}\t{r['constraint']}\t{r['classification']}\t{r['path']}")
    lines.append("PLANTED-FLOATING-END")
    lines.append("FLOATING-SAMPLE-BEGIN")
    for r in floating_sample[:40]:
        lines.append(f"FLOAT\t{r['ecosystem']}\t{r['classification']}\t{r['name']}={r['constraint']}\t{r['path']}")
    lines.append("FLOATING-SAMPLE-END")
    lines.append("SUCCESS:AUD-0025-probe1" if planted_ok else "FAIL:AUD-0025-probe1 planted negative control not caught")
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if planted_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
