#!/usr/bin/env python3
"""Live inventory: undocumented env/flags/subcommands the installed client honours."""
from __future__ import annotations

import json
import os
from pathlib import Path

from client import bundled_index, describe_client
from delta import compare_runs, redact, run_cmd, scratch_dir
from extract import harvest, load_published, parse_help_surface
from wrapper_harness import prepare_wrapper_sandbox, run_wrapper

HERE = Path(__file__).resolve().parent
INVENTED_ENV = "RES0021_INVENTED_FLAG"
INVENTED_CLI = "--res0021-invented-flag"
INVENTED_CMD = "res0021-invented-cmd"


def _pub_sets() -> tuple[set[str], set[str], set[str]]:
    pub = load_published()
    return set(pub["env"]), set(pub["flags"]), set(pub["commands"])


def _in_help(help_text: str, token: str) -> bool:
    return token in help_text


def _unknown_rejection(run: dict) -> bool:
    blob = f"{run.get('stderr') or ''}\n{run.get('stdout') or ''}".lower()
    needles = (
        "unknown option",
        "unknown command",
        "invalid option",
        "unexpected argument",
        "error: unknown",
        "unrecognized option",
    )
    return any(n in blob for n in needles)


def _credential_store_delta(launcher: Path) -> dict:
    root = prepare_wrapper_sandbox(launcher)
    off = run_wrapper(root, None, pop=("AGENT_CLI_CREDENTIAL_STORE",))
    on = run_wrapper(root, {"AGENT_CLI_CREDENTIAL_STORE": "file"})
    delta = off["use_system_ca_count"] != on["use_system_ca_count"]
    return {
        "kind": "env",
        "name": "AGENT_CLI_CREDENTIAL_STORE",
        "off": {
            "rc": off["rc"],
            "use_system_ca_count": off["use_system_ca_count"],
            "argv_sample": off["argv_flat"][:8],
        },
        "on": {
            "rc": on["rc"],
            "use_system_ca_count": on["use_system_ca_count"],
            "argv_sample": on["argv_flat"][:8],
            "value": "file",
        },
        "delta": delta,
        "reasons": (
            [
                f"stub-node --use-system-ca count {off['use_system_ca_count']} -> {on['use_system_ca_count']}"
            ]
            if delta
            else ["wrapper exec argv unchanged"]
        ),
        "unknown_rejection": False,
    }


def _cache_dir_delta(launcher: Path) -> dict:
    root = prepare_wrapper_sandbox(launcher)
    custom = str(scratch_dir("res0021-ncc-"))
    off = run_wrapper(root, None, pop=("NODE_COMPILE_CACHE",))
    on = run_wrapper(root, {"NODE_COMPILE_CACHE": custom})
    off_ncc = [x for x in off["ncc"] if x]
    on_ncc = [x for x in on["ncc"] if x]
    delta = bool(on_ncc) and bool(off_ncc) and on_ncc[0] == custom and off_ncc[0] != custom
    return {
        "kind": "env",
        "name": "NODE_COMPILE_CACHE",
        "off": {"rc": off["rc"], "ncc": off_ncc[:1]},
        "on": {"rc": on["rc"], "ncc": on_ncc[:1], "custom_dir": custom},
        "delta": delta,
        "reasons": (
            [f"wrapper exported NODE_COMPILE_CACHE {off_ncc[:1]} -> {on_ncc[:1]}"]
            if delta
            else ["compile-cache path not redirected"]
        ),
        "unknown_rejection": False,
    }


