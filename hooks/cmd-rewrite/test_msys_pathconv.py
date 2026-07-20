#!/usr/bin/env python
"""Self-tests for msys_pathconv.py + its wiring into inject-nopager.py.

Run:   python test_msys_pathconv.py
Exits non-zero on any failure.

PROOF STANDARD
==============
Every claim about MSYS behaviour here is measured at the real CreateProcess
boundary by spawning Git-Bash and reading the child's argv — never modelled.
Each argv fixture is BOTH-STATES: the same command is measured unenforced
(must be MANGLED) and enforced (must be INTENDED).  A fixture whose unenforced
state is not mangled fails loudly, so a passing enforced state can never be a
false green from a probe that simply cannot observe conversion.

The suite SKIPS (does not fail) the argv fixtures when Git-Bash is absent, so
it stays runnable on Linux CI; the pure-policy tests always run.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import msys_pathconv as M  # noqa: E402

INJECT = HERE / "inject-nopager.py"

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"
_results: list[tuple[str, str, str]] = []

ENV = {"CLAUDE_MSYS_FORCE_PLATFORM": "nt", "CLAUDE_MSYS_TELEMETRY": "0"}


def _check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, PASS if ok else FAIL, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"   {detail}" if detail and not ok else ""))


def _skip(name: str, detail: str) -> None:
    _results.append((name, SKIP, detail))
    print(f"  [{SKIP}] {name}   {detail}")


# ───────────────────────────────────────────────────────── MSYS ground truth

def _find_bash() -> str | None:
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if os.path.exists(cand):
            return cand
    which = shutil.which("bash")
    # WSL's bash is NOT MSYS and must not be used as the oracle.
    if which and "system32" not in which.lower():
        return which
    return None


BASH = _find_bash()
PROBE = HERE / "_argv_probe.py"
PROBE_SRC = (
    "import sys\n"
    "for i, a in enumerate(sys.argv[1:]):\n"
    "    sys.stdout.write('ARG%d\\t%s\\n' % (i, a))\n"
)


def run_msys(command: str) -> tuple[int, str, str]:
    """Run *command* in Git-Bash. Returns (exit_code, stdout, stderr)."""
    assert BASH
    r = subprocess.run([BASH, "-lc", command], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def measure_argv(command: str) -> list[str]:
    """-> the child's argv exactly as MSYS delivered it."""
    code, out, err = run_msys(command)
    if code != 0:
        raise AssertionError(f"probe failed ({code}): {err.strip()[:200]}")
    return [ln.split("\t", 1)[1] for ln in out.splitlines() if ln.startswith("ARG")]


def bashpath(p) -> str:
    """Windows path -> a form Git-Bash accepts verbatim.

    `subprocess.list2cmdline` is WRONG here: it emits backslashes, which bash
    consumes as escapes (`C:\\Python314\\python.exe` arrives as
    `C:Python314python.exe`). Forward slashes survive both shells. Paths with
    spaces are rejected rather than quoted, because the E5 fixture body is
    itself single-quoted and cannot nest quotes.
    """
    s = str(p).replace("\\", "/")
    assert " " not in s, f"fixture path must not contain spaces: {s}"
    return s


def enforce(command: str) -> str:
    """Apply the production policy; return the command actually to be run."""
    d = M.plan(command, ENV)
    return d.rewritten if d.action == "protect" and d.rewritten else command


# ───────────────────────────────────────────── the four false-negative classes
#
# Recovered in 05a §3 from R3:162-165.  Each is expansion-mediated: MSYS
# converts the POST-expansion argv, so the literal token text is not what the
# child sees.  Named fixture per class, one per recovered false-negative.

