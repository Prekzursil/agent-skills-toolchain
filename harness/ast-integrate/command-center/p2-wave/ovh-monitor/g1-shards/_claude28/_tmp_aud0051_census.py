import pathlib

REPO = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate')
SKIP = {"node_modules", ".git", ".venv", "venv", "dist", "build", "__pycache__",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox"}
PROBE_MARK = "/p2-wave/probes/"


def skipped(path):
    return any(part in SKIP for part in path.parts)


def in_probe_tree(path):
    return PROBE_MARK in path.as_posix().replace("\\", "/")


projects = {}
tools = REPO / "tools"
if tools.is_dir():
    for child in sorted(tools.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name in SKIP:
            continue
        rel = child.relative_to(REPO).as_posix()
        py_files = [p for p in child.rglob("*.py") if not skipped(p)]
        if py_files or (child / "tests").is_dir():
            projects[rel] = child

for pat in ("pyproject.toml", "package.json", "pytest.ini", ".coverage-thresholds.json"):
    for path in REPO.rglob(pat):
        if skipped(path) or in_probe_tree(path):
            continue
        rel = path.parent.relative_to(REPO).as_posix() or "."
        projects.setdefault(rel, path.parent)

gated = sum(1 for root in projects.values() if (root / ".coverage-thresholds.json").is_file())
print("projects:", len(projects), "gated:", gated)