def _xdg_cache_delta(launcher: Path) -> dict:
    root = prepare_wrapper_sandbox(launcher)
    custom = str(scratch_dir("res0021-xdg-"))
    off = run_wrapper(root, None, pop=("NODE_COMPILE_CACHE", "XDG_CACHE_HOME"))
    on = run_wrapper(
        root,
        {"XDG_CACHE_HOME": custom},
        pop=("NODE_COMPILE_CACHE",),
    )
    off_ncc = [x for x in off["ncc"] if x]
    on_ncc = [x for x in on["ncc"] if x]
    expected = str(Path(custom) / "cursor-compile-cache")
    delta = bool(on_ncc) and on_ncc[0] == expected
    return {
        "kind": "env",
        "name": "XDG_CACHE_HOME",
        "off": {"rc": off["rc"], "ncc": off_ncc[:1]},
        "on": {"rc": on["rc"], "ncc": on_ncc[:1], "expected": expected},
        "delta": delta,
        "reasons": (
            [f"wrapper derived NODE_COMPILE_CACHE={expected} from XDG_CACHE_HOME"]
            if delta
            else ["XDG_CACHE_HOME did not redirect compile-cache path"]
        ),
        "unknown_rejection": False,
    }


def _invoked_as_delta(launcher: Path) -> dict:
    root = prepare_wrapper_sandbox(launcher)
    off = run_wrapper(root, None, pop=("CURSOR_INVOKED_AS",))
    on = run_wrapper(root, {"CURSOR_INVOKED_AS": "res0021-probe"})
    off_v = off["invoked_as"][:1]
    on_v = on["invoked_as"][:1]
    delta = off_v != on_v
    return {
        "kind": "env",
        "name": "CURSOR_INVOKED_AS",
        "off": {"rc": off["rc"], "invoked_as": off_v},
        "on": {"rc": on["rc"], "invoked_as": on_v},
        "delta": delta,
        "reasons": (
            [f"CURSOR_INVOKED_AS {off_v} -> {on_v}"]
            if delta
            else ["wrapper overwrote incoming CURSOR_INVOKED_AS from basename"]
        ),
        "unknown_rejection": False,
    }


def _config_dir_delta(launcher: Path) -> dict:
    bad = scratch_dir("res0021-cfg-bad-")
    (bad / "cli-config.json").write_text("{not-json", encoding="utf-8")
    good = scratch_dir("res0021-cfg-ok-")
    (good / "cli-config.json").write_text(
        json.dumps(
            {
                "version": 1,
                "editor": {"vimMode": False},
                "permissions": {"allow": [], "deny": []},
            }
        ),
        encoding="utf-8",
    )
    env_bad = os.environ.copy()
    env_bad["CURSOR_CONFIG_DIR"] = str(bad)
    env_ok = os.environ.copy()
    env_ok["CURSOR_CONFIG_DIR"] = str(good)
    off = run_cmd([str(launcher), "about", "--format", "json"], env=env_ok, timeout=30)
    on = run_cmd([str(launcher), "about", "--format", "json"], env=env_bad, timeout=30)
    cmp = compare_runs(off, on)
    return {
        "kind": "env",
        "name": "CURSOR_CONFIG_DIR",
        "off": {"rc": off["rc"], "fp": off["fingerprint"]},
        "on": {"rc": on["rc"], "fp": on["fingerprint"]},
        "delta": cmp["delta"],
        "reasons": cmp["reasons"] or ["about json identical for good vs broken config"],
        "unknown_rejection": False,
    }


def _plain_env_delta(launcher: Path, name: str, value: str) -> dict:
    if name == INVENTED_ENV:
        root = prepare_wrapper_sandbox(launcher)
        off = run_wrapper(root, None, pop=(INVENTED_ENV,))
        on = run_wrapper(root, {INVENTED_ENV: value})
        delta = off["argv_flat"] != on["argv_flat"] or off["ncc"] != on["ncc"]
        return {
            "kind": "env",
            "name": name,
            "off": {"rc": off["rc"], "argv": off["argv_flat"][:6], "ncc": off["ncc"][:1]},
            "on": {"rc": on["rc"], "argv": on["argv_flat"][:6], "ncc": on["ncc"][:1]},
            "delta": delta,
            "reasons": (
                ["wrapper argv or compile-cache path changed"]
                if delta
                else ["invented env did not change wrapper argv or compile-cache path"]
            ),
            "unknown_rejection": False,
        }
    env_off = os.environ.copy()
    env_off.pop(name, None)
    env_on = os.environ.copy()
    env_on[name] = value
    off = run_cmd([str(launcher), "--version"], env=env_off, timeout=20)
    on = run_cmd([str(launcher), "--version"], env=env_on, timeout=20)
    cmp = compare_runs(off, on)
    return {
        "kind": "env",
        "name": name,
        "off": {"rc": off["rc"], "fp": off["fingerprint"]},
        "on": {"rc": on["rc"], "fp": on["fingerprint"]},
        "delta": cmp["delta"],
        "reasons": cmp["reasons"] or ["--version fingerprint identical"],
        "unknown_rejection": False,
    }