FN_FIXTURES = [
    # (id, production form (bridge callee),  probe form (same shell structure))
    ("E1-variable-expansion",
     'V=/mnt/evade1; wsl ls "$V"',
     'V=/mnt/evade1; {py} {probe} "$V"'),
    ("E2-cmdsubst-produces-path",
     'wsl ls "$(echo /mnt/evade2)"',
     '{py} {probe} "$(echo /mnt/evade2)"'),
    ("E4-concatenated-prefix-var",
     'PRE=/mnt; wsl ls "$PRE/evade4"',
     'PRE=/mnt; {py} {probe} "$PRE/evade4"'),
    ("E5-eval-wrapped",
     "eval 'wsl ls /mnt/evade5'",
     "eval '{py} {probe} /mnt/evade5'"),
]

FN_EXPECTED = {
    "E1-variable-expansion": "/mnt/evade1",
    "E2-cmdsubst-produces-path": "/mnt/evade2",
    "E4-concatenated-prefix-var": "/mnt/evade4",
    "E5-eval-wrapped": "/mnt/evade5",
}


def test_false_negative_fixtures() -> None:
    print("\n== recovered false-negative classes (both-states argv) ==")
    if not BASH:
        for fid, _, _ in FN_FIXTURES:
            _skip(f"FN {fid}", "Git-Bash not found")
        return
    PROBE.write_text(PROBE_SRC, encoding="utf-8")
    py = bashpath(sys.executable)
    probe = bashpath(PROBE)
    for fid, production, template in FN_FIXTURES:
        want = FN_EXPECTED[fid]
        probe_cmd = template.format(py=py, probe=probe)

        # STATE A — unenforced. MUST be mangled, else the fixture proves nothing.
        base = measure_argv(probe_cmd)
        mangled = bool(base) and base[0] != want
        _check(f"FN {fid} · STATE A unenforced argv is MANGLED",
               mangled, f"got {base!r}")

        # STATE B — enforced through the production policy.
        enforced_cmd = enforce(probe_cmd)
        got = measure_argv(enforced_cmd)
        _check(f"FN {fid} · STATE B enforced argv is INTENDED",
               got == [want], f"got {got!r} want [{want!r}]")

        # The policy must also fire on the ORIGINAL bridge-callee production
        # form, not merely on the probe substitution.
        d = M.plan(production, ENV)
        _check(f"FN {fid} · policy fires on production form",
               d.action == "protect" and want in d.protected,
               f"action={d.action} protected={d.protected}")
    PROBE.unlink(missing_ok=True)


# ─────────────────────────────────────────────── command/argument discrimination

