"""AUDIT (independent): coverage-gate operability + dependency-manifest census, my own scan."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build"}


def walk(root):
    for p in root.rglob("*"):
        if any(s in p.parts for s in SKIP):
            continue
        yield p


print("=" * 72)
print("COVERAGE GATE  (builder: 43 projects, 1 gated, 42 NOT-CHECKED, 0 runnable)")
print("=" * 72)
thr = [p for p in walk(REPO) if p.name == ".coverage-thresholds.json"]
print(f"  .coverage-thresholds.json files : {len(thr)}")
for t in thr:
    d = json.loads(t.read_text(encoding="utf-8"))
    enf = d.get("enforcement", {})
    cmd = enf.get("command")
    print(f"    path    : {t.relative_to(REPO).as_posix()}")
    print(f"    command : {cmd!r}")
    print(f"    blockPRCreation={enf.get('blockPRCreation')} blockTaskCompletion={enf.get('blockTaskCompletion')}")
    pkg = t.parent / "package.json"
    if pkg.is_file():
        pj = json.loads(pkg.read_text(encoding="utf-8"))
        scripts = pj.get("scripts", {})
        print(f"    sibling package.json scripts = {scripts!r}   (empty => command cannot run)")
        want = (cmd or "").replace("pnpm ", "").replace("npm run ", "").strip()
        print(f"    is '{want}' present in scripts? {want in scripts}")
    else:
        print("    NO sibling package.json")

# project discovery, my own definition
markers = ("pyproject.toml", "package.json", "pytest.ini", "setup.py", "setup.cfg", "tox.ini")
projs = set()
for p in walk(REPO):
    if p.name in markers:
        projs.add(p.parent)
print(f"  projects discovered by marker files : {len(projs)}  (builder: 43)")
print(f"  gated (have .coverage-thresholds)   : {len(thr)}")
print(f"  ungated                              : {len(projs) - len(thr)}")

print()
print("=" * 72)
print("PYTHON DEP MANIFESTS  (builder: 23 manifests, 93 deps, 4 locked, 19 unlocked)")
print("=" * 72)
man = [p for p in walk(REPO)
       if p.name in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "Pipfile", "setup.py", "setup.cfg")]
kinds = {}
for m in man:
    kinds[m.name] = kinds.get(m.name, 0) + 1
print(f"  python manifests found : {len(man)}   breakdown={kinds}")
locks = [p for p in walk(REPO) if p.name in ("uv.lock", "poetry.lock", "Pipfile.lock", "requirements.lock")]
print(f"  lockfiles found        : {len(locks)} {[str(x.relative_to(REPO).as_posix()) for x in locks]}")