def _flag_delta(launcher: Path, flag: str) -> dict:
    off = run_cmd([str(launcher), "--version"], env=None, timeout=8)
    on = run_cmd([str(launcher), flag, "--version"], env=None, timeout=8)
    cmp = compare_runs(off, on)
    rej = _unknown_rejection(on)
    return {
        "kind": "flag",
        "name": flag,
        "off": {"rc": off["rc"], "fp": off["fingerprint"]},
        "on": {"rc": on["rc"], "fp": on["fingerprint"], "stderr_tail": on["stderr"][-400:]},
        "delta": cmp["delta"],
        "reasons": cmp["reasons"] or ["--version fingerprint identical"],
        "unknown_rejection": rej,
    }


def _cmd_delta(launcher: Path, cmd: str) -> dict:
    off = run_cmd([str(launcher), "help"], env=None, timeout=8)
    on = run_cmd([str(launcher), cmd, "--help"], env=None, timeout=8)
    cmp = compare_runs(off, on)
    rej = _unknown_rejection(on)
    return {
        "kind": "subcommand",
        "name": cmd,
        "off": {"rc": off["rc"], "fp": off["fingerprint"]},
        "on": {"rc": on["rc"], "fp": on["fingerprint"], "stderr_tail": on["stderr"][-400:]},
        "delta": cmp["delta"],
        "reasons": cmp["reasons"] or ["help fingerprint identical"],
        "unknown_rejection": rej,
    }


def classify(row: dict, pub_env: set[str], pub_flags: set[str], pub_cmds: set[str], help_text: str) -> dict:
    name = row["name"]
    in_docs = (
        name in pub_env or name in pub_flags or name in pub_cmds or name.lstrip("-") in pub_cmds
    )
    help_hit = _in_help(help_text, name)
    honouring = bool(row["delta"]) and not row.get("unknown_rejection")
    on_rc = (row.get("on") or {}).get("rc")
    if on_rc == 124 and row.get("kind") in {"flag", "subcommand"}:
        honouring = False
        row.setdefault("reasons", []).append("timed out; not counted as honour")
    if honouring and in_docs:
        status = "documented"
    elif honouring and not in_docs:
        status = "honoured"
    else:
        status = "string-only"
    return {
        **row,
        "in_published_docs": in_docs,
        "in_help": help_hit,
        "status": status,
        "behaviour_delta": {
            "observed": honouring,
            "reasons": row.get("reasons") or [],
            "unknown_rejection": bool(row.get("unknown_rejection")),
            "off": row.get("off"),
            "on": row.get("on"),
        },
    }


def design_impact(row: dict) -> dict:
    name = row["name"]
    status = row["status"]
    if status != "honoured":
        return {
            "would_change_design_if_relied_upon": False,
            "rationale": (
                "Not classified honoured on this worktree; relying on it would be "
                "an unmeasured dependency."
                if status == "string-only"
                else "Published/documented surface; already an explicit dependency class."
            ),
        }
    impacts = {
        "AGENT_CLI_CREDENTIAL_STORE": (
            True,
            "Value `file` skips Node --use-system-ca on the wrapper exec. A runner "
            "that assumed OS trust-store CAs would silently lose enterprise MITM/CA "
            "injection. This program's dispatcher must not treat that skip as a stable API.",
        ),
        "NODE_COMPILE_CACHE": (
            True,
            "Redirects the wrapper's Node compile-cache directory. A hermetic runner "
            "that did not pin this would share or lose startup cache across jobs.",
        ),
        "XDG_CACHE_HOME": (
            True,
            "When NODE_COMPILE_CACHE is unset, the wrapper derives the cache path "
            "from XDG_CACHE_HOME. Isolation assumptions that only unset NODE_* would fail.",
        ),
        "CURSOR_INVOKED_AS": (
            False,
            "Wrapper overwrites from basename; env injection through `agent` is inert.",
        ),
    }
    if name in impacts:
        change, why = impacts[name]
        return {"would_change_design_if_relied_upon": change, "rationale": why}
    return {
        "would_change_design_if_relied_upon": True,
        "rationale": (
            f"Undocumented honoured {row['kind']} {name!r} is not a contract this "
            "program may take as stable without pinning and a probe."
        ),
    }