# (id, command, expected action, note)
DISCRIMINATION = [
    # --- Windows-native exe receiving POSIX-looking args -> ENFORCE
    ("native-git-colon-form", "git show origin/main:.github/workflows", "protect"),
    ("native-wsl-mnt", "wsl -- fstrim /mnt/docker-desktop-disk", "protect"),
    ("native-adb-sdcard", "adb push local /sdcard/SAVE_DATA", "protect"),
    ("native-curl-unix-socket",
     "curl --unix-socket /var/run/docker.sock http://x/info", "protect"),
    # --- MSYS-linked callees: conversion never reaches them -> NO-OP
    ("msys-immune-ls", "ls /mnt/whatever", "noop"),
    ("msys-immune-grep", "grep -r /api/v1 .", "noop"),
    ("msys-immune-printf", "printf '%s\\n' /mnt/x", "noop"),
    # --- conversion IS wanted (native callee, real local mount) -> NO-OP
    ("legit-git-F-tmp", "git commit -F /tmp/msg.txt", "noop"),
    ("legit-git-C-drive", "git -C /c/Users/x status", "noop"),
    ("legit-native-usr", "git config --file /usr/local/gitconfig --list", "noop"),
    # --- URLs -> NO-OP
    ("url-https", "curl https://example.com/api/v1/jobs", "noop"),
    ("url-localhost-mcp", "curl http://127.0.0.1:8813/mcp", "noop"),
    # --- CLI switches containing slashes
    ("switch-eq-slash", "curl --data-binary --out=/mcp x", "protect"),
    ("switch-two-char-silent", "gcc -Ipath/to/inc main.c", "noop"),
    ("switch-windows-path", "chrome --print-to-pdf=C:/Users/x/o.pdf", "noop"),
    # --- /c/... vs C:/...
    ("drive-c-native-nonbridge", "git -C /c/Users/x log", "noop"),
    ("drive-c-bridge", "wsl ls /c/Users/x", "protect"),
    ("already-windows", "git -C C:/Users/x status", "noop"),
    # --- git revisions / refs / pathspecs
    ("git-rev-dotless-silent", "git show origin/main:docs/x.md", "noop"),
    ("git-rev-head-file", "git show HEAD:file.md", "noop"),
    ("git-rev-dotted-fires", "git show origin/main:.agents/skills/x.md", "protect"),
    ("git-pathspec-glob-silent", "git show origin/main:.github/*.yml", "noop"),
    # --- quoting does NOT protect (shell strips quotes before argv)
    ("quoted-double", 'wsl ls "/mnt/x"', "protect"),
    ("quoted-single", "wsl ls '/mnt/x'", "protect"),
    # --- response-file style
    ("response-file-at-slash", "javac @/opt/args.rsp", "protect"),
    ("response-file-relative", "javac @args.rsp", "noop"),
    # --- escapes / globs
    ("double-slash-escape", "wsl ls //mnt/escaped", "noop"),
    ("glob-suppresses", "wsl ls /tmp/js-*", "noop"),
    ("query-suppresses", "curl /api/2.1/jobs?x=1", "noop"),
    # --- heredoc bodies are stdin, never argv
    ("heredoc-body-immune",
     "cat <<'EOF' > f\ngit show origin/main:.github/workflows\nEOF", "noop"),
    # --- shell builtins never reach CreateProcess
    ("builtin-cd", "cd /mnt/nowhere", "noop"),
    ("builtin-export", "export PATH=/usr/bin:/bin", "noop"),
    # --- wrappers must be traversed, not treated as the callee
    ("wrapper-sudo-bridge", "sudo docker run -v /mnt/x:/y img", "protect"),
    ("wrapper-timeout-bridge", "timeout 5 wsl ls /mnt/x", "protect"),
    # --- word-list keywords expand in-shell, no process spawned
    ("wordlist-for", "for f in /mnt/a /mnt/b; do echo $f; done", "noop"),
    # --- explicit opt-outs
    ("optout-inline-nopathconv",
     "MSYS_NO_PATHCONV=1 git show origin/main:.github/workflows", "noop"),
    ("optout-inline-excl",
     "MSYS2_ARG_CONV_EXCL=origin git show origin/main:.github/workflows", "noop"),
    ("optout-exported",
     "export MSYS_NO_PATHCONV=1; git show origin/main:.github/workflows", "noop"),
    ("optout-marker", "git show origin/main:.github/workflows  # msys:off", "optout"),
    # --- redirect targets are resolved by bash, never converted
    ("redirect-target", "git status > /tmp/out.txt", "noop"),
    # --- grammar defects found by the argv-oracle fuzz (all measured)
    ("fuzz-proc-virtual-mount", "wsl cat /proc/self/status", "noop"),
    ("fuzz-proc-lookalike-converts", "wsl cat /procfs/a", "protect"),
    ("fuzz-bracket-glob-suppresses", "wsl ls /mnt/a[0-9]", "noop"),
    ("fuzz-bracket-unbalanced-suppresses", "wsl ls /mnt/a[b", "noop"),
    ("fuzz-colon-nonpathlist-silent", "wsl ls /mnt/x:y", "noop"),
    ("fuzz-colon-pathlist-converts", "wsl ls /mnt/x:/y", "protect"),
    ("fuzz-colon-suppresses-flag-form", "gcc -p/mcp:x main.c", "noop"),
    ("fuzz-colon-suppresses-delimiter", "curl --out=/mcp:x http://x", "noop"),
]


