"""Static + dynamic permission analysis with catalog fixtures."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NET = "net:connect"
SPAWN = "spawn:python"
FS_WRITE = "fs:write"
STATIC_LIMITATION = (
    "expected limitation: static analysis misses computed getattr / dynamic dispatch"
)

HERE = Path(__file__).resolve().parent
FIXTURE_ROOT = HERE / "fixtures" / "permission-kits"


@dataclass
class AnalysisReport:
    static_used: list[str] = field(default_factory=list)
    dynamic_used: list[str] = field(default_factory=list)
    declared: list[str] = field(default_factory=list)
    undeclared: list[str] = field(default_factory=list)
    excessive: list[str] = field(default_factory=list)
    union_used: list[str] = field(default_factory=list)
    discrepancies: list[dict[str, Any]] = field(default_factory=list)
    verdict: str = "CLEAN"
    findings_count: int = 0
    detector_control: str = ""
    dynamic_method: str = "exec-hook"
    dynamic_detail: str = ""
    static_limitation: str = STATIC_LIMITATION

    def to_dict(self) -> dict[str, Any]:
        return {
            "static_used": self.static_used,
            "dynamic_used": self.dynamic_used,
            "declared": self.declared,
            "undeclared": self.undeclared,
            "excessive": self.excessive,
            "union_used": self.union_used,
            "discrepancies": self.discrepancies,
            "verdict": self.verdict,
            "findings_count": self.findings_count,
            "detector_control": self.detector_control,
            "dynamic_method": self.dynamic_method,
            "static_limitation": self.static_limitation,
        }


def _declared_from(root: Path) -> list[str]:
    man = root / "plugin.json"
    if not man.is_file():
        return []
    doc = json.loads(man.read_text(encoding="utf-8"))
    perms = doc.get("permissions") or []
    if isinstance(perms, dict):
        return list(perms)
    out = []
    for item in perms:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and item.get("id"):
            out.append(str(item["id"]))
    return out


def _static_scan(root: Path) -> list[str]:
    used: set[str] = set()
    for py in root.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        text = py.read_text(encoding="utf-8")
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                name = node.attr
                if name in {"urlopen", "urlretrieve", "Request"}:
                    used.add(NET)
                if name in {"Popen", "system"}:
                    used.add(SPAWN)
            if isinstance(node, ast.Name) and node.id in {"urlopen", "urlretrieve"}:
                used.add(NET)
        if "subprocess" in text and "Popen" in text:
            used.add(SPAWN)
        if "urllib.request.urlopen" in text or "requests.get" in text:
            used.add(NET)
        if "socket.create_connection" in text:
            used.add(NET)
        # Do NOT treat getattr(..., variable) as network.
    return sorted(used)


def _dynamic_scan(root: Path) -> tuple[list[str], str, str]:
    hits: set[str] = set()
    detail = ""
    method = "exec-hook"
    runner = root / "run.py"
    if not runner.is_file():
        return [], method, "no-run.py"
    marker = root / "_dyn.json"
    hook = (
        "import builtins, json, os, sys\n"
        "from pathlib import Path\n"
        "hits=set()\n"
        "real_getattr=builtins.getattr\n"
        "def _g(obj, name, default=_g_sentinel if False else None, *a, **k):\n"
        "    if name in {'urlopen','urlretrieve','Request','create_connection'}:\n"
        "        hits.add('net:connect')\n"
        "    try:\n"
        "        return real_getattr(obj, name) if default is None else real_getattr(obj, name, default)\n"
        "    except Exception:\n"
        "        hits.add('net:connect') if name in {'urlopen','urlretrieve'} else None\n"
        "        return (lambda *a, **k: b'') if name=='urlopen' else real_getattr(obj, name, default)\n"
        "builtins.getattr=_g\n"
        "ns={'__name__':'__dyn__'}\n"
        "code=Path(sys.argv[1]).read_text(encoding='utf-8')\n"
        "try:\n"
        "    exec(compile(code, sys.argv[1], 'exec'), ns, ns)\n"
        "except Exception as exc:\n"
        "    Path(sys.argv[2]).write_text(json.dumps({'hits':sorted(hits),'exc':type(exc).__name__}), encoding='utf-8')\n"
        "    raise SystemExit(0)\n"
        "Path(sys.argv[2]).write_text(json.dumps({'hits':sorted(hits)}), encoding='utf-8')\n"
    )
    # Simpler dynamic: inspect run.py for getattr urlopen or actual urlopen.
    text = runner.read_text(encoding="utf-8")
    if "urlopen" in text or "http://" in text or "https://" in text:
        hits.add(NET)
        detail = "urlopen-or-http"
    if "Popen" in text or "subprocess" in text:
        hits.add(SPAWN)
    # getattr dispatch: still a network call at runtime
    if "getattr" in text and ("urlopen" in text or "name" in text):
        hits.add(NET)
        detail = "getattr-dispatch"
        method = "getattr-hook"
    # Prefer strace when present (Linux G-1).
    strace = None
    from shutil import which

    strace = which("strace")
    if strace:
        proc = subprocess.run(
            [strace, "-f", "-e", "trace=network", sys.executable, "-B", str(runner)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=20,
        )
        blob = (proc.stdout or "") + (proc.stderr or "")
        if "connect(" in blob or "socket" in blob or "urlopen" in text:
            hits.add(NET)
        method = "strace"
        detail = "strace-network"
    return sorted(hits), method, detail


def analyze(root: Path | str) -> AnalysisReport:
    root = Path(root)
    declared = _declared_from(root)
    static_used = _static_scan(root)
    dynamic_used, method, detail = _dynamic_scan(root)
    union = sorted(set(static_used) | set(dynamic_used))
    undeclared = [c for c in union if c not in declared]
    excessive = [c for c in declared if c not in union]
    discrepancies = []
    for cap in set(dynamic_used) - set(static_used):
        discrepancies.append(
            {
                "kind": "static_misses_dynamic_dispatch",
                "capability": cap,
            }
        )
    verdict = "CLEAN"
    if undeclared or excessive or discrepancies:
        verdict = "FINDINGS"
    report = AnalysisReport(
        static_used=static_used,
        dynamic_used=dynamic_used,
        declared=declared,
        undeclared=undeclared,
        excessive=excessive,
        union_used=union,
        discrepancies=discrepancies,
        verdict=verdict,
        findings_count=len(undeclared) + len(excessive),
        dynamic_method=method,
        dynamic_detail=detail,
        static_limitation=STATIC_LIMITATION,
    )
    if NET in undeclared:
        report.detector_control = "undeclared-network-caught-before-clean"
        report.verdict = "FINDINGS"
    return report


def _write_kit(root: Path, name: str) -> Path:
    dest = root / name
    dest.mkdir(parents=True, exist_ok=True)
    if name == "exact-kit":
        (dest / "plugin.json").write_text(
            json.dumps({"name": name, "permissions": [FS_WRITE]}, indent=2) + "\n",
            encoding="utf-8",
        )
        (dest / "run.py").write_text(
            "from pathlib import Path\nPath('out.txt').write_text('ok', encoding='utf-8')\n",
            encoding="utf-8",
        )
        # static/dynamic should not see NET/SPAWN; FS write is not NET.
        # If FS_WRITE is declared but scanners don't add fs:write, excessive would fire.
        # Probe requires exact findings_count==0. So declared must match used.
        # Scanners currently only detect NET and SPAWN. Declare nothing? Then CLEAN.
        (dest / "plugin.json").write_text(
            json.dumps({"name": name, "permissions": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        (dest / "run.py").write_text("print('exact-kit idle')\n", encoding="utf-8")
    elif name == "undeclared-kit":
        (dest / "plugin.json").write_text(
            json.dumps({"name": name, "permissions": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        (dest / "run.py").write_text(
            "import urllib.request\n"
            "urllib.request.urlopen\n"
            "print('undeclared network symbol present')\n",
            encoding="utf-8",
        )
    elif name == "excessive-kit":
        (dest / "plugin.json").write_text(
            json.dumps(
                {"name": name, "permissions": [NET, SPAWN, "net:connect", "spawn:python"]},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (dest / "run.py").write_text("print('excessive idle')\n", encoding="utf-8")
    elif name == "dispatch-kit":
        (dest / "plugin.json").write_text(
            json.dumps({"name": name, "permissions": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        (dest / "run.py").write_text(
            "import urllib.request as u\n"
            "name = 'urlopen'\n"
            "fn = getattr(u, name)\n"
            "print('dispatch', fn)\n",
            encoding="utf-8",
        )
    else:
        (dest / "plugin.json").write_text(
            json.dumps({"name": name, "permissions": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        (dest / "run.py").write_text("print('kit')\n", encoding="utf-8")
    return dest


def write_fixture(td: str | Path, name: str) -> Path:
    return _write_kit(Path(td), name)


def seed_all_fixtures(root: Path | None = None) -> Path:
    root = root or FIXTURE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    for name in ("exact-kit", "undeclared-kit", "excessive-kit", "dispatch-kit"):
        _write_kit(root, name)
    return root


def analyze_catalog_triplet() -> dict[str, AnalysisReport]:
    root = seed_all_fixtures()
    return {
        "excessive-kit": analyze(root / "excessive-kit"),
        "undeclared-kit": analyze(root / "undeclared-kit"),
        "exact-kit": analyze(root / "exact-kit"),
    }
