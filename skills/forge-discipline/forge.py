#!/usr/bin/env python3
r"""forge-discipline/forge.py - turn a named behavioral pattern into an INSTALLED,
self-tested discipline (a Claude Code hook) in ONE pass, staged in a review queue.

This is a BEHAVIOR forge, not a tool forge: it forges hooks/tripwires (things the
harness RUNS deterministically), not MCP tools (things the model CHOOSES to call).

Given a pattern spec it:
  1. SCAFFOLDS the artifacts the pattern needs:
       - a HOOK script conforming to the dispatcher check-interface
         (main(argv) reads stdin, emits hookSpecificOutput; gates exit 2 + stderr);
       - a TRIPWIRE predicate module      (only when gates=True; exit-2 path);
       - a MEMORY-SCHEMA (state schema)    (only when needs_state=True);
       - a SKILL stub                      (only when has_procedure=True).
     Everything FAILS OPEN (try/except -> exit 0; a gate never blocks on error).
  2. GENERATES a unit TEST of the predicate and runs it.
  3. Runs a CHAOS / GameDay SELF-TEST that fault-injects to PROVE the hook
       FIRES on its trigger, stays SILENT otherwise, and FAIL-OPENS on garbage.
       The discipline is NOT considered installed until this passes.
  4. Promotes the result to a REVIEW QUEUE  ~/.claude/forge-queue/<name>/  with the
       artifacts + the passing self-test + a one-line "to install" instruction
       (a manifest line for dispatcher-foldable inject hooks, or a settings.json
       entry for gates / UserPromptSubmit). It NEVER edits the live settings.json
       or manifest.json - the human reviews and applies the one line.

Design constraints honoured (mirrors the workspace's existing hooks):
  - Pure stdlib. Windows-safe (utf-8 everywhere, sys.executable for subprocesses).
  - Foldable inject events = {sessionstart, stop, pretooluse, posttooluse}; the
    dispatcher handles exactly these and only ever exits 0. userpromptsubmit and
    every gate (exit 2) therefore install as standalone settings.json entries.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
TEMPLATES = THIS / "templates"
HOME = Path.home()
HOOKS_ROOT = (HOME / ".claude" / "hooks").as_posix()
DISPATCH_MANIFEST = (HOME / ".claude" / "hooks" / "_dispatch" / "manifest.json").as_posix()
SETTINGS_JSON = (HOME / ".claude" / "settings.json").as_posix()
DEFAULT_QUEUE = HOME / ".claude" / "forge-queue"

# CLI event token -> canonical Claude Code event name.
CANON = {
    "sessionstart": "SessionStart",
    "stop": "Stop",
    "pretooluse": "PreToolUse",
    "posttooluse": "PostToolUse",
    "userpromptsubmit": "UserPromptSubmit",
}
# Events the in-process dispatcher consolidates (see _dispatch/dispatch.py).
# Inject hooks on these fold via a one-line manifest entry. NOTE: userpromptsubmit
# is intentionally absent - the dispatcher does not handle it.
DISPATCH_EVENTS = {"sessionstart", "stop", "pretooluse", "posttooluse"}
# Events on which an exit-2 gate meaningfully blocks BEFORE an action occurs.
GATE_EVENTS = {"pretooluse", "userpromptsubmit"}
# Trigger kinds and the default payload field each reads.
KIND_FIELD = {
    "tool": "tool_name",
    "command": "tool_input.command",
    "prompt": "prompt",
    "response": None,   # special: parsed from transcript_path
    "field": None,      # caller supplies --trigger-field
    "always": None,     # no predicate: always fires (inject only)
}


# ---------------------------------------------------------------------------
# Spec construction + validation
# ---------------------------------------------------------------------------

def env_off_token(name: str) -> str:
    """FORGE_<NAME>_OFF env opt-out token for the generated hook."""
    return "FORGE_" + re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").upper() + "_OFF"


def build_spec(args: argparse.Namespace) -> dict:
    """Merge an optional --spec JSON file under explicit CLI flags."""
    spec: dict = {}
    if args.spec:
        spec.update(json.loads(Path(args.spec).read_text(encoding="utf-8")))

    def take(key, val):
        if val is not None:
            spec[key] = val

    take("name", args.name)
    take("event", args.event)
    take("action", args.action)
    take("trigger_kind", args.trigger_kind)
    take("trigger_regex", args.trigger_regex)
    take("trigger_field", args.trigger_field)
    take("fire_example", args.fire_example)
    take("silent_example", args.silent_example)
    take("matcher", args.matcher)
    take("skill_description", args.skill_description)
    if args.needs_state:
        spec["needs_state"] = True
    if args.gates:
        spec["gates"] = True
    if args.has_procedure:
        spec["has_procedure"] = True
    if args.case_sensitive:
        spec["case_sensitive"] = True

    # Defaults / normalisation.
    spec.setdefault("needs_state", False)
    spec.setdefault("gates", False)
    spec.setdefault("has_procedure", False)
    spec.setdefault("case_sensitive", False)
    spec.setdefault("silent_example", "echo benign-no-match-placeholder")
    spec.setdefault("trigger_field", None)
    spec.setdefault("matcher", None)
    if "event" in spec and spec["event"]:
        spec["event"] = str(spec["event"]).strip().lower()
    if "trigger_kind" in spec and spec["trigger_kind"]:
        spec["trigger_kind"] = str(spec["trigger_kind"]).strip().lower()
    return spec


def validate_spec(spec: dict) -> None:
    """Raise ValueError on any unsound spec. This is the boundary check."""
    name = spec.get("name") or ""
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name):
        raise ValueError(f"name must be hyphen-case [a-z0-9-]: got {name!r}")
    event = spec.get("event")
    if event not in CANON:
        raise ValueError(f"event must be one of {sorted(CANON)}: got {event!r}")
    if not (spec.get("action") or "").strip():
        raise ValueError("action (inject message / block reason) is required")

    # The template renderer substitutes @@TOKEN@@ markers; a user value containing
    # '@@' could have an inner token rewritten on a later pass (corrupting the
    # emitted message and letting a chaos test pass on the wrong text). Forbid it.
    for fld in ("name", "action", "trigger_regex", "trigger_field", "skill_description",
                "fire_example", "silent_example", "matcher"):
        val = spec.get(fld)
        if isinstance(val, str) and "@@" in val:
            raise ValueError(f"{fld} may not contain '@@' (reserved template token delimiter)")

    kind = spec.get("trigger_kind")
    if kind not in KIND_FIELD:
        raise ValueError(f"trigger_kind must be one of {sorted(KIND_FIELD)}: got {kind!r}")

    if spec["gates"]:
        if event not in GATE_EVENTS:
            raise ValueError(
                f"gates=True requires a blocking event {sorted(GATE_EVENTS)}; "
                f"{event} cannot block (exit-2 is meaningless there)")
        if kind == "always":
            raise ValueError("gates=True with trigger_kind=always would block everything - refused")
    if kind == "response" and event != "stop":
        raise ValueError("trigger_kind=response reads the final assistant message - only valid on event=stop")
    if kind == "prompt" and event != "userpromptsubmit":
        raise ValueError("trigger_kind=prompt - only valid on event=userpromptsubmit")
    if kind == "field" and not spec.get("trigger_field"):
        raise ValueError("trigger_kind=field requires --trigger-field <dotted.path>")

    desc = spec.get("skill_description") or ""
    if "<" in desc or ">" in desc:
        raise ValueError("skill_description cannot contain angle brackets (skill-validator rule)")

    if kind != "always":
        regex = spec.get("trigger_regex")
        if not regex:
            raise ValueError("trigger_regex is required unless trigger_kind=always")
        flags = 0 if spec["case_sensitive"] else re.IGNORECASE
        try:
            pat = re.compile(regex, flags)
        except re.error as exc:
            raise ValueError(f"trigger_regex does not compile: {exc}") from exc
        fire = spec.get("fire_example")
        if not fire:
            raise ValueError("fire_example is required (a sample value the trigger SHOULD match) "
                             "so the chaos self-test can prove the hook fires")
        if not pat.search(fire):
            raise ValueError(f"fire_example {fire!r} does NOT match trigger_regex {regex!r} - "
                             "the chaos test would be a lie; fix the example or the regex")
        silent = spec.get("silent_example") or ""
        if pat.search(silent):
            raise ValueError(f"silent_example {silent!r} DOES match trigger_regex {regex!r} - "
                             "the 'stays silent' test would fail; choose a non-matching example")


# ---------------------------------------------------------------------------
# Derived spec fields
# ---------------------------------------------------------------------------

def resolved_field(spec: dict):
    """The dotted payload path the predicate reads (None for response/always)."""
    kind = spec["trigger_kind"]
    if kind == "field":
        return spec["trigger_field"]
    return KIND_FIELD[kind]


def default_matcher(spec: dict):
    """tool_name matcher for pre/post-tool install lines (None where N/A)."""
    if spec.get("matcher"):
        return spec["matcher"]
    kind = spec["trigger_kind"]
    if kind == "tool":
        return spec.get("trigger_regex")
    if kind == "command":
        return "Bash"
    if spec["event"] in ("pretooluse", "posttooluse"):
        return ".*"
    return None


# ---------------------------------------------------------------------------
# Template rendering ( @@TOKEN@@ replacement - safe inside Python regex/code )
# ---------------------------------------------------------------------------

def render(tmpl: str, mapping: dict) -> str:
    out = tmpl
    for key, val in mapping.items():
        out = out.replace(f"@@{key}@@", val)
    return out


def load_tmpl(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def base_mapping(spec: dict) -> dict:
    flags = "0" if spec["case_sensitive"] else "re.IGNORECASE"
    return {
        "NAME": spec["name"],
        "NAME_ID": spec["name"].replace("-", "_"),
        "CANON_EVENT": CANON[spec["event"]],
        "ENV_OFF": env_off_token(spec["name"]),
        "KIND": spec["trigger_kind"],
        "FIELD_REPR": repr(resolved_field(spec)),
        "PATTERN_REPR": repr(spec.get("trigger_regex") or ""),
        "FLAGS": flags,
        "ACTION_REPR": repr(spec["action"]),
        "NEEDS_STATE": "True" if spec["needs_state"] else "False",
    }


# ---------------------------------------------------------------------------
# Fixtures (drive both the unit test and the chaos self-test)
# ---------------------------------------------------------------------------

def build_fixtures(spec: dict) -> dict:
    extra: dict = {}
    if spec["trigger_kind"] in ("command", "tool") or spec["event"] in ("pretooluse", "posttooluse"):
        extra["tool_name"] = "Bash" if spec["trigger_kind"] == "command" else (
            spec.get("fire_example") if spec["trigger_kind"] == "tool" else "Bash")
    return {
        "name": spec["name"],
        "event": CANON[spec["event"]],
        "kind": spec["trigger_kind"],
        "field": resolved_field(spec),
        "gates": bool(spec["gates"]),
        "has_silent": spec["trigger_kind"] != "always",
        "fire_value": spec.get("fire_example") or "",
        "silent_value": spec.get("silent_example") or "",
        "extra_payload": extra,
        "garbage": ["{ not valid json", "", "\x00\x01\x02 not json", "[]", "null"],
    }


# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------

def scaffold(spec: dict, work: Path) -> list[str]:
    work.mkdir(parents=True, exist_ok=True)
    m = base_mapping(spec)
    written: list[str] = []

    if spec["gates"]:
        (work / "tripwire.py").write_text(render(load_tmpl("tripwire.py.tmpl"), m), encoding="utf-8")
        (work / "hook.py").write_text(render(load_tmpl("hook_gate.py.tmpl"), m), encoding="utf-8")
        written += ["tripwire.py", "hook.py"]
    else:
        (work / "hook.py").write_text(render(load_tmpl("hook_inject.py.tmpl"), m), encoding="utf-8")
        written += ["hook.py"]

    if spec["needs_state"]:
        schema = {
            "discipline": spec["name"],
            "store": (HOME / ".claude" / "forge-state" / spec["name"] / "ledger.ndjson").as_posix(),
            "format": "ndjson (one JSON object per line, append-only)",
            "record": {
                "ts": "float - unix epoch when recorded",
                "session": "str - session_id (dedup scope)",
                "key": "str - sha1 of the matched source (dedup identity)",
                "count": "int - number of trigger matches in that firing",
            },
            "purpose": "session-scoped dedup so the same matched item is surfaced at most once",
        }
        (work / "state_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
        written += ["state_schema.json"]

    if spec["has_procedure"]:
        desc = spec.get("skill_description") or (
            f"Companion procedure for the {spec['name']} discipline (forged hook). "
            f"Use when the {spec['name']} hook fires and a manual follow-up is needed.")
        sm = dict(m)
        sm["SKILL_DESCRIPTION"] = desc.replace("<", "(").replace(">", ")")
        sm["ACTION_PLAIN"] = spec["action"]
        (work / "SKILL.md").write_text(render(load_tmpl("skill_stub.md.tmpl"), sm), encoding="utf-8")
        written += ["SKILL.md"]

    (work / "fixtures.json").write_text(json.dumps(build_fixtures(spec), indent=2), encoding="utf-8")
    (work / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    written += ["fixtures.json", "spec.json"]
    return written


def gen_tests(spec: dict, work: Path) -> tuple[Path, Path]:
    m = base_mapping(spec)
    if spec["gates"]:
        test = render(load_tmpl("test_gate.py.tmpl"), m)
        chaos = render(load_tmpl("chaos_gate.py.tmpl"), m)
    else:
        test = render(load_tmpl("test_inject.py.tmpl"), m)
        chaos = render(load_tmpl("chaos_inject.py.tmpl"), m)
    tp = work / f"test_{spec['name'].replace('-', '_')}.py"
    cp = work / f"chaos_{spec['name'].replace('-', '_')}.py"
    tp.write_text(test, encoding="utf-8")
    cp.write_text(chaos, encoding="utf-8")
    return tp, cp


def run_script(path: Path) -> tuple[bool, str]:
    # Keep the work/queue dir free of __pycache__: the flag propagates via os.environ
    # to the test, and onward to any hook subprocess the chaos test spawns.
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        res = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(path.parent), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=120, env=env)
    except Exception as exc:  # pragma: no cover - subprocess launch failure
        return False, f"subprocess failed to launch: {exc}"
    out = (res.stdout or "") + (res.stderr or "")
    return res.returncode == 0, out.strip()


# ---------------------------------------------------------------------------
# Install-line computation + queue promotion
# ---------------------------------------------------------------------------

def fold_target(spec: dict) -> str:
    """'manifest' (one-line dispatcher fold) or 'settings' (standalone entry)."""
    if spec["gates"]:
        return "settings"  # exit-2 gates are never foldable (dispatcher exits 0 only)
    if spec["event"] in DISPATCH_EVENTS:
        return "manifest"
    return "settings"  # userpromptsubmit inject


def install_block(spec: dict) -> tuple[str, str]:
    """Return (target, the exact one-line/one-object install instruction text)."""
    name = spec["name"]
    target = fold_target(spec)
    hook_path = f"{HOOKS_ROOT}/{name}/hook.py"

    if target == "manifest":
        line: dict = {"name": f"forge/{name}", "script": f"{name}/hook.py", "args": []}
        mt = default_matcher(spec)
        if spec["event"] in ("pretooluse", "posttooluse") and mt:
            line["matcher"] = mt
        line["timeout"] = 8
        line["isolate"] = None
        line["side_effect"] = "state" if spec["needs_state"] else "none"
        line["emits"] = True
        return target, json.dumps(line)

    entry = {
        "matcher": default_matcher(spec) or ".*",
        "hooks": [{
            "type": "command",
            "command": f'python "{hook_path}"',
            "timeout": 8,
            "statusMessage": f"{name} ({'tripwire' if spec['gates'] else 'inject'})",
        }],
    }
    return target, json.dumps(entry)


def write_install_md(spec: dict, work: Path, selftest_output: str) -> None:
    name = spec["name"]
    canon = CANON[spec["event"]]
    target, one_liner = install_block(spec)
    m = base_mapping(spec)
    m["SPEC_JSON"] = json.dumps(spec, indent=2)
    m["ONE_LINER"] = one_liner
    m["HOOK_INSTALL_DIR"] = f"{HOOKS_ROOT}/{name}/"

    if target == "manifest":
        extra = ""
        if spec["event"] in ("pretooluse", "posttooluse"):
            extra = (f"\n   NOTE: also confirm the dispatcher's settings.json `{canon}` matcher "
                     f"covers this tool, or the event never reaches the dispatcher.")
        step2 = (f"2. Add this ONE line to the `checks` array under `events.{canon}` in:\n"
                 f"      {DISPATCH_MANIFEST}\n\n"
                 f"      {one_liner}\n{extra}")
    else:
        step2 = (f"2. Add this hook object to the `\"{canon}\"` array under `\"hooks\"` in:\n"
                 f"      {SETTINGS_JSON}\n\n"
                 f"      {one_liner}")
    m["STEP2"] = step2
    m["TARGET"] = target
    m["SELFTEST_OUTPUT"] = selftest_output
    m["ENV_OFF"] = env_off_token(name)
    (work / "INSTALL.md").write_text(render(load_tmpl("INSTALL.md.tmpl"), m), encoding="utf-8")


def promote(work: Path, queue_dir: Path, name: str) -> Path:
    dest = queue_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(work, dest)
    # Drop pyc/cache noise.
    for junk in dest.rglob("__pycache__"):
        shutil.rmtree(junk, ignore_errors=True)
    return dest


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def forge(spec: dict, queue_dir: Path, dry_run: bool = False, keep_work: bool = False) -> dict:
    validate_spec(spec)
    work = Path(tempfile.mkdtemp(prefix=f"forge-{spec['name']}-"))
    result: dict = {"name": spec["name"], "work": str(work)}
    try:
        artifacts = scaffold(spec, work)
        test_path, chaos_path = gen_tests(spec, work)

        unit_ok, unit_out = run_script(test_path)
        chaos_ok, chaos_out = run_script(chaos_path)
        result.update({
            "artifacts": artifacts,
            "unit_ok": unit_ok, "unit_out": unit_out,
            "chaos_ok": chaos_ok, "chaos_out": chaos_out,
        })

        selftest_report = (
            f"unit test : {'PASS' if unit_ok else 'FAIL'}\n{unit_out}\n\n"
            f"chaos test: {'PASS' if chaos_ok else 'FAIL'}\n{chaos_out}\n")
        (work / "SELFTEST-RESULT.txt").write_text(
            f"discipline: {spec['name']}\nforged: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"verdict: {'PASS' if (unit_ok and chaos_ok) else 'FAIL'}\n\n{selftest_report}",
            encoding="utf-8")

        passed = unit_ok and chaos_ok
        result["passed"] = passed
        if not passed:
            result["promoted"] = None
            return result

        write_install_md(spec, work, selftest_report)
        target, one_liner = install_block(spec)
        result["target"] = target
        result["install_line"] = one_liner
        if not dry_run:
            result["promoted"] = str(promote(work, queue_dir, spec["name"]))
        else:
            result["promoted"] = None
        return result
    finally:
        # Clean the temp work dir unless explicitly kept - promotion already copied
        # artifacts to the queue, and on failure the chaos output was already printed.
        # (Leaving it only on failure would leak a dir per failed forge attempt.)
        if not keep_work:
            shutil.rmtree(work, ignore_errors=True)
            result["work"] = None


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="forge.py",
        description="Forge a named behavioral pattern into a self-tested, review-queued discipline (hook).")
    p.add_argument("--name", help="hyphen-case discipline name")
    p.add_argument("--event", choices=sorted(CANON), help="hook event")
    p.add_argument("--action", help="inject message (may contain {count}) or block reason for a gate")
    p.add_argument("--trigger-kind", choices=sorted(KIND_FIELD), help="how the predicate reads its source")
    p.add_argument("--trigger-regex", help="regex the source must match to fire")
    p.add_argument("--trigger-field", help="dotted payload path (trigger-kind=field)")
    p.add_argument("--fire-example", help="a sample source value the trigger SHOULD match")
    p.add_argument("--silent-example", help="a sample source value the trigger must NOT match")
    p.add_argument("--matcher", help="tool_name matcher for the install line (pre/post-tool)")
    p.add_argument("--skill-description", help="description for the SKILL stub (no angle brackets)")
    p.add_argument("--needs-state", action="store_true", help="scaffold a state/ledger schema + session dedup")
    p.add_argument("--gates", action="store_true", help="forge a blocking tripwire (exit-2 path)")
    p.add_argument("--has-procedure", action="store_true", help="emit a companion SKILL stub")
    p.add_argument("--case-sensitive", action="store_true", help="compile the trigger regex case-sensitively")
    p.add_argument("--queue-dir", default=str(DEFAULT_QUEUE), help="review-queue root (default ~/.claude/forge-queue)")
    p.add_argument("--spec", help="JSON spec file; explicit flags override its keys")
    p.add_argument("--dry-run", action="store_true", help="scaffold + self-test in a temp dir; do NOT promote")
    p.add_argument("--keep-work", action="store_true", help="keep the temp work dir for inspection")
    p.add_argument("--json", action="store_true", help="emit the result as JSON")
    return p


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    try:
        spec = build_spec(args)
        result = forge(spec, Path(args.queue_dir), dry_run=args.dry_run, keep_work=args.keep_work)
    except ValueError as exc:
        print(f"FAILED:{getattr(args, 'name', None) or '?'} spec rejected - {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - unexpected
        print(f"FAILED:{getattr(args, 'name', None) or '?'} {type(exc).__name__}: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        name = result["name"]
        print(f"unit  test : {'PASS' if result.get('unit_ok') else 'FAIL'}")
        print(f"chaos test : {'PASS' if result.get('chaos_ok') else 'FAIL'}")
        if not result.get("passed"):
            print("\n--- chaos output ---")
            print(result.get("chaos_out", ""))
            print(f"\nFAILED:{name} self-test did not pass - nothing promoted to the queue")
            return 1
        if result.get("promoted"):
            print(f"\nqueued     : {result['promoted']}")
            print(f"install via: ({result['target']}) {result['install_line']}")
            print(f"\nSUCCESS:{name} forged + self-tested; staged for review (NOT auto-wired)")
        else:
            print(f"\nSUCCESS:{name} forged + self-tested (dry-run; not promoted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