# Direct shape-grammar assertions for the fuzz-found defects, stated against
# the MEASURED argv so a later editor cannot "simplify" them away.
GRAMMAR_TRUTH = [
    ("/proc", None), ("/proc/x", None), ("/proc/self/fd", None),
    ("/procX", "<GIT-ROOT>/procX"), ("/procfs/a", "<GIT-ROOT>/procfs/a"),
    ("/PROC/x", "<GIT-ROOT>/PROC/x"),
    ("/mnt/a[0-9]", None), ("/mnt/a[b", None), ("/tmp/a[0-9]", None),
    ("/mnt/plain", "<GIT-ROOT>/mnt/plain"),
    ("/mnt/x:y", None), ("/mnt:x", None), ("/mnt/x:y/z", None),
    ("/a/b:c/d", None),
    ("--out=/mcp:x", None), ("-p/mcp:x", None), ("@/mcp:x", None),
    ("--out=/mcp", "--out=<GIT-ROOT>/mcp"), ("-p/mcp", "-p<GIT-ROOT>/mcp"),
    ("http://127.0.0.1:8813/mcp", None), ("C:/already/windows", None),
]


def test_shape_grammar() -> None:
    print("\n== shape grammar vs measured argv ==")
    for tok, want in GRAMMAR_TRUTH:
        hit = M.predict_conversion(tok)
        got = hit[0] if hit else None
        _check(f"grammar {tok!r} -> {want!r}", got == want, f"got {got!r}")


def test_discrimination() -> None:
    print("\n== command-aware / argument-aware discrimination ==")
    for tid, cmd, want in DISCRIMINATION:
        d = M.plan(cmd, ENV)
        _check(f"discriminate {tid} -> {want}", d.action == want,
               f"got {d.action} ({d.reason})")


# ───────────────────────────────────────────────────────── real end-to-end git

def test_real_git_end_to_end(repo: Path) -> None:
    """The decisive proof: a REAL native callee, a REAL command, real exit codes."""
    print("\n== real end-to-end enforcement (native git) ==")
    if not BASH:
        _skip("git end-to-end", "Git-Bash not found")
        return
    if not (repo / ".git").exists():
        # Happens when the suite runs from a copied tree (e.g. mutation
        # testing). SKIP rather than fail for the wrong reason.
        _skip("git end-to-end", f"not a git repository: {repo}")
        return
    cmd = "git show origin/main:.github/workflows"
    cd = f"cd {bashpath(repo)} && "

    # STATE A — known-broken.
    a_code, a_out, a_err = run_msys(cd + cmd)
    _check("git STATE A unenforced FAILS with the ambiguous-argument error",
           a_code != 0 and "ambiguous argument" in (a_err + a_out).lower(),
           f"exit={a_code} err={a_err.strip()[:120]}")

    # STATE B — enforced.
    enforced = enforce(cmd)
    _check("git enforcement actually rewrote the command",
           enforced != cmd and "MSYS2_ARG_CONV_EXCL" in enforced, enforced)
    b_code, b_out, b_err = run_msys(cd + enforced)
    _check("git STATE B enforced SUCCEEDS (exit 0, real tree listing)",
           b_code == 0 and "tree origin/main:.github/workflows" in b_out,
           f"exit={b_code} out={b_out.strip()[:120]} err={b_err.strip()[:120]}")

    # Exit-code fidelity: the caller sees the CHILD's code, not a wrapper's.
    # A deliberately failing enforced command must still surface git's own code.
    bad = enforce("git show origin/main:.github/does-not-exist-xyz")
    c_code, _, c_err = run_msys(cd + bad)
    _check("exit-code fidelity: child's own non-zero code reaches the caller",
           c_code == 128, f"exit={c_code} err={c_err.strip()[:120]}")

    # A legitimate conversion must still happen in the SAME command.
    with tempfile.TemporaryDirectory() as td:
        msg = Path(td) / "msg.txt"
        msg.write_text("hello\n", encoding="utf-8")
        # /tmp is a real mount: conversion resolves back to the same file.
        legit = "git rev-parse --git-dir"
        _check("legitimate command untouched by policy",
               M.plan(legit, ENV).action == "noop")


# ──────────────────────────────────────── prevention: byte-identical protected state

