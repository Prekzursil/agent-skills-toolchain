#!/usr/bin/env python3
"""Mechanise CNF-0023 prose recipes into path-invoked scripts.

Scripts are always spawned as argv [interpreter, script_path, state_dir].
The body is never interpolated into a shell command (windows-shell section 10).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0023"
GEN = HERE / "generated"
UNFIXED = HERE / "fixtures" / "unfixed"
FIXED = HERE / "fixtures" / "fixed"
CORPUS_PATH = HERE / "fixtures" / "corpus.json"

HEADER = '''#!/usr/bin/env python3
"""Mechanised repro {rid} — don't inline; the reporter's can't-repro string
would break single-quoted shell quoting (windows-shell section 10)."""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

RID = {rid!r}
'''

SCRIPTS = {
    "R-APOSTROPHE-INLINE": '''
def main() -> int:
    state = Path(sys.argv[1])
    adapter = state / "adapter.py"
    payload = state / "payload.py"
    if not adapter.is_file() or not payload.is_file():
        print("missing adapter or payload")
        return 2
    proc = subprocess.run(
        [sys.executable, str(adapter), str(payload)],
        capture_output=True,
        text=True,
    )
    sys.stdout.write(proc.stdout or "")
    sys.stderr.write(proc.stderr or "")
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
''',
    "R-OPTION-ID-COLLISION": r'''
TOKEN = re.compile(r"\bM-\d{2}\b")


def tokens(path: Path) -> set[str]:
    return set(TOKEN.findall(path.read_text(encoding="utf-8")))


def main() -> int:
    state = Path(sys.argv[1])
    a = tokens(state / "option-universe.md")
    b = tokens(state / "architecture-candidates.md")
    shared = sorted(a & b)
    print(f"shared={len(shared)} ids={shared[:8]}")
    if len(shared) == 31:
        return 1
    if len(shared) == 0:
        return 0
    print("unexpected intersection size")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
''',
    "R-SIDECAR-DRY-RUN": '''
def main() -> int:
    state = Path(sys.argv[1])
    sidecar = state / "dry-run-out" / "sidecar.json"
    if sidecar.is_file():
        print(f"sidecar present at {sidecar} (dry-run leaked)")
        return 1
    print("sidecar absent (dry-run clean)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
    "R-PIN-PARITY": '''
def digest(path: Path) -> str:
    raw = path.read_bytes().replace(b"\\r\\n", b"\\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    state = Path(sys.argv[1])
    a = state / "pin-a.txt"
    b = state / "pin-b.txt"
    da, db = digest(a), digest(b)
    print(f"pin-a={da} pin-b={db}")
    if da != db:
        print("pin mismatch: ambient formatter disagrees with the pin")
        return 1
    print("pin match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
}

SCRIPT_NAMES = {
    "R-APOSTROPHE-INLINE": "r_apostrophe.py",
    "R-OPTION-ID-COLLISION": "r_option_id.py",
    "R-SIDECAR-DRY-RUN": "r_sidecar.py",
    "R-PIN-PARITY": "r_pin.py",
}


def load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


def artifact_field(doc: dict, key: str, default=None):
    """Read a probe-facing field from the receipt core or report payload."""
    if not isinstance(doc, dict):
        return default
    if key in doc:
        return doc[key]
    report = doc.get("report")
    if isinstance(report, dict) and key in report:
        return report[key]
    return default


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ids_md(prefix: str, title: str) -> str:
    lines = [f"# {title}", ""]
    for i in range(1, 32):
        lines.append(f"{prefix}-{i:02d} item-{i:02d}")
    lines.append("")
    return "\n".join(lines)


def ensure_fixtures() -> None:
    universe = _ids_md("M", "Family M options")
    colliding = _ids_md("M", "Mechanisms (colliding M-NN)")
    repaired = _ids_md("MECH", "Mechanisms (re-prefixed)")
    for root in (UNFIXED, FIXED):
        _write(root / "option-universe.md", universe)
        _write(root / "payload.py", 'print("can\'t")\n')
    _write(UNFIXED / "architecture-candidates.md", colliding)
    _write(FIXED / "architecture-candidates.md", repaired)
    _write(
        UNFIXED / "dry-run-out" / "sidecar.json",
        '{"written": true, "dry_run": true}\n',
    )
    _write(FIXED / "dry-run-out" / ".keep", "")
    _write(UNFIXED / "pin-a.txt", "formatter 0.15.17 canonical bytes\n")
    _write(UNFIXED / "pin-b.txt", "formatter 0.15.22 DIFFERENT bytes\n")
    _write(FIXED / "pin-a.txt", "formatter 0.15.17 canonical bytes\n")
    _write(FIXED / "pin-b.txt", "formatter 0.15.17 canonical bytes\n")
    _write(
        UNFIXED / "adapter.py",
        (
            "#!/usr/bin/env python3\n"
            "'''UNFIXED adapter: interpolates payload into a single-quoted bash -c body.'''\n"
            "import subprocess\n"
            "import sys\n"
            "from pathlib import Path\n"
            "\n"
            "body = Path(sys.argv[1]).read_text(encoding='utf-8').strip()\n"
            "# windows-shell section 10 defect: apostrophe in body terminates the quotes.\n"
            "cmd = \"python3 -c '\" + body + \"'\"\n"
            "proc = subprocess.run(['bash', '-c', cmd], capture_output=True, text=True)\n"
            "sys.stdout.write(proc.stdout or '')\n"
            "sys.stderr.write(proc.stderr or '')\n"
            "raise SystemExit(proc.returncode if proc.returncode != 0 else 1)\n"
        ),
    )
    _write(
        FIXED / "adapter.py",
        (
            "#!/usr/bin/env python3\n"
            "'''FIXED adapter: invoke the payload script by path, never inline.'''\n"
            "import subprocess\n"
            "import sys\n"
            "\n"
            "proc = subprocess.run([sys.executable, sys.argv[1]])\n"
            "raise SystemExit(proc.returncode)\n"
        ),
    )


def write_generated_scripts() -> dict:
    ensure_fixtures()
    GEN.mkdir(parents=True, exist_ok=True)
    out = {}
    for rid, name in SCRIPT_NAMES.items():
        path = GEN / name
        path.write_text(HEADER.format(rid=rid) + SCRIPTS[rid], encoding="utf-8")
        path.chmod(path.stat().st_mode | 0o111)
        out[rid] = path
    return out


def invoke_by_path(script: Path, state_dir: Path, timeout: int = 30) -> subprocess.CompletedProcess:
    """Spawn the script by argv path. Never shell=True, never python -c."""
    if not script.is_file():
        raise FileNotFoundError(script)
    argv = [sys.executable, str(script), str(state_dir)]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO),
    )


def try_inline_apostrophe_payload() -> subprocess.CompletedProcess:
    """Negative control: inline payload.py into a single-quoted python -c."""
    payload = (UNFIXED / "payload.py").read_text(encoding="utf-8").strip()
    cmd = "python3 -c '" + payload + "'"
    return subprocess.run(
        ["bash", "-c", cmd], capture_output=True, text=True, timeout=15
    )


def run_all() -> dict:
    scripts = write_generated_scripts()
    corpus = load_corpus()
    recipes = list(corpus["recipes"])
    generated = []
    for rid, path in scripts.items():
        red = invoke_by_path(path, UNFIXED)
        green = invoke_by_path(path, FIXED)
        generated.append(
            {
                "recipe_id": rid,
                "script_path": path.relative_to(REPO).as_posix(),
                "invoked_by_path": True,
                "argv_unfixed": [
                    sys.executable,
                    path.relative_to(REPO).as_posix(),
                    UNFIXED.relative_to(REPO).as_posix(),
                ],
                "argv_fixed": [
                    sys.executable,
                    path.relative_to(REPO).as_posix(),
                    FIXED.relative_to(REPO).as_posix(),
                ],
                "unfixed_exit_code": red.returncode,
                "fixed_exit_code": green.returncode,
                "unfixed_stdout_tail": (red.stdout or "")[-400:],
                "fixed_stdout_tail": (green.stdout or "")[-400:],
                "unfixed_stderr_tail": (red.stderr or "")[-400:],
                "fixed_stderr_tail": (green.stderr or "")[-400:],
            }
        )
    inline = try_inline_apostrophe_payload()
    payload_by_path = subprocess.run(
        [sys.executable, str(UNFIXED / "payload.py")],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return {
        "recipes": recipes,
        "generated": generated,
        "inline_control": {
            "command_shape": "bash -c python3 -c '<payload containing apostrophe>'",
            "exit_code": inline.returncode,
            "stderr_tail": (inline.stderr or "")[-300:],
            "failed_as_required": inline.returncode != 0,
        },
        "path_control": {
            "command_shape": "python3 <payload.py path>",
            "exit_code": payload_by_path.returncode,
            "stdout": (payload_by_path.stdout or "").strip(),
            "succeeded_as_required": payload_by_path.returncode == 0,
        },
    }


def assert_both_states(generated: list) -> list:
    errors = []
    for row in generated:
        rid = row["recipe_id"]
        if row["unfixed_exit_code"] == 0:
            errors.append(f"{rid} unfixed exited 0 (must be non-zero)")
        if row["fixed_exit_code"] != 0:
            errors.append(f"{rid} fixed exited {row['fixed_exit_code']} (must be 0)")
        if not row["invoked_by_path"]:
            errors.append(f"{rid} was not invoked by path")
        if "-c" in row["argv_unfixed"]:
            errors.append(f"{rid} argv contains -c (inlined)")
    return errors