def measure() -> dict:
    info = describe_client()
    if not info.get("present"):
        return {"ok": False, "client": info, "error": "no-installed-client"}
    launcher = Path(info["launcher"])
    idx = Path(info["index_js"]) if info.get("index_js") else bundled_index(launcher)
    harvested = harvest(launcher, None)
    harvested["index_js"] = str(idx) if idx else None
    if idx and idx.is_file():
        harvested["index_bytes"] = idx.stat().st_size
    help_run = run_cmd([str(launcher), "--help"], env=None, timeout=8)
    ver_run = run_cmd([str(launcher), "--version"], env=None, timeout=8)
    help_text = help_run["stdout"] + "\n" + help_run["stderr"]
    help_surface = parse_help_surface(help_text)
    pub_env, pub_flags, pub_cmds = _pub_sets()

    raw_rows = [
        _credential_store_delta(launcher),
        _cache_dir_delta(launcher),
        _xdg_cache_delta(launcher),
        _invoked_as_delta(launcher),
        _plain_env_delta(launcher, INVENTED_ENV, "1"),
        _flag_delta(launcher, INVENTED_CLI),
        _cmd_delta(launcher, INVENTED_CMD),
    ]

    candidates = []
    for row in raw_rows:
        classified = classify(row, pub_env, pub_flags, pub_cmds, help_text)
        classified["design_impact"] = design_impact(classified)
        classified["string_in_binary"] = (
            classified["name"] in harvested["wrapper_env"]
            or classified["name"] in harvested["js_env"]
            or classified["name"] in (harvested.get("js_flags_sample") or [])
            or classified["name"] in {INVENTED_ENV, INVENTED_CLI, INVENTED_CMD}
        )
        if classified["name"] in {INVENTED_ENV, INVENTED_CLI, INVENTED_CMD}:
            classified["role"] = "negative-control"
            classified["unconfirmed"] = True
            if classified.get("unknown_rejection") or not classified["behaviour_delta"]["observed"]:
                classified["status"] = "string-only"
        else:
            classified["role"] = "candidate"
            classified["unconfirmed"] = classified["status"] == "string-only"
        candidates.append(classified)

    invented_env = next(c for c in candidates if c["name"] == INVENTED_ENV)
    honoured = [c for c in candidates if c["status"] == "honoured"]
    return {
        "ok": True,
        "client": info,
        "client_version_text": redact(ver_run["stdout"] or ver_run["stderr"]).strip()[:200],
        "help": {
            "rc": help_run["rc"],
            "flags": help_surface["flags"],
            "commands": help_surface["commands"],
            "bytes": help_run["stdout_len"] + help_run["stderr_len"],
        },
        "harvest": harvested,
        "published_docs": {
            "fetched_at": load_published()["fetched_at"],
            "sources": load_published()["sources"],
        },
        "candidates": candidates,
        "counts": {
            "honoured": len(honoured),
            "string_only": sum(1 for c in candidates if c["status"] == "string-only"),
            "documented": sum(1 for c in candidates if c["status"] == "documented"),
        },
        "negative_control": {
            "name": INVENTED_ENV,
            "delta": invented_env["delta"],
            "observed_honour": invented_env["behaviour_delta"]["observed"],
            "pass": not invented_env["behaviour_delta"]["observed"],
        },
    }


if __name__ == "__main__":
    doc = measure()
    print(json.dumps({k: doc[k] for k in ("ok", "client", "counts", "negative_control") if k in doc}, indent=2))
    if not doc.get("ok"):
        raise SystemExit(1)