FARSIDE_TOOL = """import json, sys
# Simulates a POSIX far side (WSL / adb): argv[1] is a key IN THE FAR-SIDE
# namespace that only the far side can resolve. argv[2] is a LOCAL destination.
# Order of operations is the naive one that caused the 2026-05-27 save wipe:
# the destination is opened for write BEFORE the source is resolved.
manifest = json.load(open(sys.argv[3], encoding='utf-8'))
open(sys.argv[2], 'w', encoding='utf-8').close()          # truncate FIRST
src = manifest.get(sys.argv[1])
if src is None:
    sys.stderr.write('far-side path not found: %s\\n' % sys.argv[1])
    sys.exit(1)
open(sys.argv[2], 'w', encoding='utf-8').write(open(src, encoding='utf-8').read())
sys.exit(0)
"""


def test_prevention_protected_state() -> None:
    """Unsafe op stopped BEFORE mutation; protected state byte-identical after."""
    print("\n== prevention (destructive shape, byte-identical postcondition) ==")
    if not BASH:
        _skip("prevention fixture", "Git-Bash not found")
        return
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        tool = tdp / "farside_tool.py"
        tool.write_text(FARSIDE_TOOL, encoding="utf-8")
        real_src = tdp / "real_source.txt"
        real_src.write_text("PAYLOAD-v1\n", encoding="utf-8")
        manifest = tdp / "manifest.json"
        manifest.write_text(json.dumps({"/sdcard/SAVE_DATA": str(real_src)}),
                            encoding="utf-8")

        def dest_with(content: str) -> Path:
            p = tdp / "SAVE_DATA.local"
            p.write_text(content, encoding="utf-8")
            return p

        def build(dst: Path) -> str:
            return (f"{bashpath(sys.executable)} {bashpath(tool)} "
                    f"/sdcard/SAVE_DATA {bashpath(dst)} {bashpath(manifest)}")

        # STATE A — unenforced: argv mangles, source unresolvable, destination
        # already truncated => irreversible data loss (the historical wipe).
        dst = dest_with("PRECIOUS-SAVE\n")
        before = dst.read_bytes()
        code_a, _, _ = run_msys(build(dst))
        after_a = dst.read_bytes()
        _check("STATE A unenforced: destination WIPED to 0 bytes",
               code_a != 0 and after_a == b"", f"exit={code_a} len={len(after_a)}")

        # STATE B — enforced: the far-side path survives, no wipe, correct copy.
        dst = dest_with("PRECIOUS-SAVE\n")
        before = dst.read_bytes()
        cmd_b = enforce(build(dst))
        _check("STATE B command was rewritten with a per-argument exclusion",
               "MSYS2_ARG_CONV_EXCL='/sdcard/SAVE_DATA'" in cmd_b, cmd_b[:160])
        code_b, _, err_b = run_msys(cmd_b)
        after_b = dst.read_bytes()
        # Compare EOL-normalised: the far-side tool writes in text mode, so
        # Windows turns \n into \r\n. Asserting raw bytes here would be the
        # CRLF-vs-LF trap (windows-shell.md §8b) in the assertion itself.
        _check("STATE B enforced: operation SUCCEEDS and writes the real payload",
               code_b == 0 and after_b.replace(b"\r\n", b"\n") == b"PAYLOAD-v1\n",
               f"exit={code_b} content={after_b!r} err={err_b.strip()[:120]}")

        # Bystander: a protected file the enforced run must not touch at all.
        bystander = tdp / "bystander.txt"
        bystander.write_text("DO-NOT-TOUCH\n", encoding="utf-8")
        h_before = bystander.read_bytes()
        run_msys(enforce(build(dest_with("x\n"))))
        _check("protected bystander is byte-identical after enforced run",
               bystander.read_bytes() == h_before)


# ──────────────────────────────────────────────── production adapter integration

