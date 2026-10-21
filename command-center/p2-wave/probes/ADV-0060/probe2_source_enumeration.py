#!/usr/bin/env python
"""ADV-0060 named probe 2: static enumeration of every external-command invocation point.

Mechanism (mechanically different from probe 1's runtime beacons): an AST walk over the
production sources of BOTH live package surfaces (platform/plugin/*.py, platform/marketplace/
mkt/*.py, tests excluded) finds every node that can spawn a process -- subprocess.* calls,
os.system, os.exec*, os.startfile, os.popen -- and records file:line + enclosing function +
the argv expression shape (fixed literal vs package-influenced). Each enumerated site is then
JOINED against probe 1's runtime trace: a site that fired is EXERCISED, a site that did not
fire is reported as NOT-EXERCISED (a gap), never as safe. The declared policy document
(platform/plugin/policy.py) is read in the same pass: install_runs_shipped_code, per-kind
triggers, and the fail-open/fail-closed table.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE_DIR = Path(__file__).resolve().parent

SURFACES = {
    "plugin": REPO / "platform" / "plugin",
    "marketplace": REPO / "platform" / "marketplace" / "mkt",
}

INTERESTING_ATTRS = {
    "run", "Popen", "call", "check_call", "check_output",
}
INTERESTING_OS = {"system", "startfile", "popen", "execv", "execve", "execvp", "spawnv",
                  "spawnve", "fork", "forkpty"}


def _target(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Attribute):
        base = f.value
        if isinstance(base, ast.Name):
            if base.id == "subprocess" and f.attr in INTERESTING_ATTRS:
                return f"subprocess.{f.attr}"
            if base.id == "os" and f.attr in INTERESTING_OS:
                return f"os.{f.attr}"
        if isinstance(base, ast.Attribute) and base.attr == "subprocess" and \
                isinstance(base.value, ast.Name) and base.value.id == "subprocess":
            return f"subprocess.{f.attr}"
    if isinstance(f, ast.Name) and f.id in {"system", "Popen", "popen"}:
        return f"bare.{f.id}"
    return None


def _argv_shape(node: ast.Call) -> str:
    """Classify the first positional argument: literal / name / expression."""
    if not node.args:
        return "no-positional-arg"
    a = node.args[0]
    if isinstance(a, (ast.List, ast.Tuple)):
        return "argv-array-literal" if all(
            isinstance(e, ast.Constant) for e in a.elts) else "argv-array-expression"
    if isinstance(a, ast.Name):
        return "argv-variable"
    return "argv-expression"


def enumerate_sites() -> list[dict[str, object]]:
    sites: list[dict[str, object]] = []
    for surface, root in SURFACES.items():
        for py in sorted(root.glob("*.py")):
            if py.name.startswith("test_") or py.name == "conftest.py":
                continue
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
            # map line -> enclosing function name
            fn_of: dict[int, str] = {}
            for t in ast.walk(tree):
                if isinstance(t, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for lineno in range(t.lineno, (t.end_lineno or t.lineno) + 1):
                        fn_of.setdefault(lineno, t.name)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                target = _target(node)
                if target is None:
                    continue
                sites.append({
                    "surface": surface,
                    "file": str(py.relative_to(REPO)).replace("\\", "/"),
                    "line": node.lineno,
                    "function": fn_of.get(node.lineno, "<module>"),
                    "call": target,
                    "argv_shape": _argv_shape(node),
                })
    return sites


def policy_audit() -> dict[str, object]:
    sys.path.insert(0, str(REPO / "platform"))
    from plugin import policy  # noqa: PLC0415

    doc = policy.exec_policy_document()
    rows = {}
    for rule in doc["rules"]:
        rows[rule["entrypoint_kind"]] = {
            "trigger": rule["trigger"],
            "interpreter_required": rule["interpreter_required"],
            "network_allowed": rule["network_allowed"],
            "credential_read_allowed": rule["credential_read_allowed"],
        }
    return {
        "default_trigger": doc["default_trigger"],
        "install_runs_shipped_code": doc["install_runs_shipped_code"],
        "credential_boundary": doc["credential_boundary"],
        "entrypoint_kinds": rows,
        "fail_open_components": [
            r["component"] for r in
            (x.as_dict() for x in policy.FAILURE_RULES) if r["mode"] == "fail-open"
        ],
        "fail_closed_components": [
            r["component"] for r in
            (x.as_dict() for x in policy.FAILURE_RULES) if r["mode"] == "fail-closed"
        ],
    }


def main() -> int:
    lines: list[str] = []
    say = lines.append
    say("PROBE-2-BEGIN:ADV-0060")
    say("mechanism=AST enumeration of process-spawn sites joined to probe1 runtime trace; "
        "unexercised site = NOT-EXERCISED gap, never safe")

    sites = enumerate_sites()
    say(f"SITES production_external_command_call_sites={len(sites)}")
    for s in sites:
        say(f"SITE {s['surface']} {s['file']}:{s['line']} in {s['function']}() "
            f"{s['call']} argv={s['argv_shape']}")

    # join with probe 1 trace
    trace_path = PROBE_DIR / "probe1-results.json"
    trace: list[dict] = []
    if trace_path.is_file():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8")).get("trace", [])
        except Exception as exc:  # noqa: BLE001
            say(f"WARN probe1 trace unreadable: {exc}")
    else:
        say("WARN probe1-results.json absent; join is NOT-CHECKED")

    # per-site derivation from the trace (stated as derivation, with basis):
    #  - proc.py probe_interpreter(): probe1 traced '<python> --version' during
    #    install+update -> that argv shape originates only from probe_interpreter
    #  - proc.py run(): probe1's explicit-entrypoint control invoked plugin.proc.run
    #    directly (rc=0, beacon written) -> the wrapper executed a subprocess
    #  - lifecycle_rehearsal.py run(): a standalone rehearsal driver (CLI-as-subprocess);
    #    probe1 never invoked it -> NOT-EXERCISED-BY-PROBE1, a declared gap
    traced = json.dumps(trace)
    ver_probes = sum(1 for t in trace if str(t.get("argv", [])[-1:]) == "['--version']")
    explicit = any(t.get("phase") == "explicit-entrypoint-control" for t in trace)
    def site_status(s):  # noqa: ANN001
        f = s["file"]
        if f.endswith("proc.py") and s["function"] == "probe_interpreter":
            return ("EXERCISED-by-probe1 (" + str(ver_probes) +
                    " traced '<interpreter> --version' probes)") if ver_probes else "NOT-EXERCISED"
        if f.endswith("proc.py") and s["function"] == "run":
            return "EXERCISED-by-probe1-explicit-control" if explicit else "NOT-EXERCISED"
        if f.endswith("lifecycle_rehearsal.py"):
            return ("NOT-EXERCISED-BY-PROBE1 (standalone rehearsal driver; install/update/"
                    "uninstall path does not import it; declared gap)")
        return "NOT-EXERCISED" if traced else "NOT-CHECKED"
    join = []
    for s in sites:
        status = site_status(s)
        join.append({**s, "join_status": status})
        say(f"JOIN {s['file']}:{s['line']} {s['call']} -> {status}")
    for s in sites:
        if s["surface"] == "marketplace":
            say(f"JOIN-MKT {s['file']}:{s['line']} -> NOT-CHECKED")

    pol = policy_audit()
    say(f"POLICY default_trigger={pol['default_trigger']} "
        f"install_runs_shipped_code={pol['install_runs_shipped_code']}")
    for kind, row in pol["entrypoint_kinds"].items():
        say(f"POLICY kind={kind} trigger={row['trigger']} "
            f"interpreter_required={row['interpreter_required']} "
            f"network_allowed={row['network_allowed']} "
            f"credential_read_allowed={row['credential_read_allowed']}")
    say(f"POLICY fail_open={pol['fail_open_components']} "
        f"fail_closed_count={len(pol['fail_closed_components'])}")

    results = {
        "production_external_command_call_sites": len(sites),
        "sites": sites,
        "join": join,
        "policy": pol,
        "probe1_trace_len": len(trace),
    }
    out = PROBE_DIR / "probe2-results.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    raw = PROBE_DIR / "probe2-source-enumeration.raw.txt"
    raw.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    say("PROBE-2-COMPLETE:ADV-0060")
    print("\n".join(lines))
    print(f"OUT={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