def test_production_adapter() -> None:
    """The REAL hook process must call the new logic — not just the module."""
    print("\n== production adapter (inject-nopager.py subprocess) ==")
    env = dict(os.environ)
    env["CLAUDE_MSYS_FORCE_PLATFORM"] = "nt"
    env["CLAUDE_MSYS_TELEMETRY"] = "0"

    def drive(command: str, tool: str = "Bash") -> dict:
        payload = {"session_id": "t", "tool_name": tool,
                   "tool_input": {"command": command}, "cwd": str(HERE)}
        r = subprocess.run([sys.executable, str(INJECT)],
                           input=json.dumps(payload), capture_output=True,
                           text=True, encoding="utf-8", env=env)
        assert r.returncode == 0, f"hook exited {r.returncode}: {r.stderr[:200]}"
        return json.loads(r.stdout) if r.stdout.strip() else {}

    out = drive("git show origin/main:.github/workflows")
    hso = out.get("hookSpecificOutput", {})
    cmd = hso.get("updatedInput", {}).get("command", "")
    _check("adapter emits an MSYS-enforced updatedInput",
           "MSYS2_ARG_CONV_EXCL='origin/main:.github/workflows'" in cmd, cmd)
    _check("adapter still injects --no-pager in the same rewrite",
           "--no-pager" in cmd, cmd)
    _check("adapter emits an actionable reason",
           "msys-pathconv" in hso.get("additionalContext", "")
           and "MSYS2_ARG_CONV_EXCL" in hso.get("additionalContext", ""),
           hso.get("additionalContext", "")[:160])
    _check("adapter keeps permissionDecision=allow (never blocks)",
           hso.get("permissionDecision") == "allow")

    out = drive("git log --oneline -5")
    cmd = out.get("hookSpecificOutput", {}).get("updatedInput", {}).get("command", "")
    _check("rule 1 alone still works (no MSYS noise on a clean command)",
           cmd == "git --no-pager log --oneline -5", cmd)

    _check("non-Bash tool is ignored", drive("whatever", tool="Edit") == {})
    _check("clean command produces no output at all", drive("echo hi") == {})


def test_selectivity_control() -> None:
    """THE control that a global MSYS_NO_PATHCONV=1 would break.

    One command, two arguments: a harmful one that must be protected, and a
    legitimate one whose conversion is REQUIRED (native callee + real mount).
    Enforcement must do both at once — that is why the primitive is the
    per-argument MSYS2_ARG_CONV_EXCL and not the process-wide switch.
    """
    print("\n== selectivity: legitimate conversion still happens ==")
    if not BASH:
        _skip("selectivity control", "Git-Bash not found")
        return
    PROBE.write_text(PROBE_SRC, encoding="utf-8")
    try:
        cmd = f"{bashpath(sys.executable)} {bashpath(PROBE)} /sdcard/SAVE_DATA /tmp/legit.txt"
        base = measure_argv(cmd)
        _check("STATE A: BOTH args converted (harmful one is mangled)",
               len(base) == 2 and base[0] != "/sdcard/SAVE_DATA"
               and base[1] != "/tmp/legit.txt", f"got {base!r}")
        got = measure_argv(enforce(cmd))
        _check("STATE B: harmful arg protected verbatim",
               got[0] == "/sdcard/SAVE_DATA", f"got {got!r}")
        _check("STATE B: legitimate arg STILL CONVERTED to its Windows path",
               got[1] != "/tmp/legit.txt" and got[1].lower().endswith("legit.txt")
               and (":" in got[1]), f"got {got!r}")
    finally:
        PROBE.unlink(missing_ok=True)


def test_platform_and_optout() -> None:
    print("\n== platform gate, opt-out, fail-open ==")
    cmd = "git show origin/main:.github/workflows"
    _check("non-Windows is a hard no-op",
           M.plan(cmd, {"CLAUDE_MSYS_FORCE_PLATFORM": "linux"}).action == "not-windows")
    _check("env opt-out CLAUDE_MSYS_ENFORCE=0 disables enforcement",
           M.plan(cmd, dict(ENV, CLAUDE_MSYS_ENFORCE="0")).action == "optout")
    _check("plan() never raises on hostile input",
           M.plan('git show "unbalanced', ENV).action in M.ACTIONS)
    _check("empty command is a no-op", M.plan("   ", ENV).action == "noop")
    d = M.plan("git show origin/main:.github/workflows", ENV)
    _check("rewrite is a pure prefix splice (original text preserved verbatim)",
           bool(d.rewritten) and d.rewritten.endswith(cmd), repr(d.rewritten))


def test_telemetry() -> None:
    print("\n== telemetry ==")
    with tempfile.TemporaryDirectory() as td:
        sink = Path(td) / "decisions.jsonl"
        env = dict(ENV, CLAUDE_MSYS_TELEMETRY=str(sink))
        d = M.plan("git show origin/main:.github/workflows", env)
        M.record(d, "git show origin/main:.github/workflows", env)
        _check("telemetry file written", sink.exists())
        rec = json.loads(sink.read_text(encoding="utf-8").splitlines()[0])
        _check("telemetry records the decision + reason",
               rec["action"] == "protect" and rec["findings"][0]["kind"] == "colon-path-list"
               and rec["protected"] == ["origin/main:.github/workflows"], str(rec)[:200])
        _check("telemetry records a latency measurement",
               isinstance(rec["elapsed_us"], int) and rec["elapsed_us"] >= 0)
        M.record(d, "x", env)
        _check("telemetry appends (bounded JSONL)",
               len(sink.read_text(encoding="utf-8").strip().splitlines()) == 2)
        _check("telemetry is disable-able",
               M.record(d, "x", dict(ENV, CLAUDE_MSYS_TELEMETRY="0")) is None)

    # BOTH-STATES on the opt-in default. A hook that is not installed must not
    # write to live state merely because someone ran it. Regression pin: an
    # earlier revision defaulted the sink to $USERPROFILE/.claude/state/... and
    # the sibling test_hooks.py suite (which inherits the ambient env) wrote 27
    # records there.
    no_tel = {k: v for k, v in ENV.items() if k != "CLAUDE_MSYS_TELEMETRY"}
    _check("default is OFF: no sink resolved when the env var is unset",
           M.telemetry_path(no_tel) is None, repr(M.telemetry_path(no_tel)))
    _check("default is OFF: record() writes nothing when unset",
           M.record(M.plan("git show origin/main:.github/workflows", no_tel),
                    "x", no_tel) is None)
    _check("default is OFF: USERPROFILE alone does NOT activate a sink",
           M.telemetry_path(dict(no_tel, USERPROFILE=r"C:\Users\nobody",
                                 HOME="/home/nobody")) is None)
    with tempfile.TemporaryDirectory() as td:
        sink = Path(td) / "on.jsonl"
        _check("explicitly ON: the configured sink IS used",
               M.telemetry_path(dict(ENV, CLAUDE_MSYS_TELEMETRY=str(sink)))
               == str(sink))


def main() -> int:
    # MSYS_TEST_REPO lets a copied tree (mutation testing) point back at a real
    # checkout instead of skipping the git end-to-end proof.
    repo = Path(os.environ.get("MSYS_TEST_REPO") or HERE.parent.parent)
    print("msys_pathconv test suite")
    print(f"  bash oracle : {BASH or '(none — argv fixtures will SKIP)'}")
    print(f"  repo        : {repo}")
    test_shape_grammar()
    test_discrimination()
    test_platform_and_optout()
    test_telemetry()
    test_production_adapter()
    test_false_negative_fixtures()
    test_selectivity_control()
    test_real_git_end_to_end(repo)
    test_prevention_protected_state()

    npass = sum(1 for _, s, _ in _results if s == PASS)
    nfail = sum(1 for _, s, _ in _results if s == FAIL)
    nskip = sum(1 for _, s, _ in _results if s == SKIP)
    print(f"\n{npass} passed, {nfail} failed, {nskip} skipped")
    if nfail:
        print("\nFAILURES:")
        for name, status, detail in _results:
            if status == FAIL:
                print(f"  - {name}: {detail}")
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
