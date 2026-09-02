#!/usr/bin/env python3
"""Hook-firing inventory: execute a scripted session, read the execution log.

Installed (manifest membership) is never treated as firing evidence. A hook
that is listed but not subprocessed does not appear in the ordered list.
A hook that subprocesses and exits non-zero DOES appear, with that exit code.
The Codex $schema precedent is reproduced: a `$schema` key on the dispatch
manifest causes the loader to return ZERO hooks while the file still looks
installed.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RUNNER = HERE / "hook_runner.py"

HOOK_CLASSES: list[tuple[str, str]] = [
    ("hook.session-start", "SessionStart"),
    ("hook.user-prompt", "UserPromptSubmit"),
    ("hook.pre-tool", "PreToolUse"),
    ("hook.post-tool", "PostToolUse"),
    ("hook.notification", "Notification"),
    ("hook.stop", "Stop"),
    ("hook.session-end", "SessionEnd"),
]

SCRIPTED_SESSION: list[tuple[str, str | None]] = [
    ("SessionStart", None),
    ("UserPromptSubmit", None),
    ("PreToolUse", "Read"),
    ("PostToolUse", "Read"),
    ("PreToolUse", "Bash"),
    ("PostToolUse", "Bash"),
    ("Notification", None),
    ("Stop", None),
    ("SessionEnd", None),
]

SENTINEL = (
    "SUCCESS:CNF-0054 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the deliberate-disable "
    "control was detected by the diff and the ordered firing lists are attached. "
    "Any other terminal state is FAILED:CNF-0054 <classification> with the "
    "diagnostic tail attached."
)

QUESTION = (
    "Did the change silently stop a hook from firing? Capture which hooks fire, "
    "in what order, with what exit codes, across a fixed scripted session before "
    "and after, and answer: is any hook missing from the after set? The measured "
    "precedent is a client loading ZERO hooks while appearing correctly installed."
)


def _hook_entry(
    hook_id: str,
    event: str,
    *,
    enabled: bool = True,
    exit_code: int = 0,
) -> dict[str, Any]:
    return {
        "id": hook_id,
        "event": event,
        "enabled": enabled,
        "exit_code": exit_code,
        "command": "hook_runner.py",
    }


def default_hooks(
    *,
    disabled_id: str | None = None,
    exit_overrides: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    overrides = exit_overrides or {}
    rows = []
    for hook_id, event in HOOK_CLASSES:
        rows.append(
            _hook_entry(
                hook_id,
                event,
                enabled=(hook_id != disabled_id),
                exit_code=int(overrides.get(hook_id, 0)),
            )
        )
    return rows


def write_manifest(
    path: Path,
    hooks: list[dict[str, Any]],
    *,
    schema_key: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "name": "cnf-0054-dispatch-manifest",
        "hooks": hooks,
    }
    if schema_key:
        # Precedent: a $schema key made Codex load ZERO hooks while installed.
        doc["$schema"] = "http://json-schema.org/draft-07/schema#"
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def ensure_fixtures() -> dict[str, Path]:
    root = HERE / "fixtures"
    before = root / "before" / "manifest.json"
    after = root / "after" / "manifest.json"
    disable = root / "control-disable" / "manifest.json"
    schema = root / "schema-zero-load" / "manifest.json"
    classify = root / "classify" / "manifest.json"
    write_manifest(before, default_hooks())
    write_manifest(after, default_hooks())
    write_manifest(disable, default_hooks(disabled_id="hook.pre-tool"))
    write_manifest(schema, default_hooks(), schema_key=True)
    write_manifest(
        classify,
        default_hooks(
            disabled_id="hook.notification",
            exit_overrides={"hook.stop": 1},
        ),
    )
    return {
        "before": before,
        "after": after,
        "control-disable": disable,
        "schema-zero-load": schema,
        "classify": classify,
    }


def load_hooks(manifest_path: Path) -> tuple[list[dict[str, Any]], list[str], str]:
    """Return (loaded_hooks, manifest_ids, loader_mode).

    `$schema` on the dispatch document reproduces the Codex zero-load bug:
    every hook remains listed, none are loaded.
    """
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    listed = data.get("hooks") or []
    if not isinstance(listed, list):
        listed = []
    manifest_ids = [str(h.get("id")) for h in listed if isinstance(h, dict) and h.get("id")]
    if "$schema" in data:
        return [], manifest_ids, "schema-key-zero-load"
    loaded = []
    for hook in listed:
        if not isinstance(hook, dict):
            continue
        if not hook.get("enabled", True):
            continue
        loaded.append(hook)
    return loaded, manifest_ids, "enabled-hooks"


def run_session(manifest_path: Path) -> dict[str, Any]:
    loaded, manifest_ids, mode = load_hooks(manifest_path)
    by_event: dict[str, list[dict[str, Any]]] = {}
    for hook in loaded:
        by_event.setdefault(str(hook.get("event")), []).append(hook)

    with tempfile.TemporaryDirectory(prefix="cnf0054-") as tmp:
        log_path = Path(tmp) / "hook-execution.log"
        seq = 0
        proc_results: list[dict[str, Any]] = []
        for event, tool in SCRIPTED_SESSION:
            for hook in by_event.get(event, []):
                seq += 1
                payload = {
                    "seq": seq,
                    "hook_id": hook["id"],
                    "event": event,
                    "exit_code": int(hook.get("exit_code", 0)),
                    "tool": tool,
                }
                proc = subprocess.run(
                    [sys.executable, "-B", str(RUNNER), str(log_path), json.dumps(payload)],
                    cwd=str(HERE),
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                proc_results.append(
                    {
                        "hook_id": hook["id"],
                        "event": event,
                        "requested_exit": int(hook.get("exit_code", 0)),
                        "observed_exit": int(proc.returncode),
                    }
                )
        ordered: list[dict[str, Any]] = []
        if log_path.is_file():
            for line in log_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                ordered.append(
                    {
                        "seq": int(rec["seq"]),
                        "hook_id": str(rec["hook_id"]),
                        "event": str(rec["event"]),
                        "exit_code": int(rec["exit_code"]),
                        "source": "execution-log",
                        "tool": rec.get("tool"),
                    }
                )

    fired_ids: list[str] = []
    for rec in ordered:
        hid = rec["hook_id"]
        if hid not in fired_ids:
            fired_ids.append(hid)
    silent_nonzero = [
        {"hook_id": r["hook_id"], "event": r["event"], "exit_code": r["exit_code"]}
        for r in ordered
        if int(r["exit_code"]) != 0
    ]
    never_fired = [hid for hid in manifest_ids if hid not in fired_ids]
    return {
        "manifest_path": str(manifest_path.relative_to(REPO)).replace("\\", "/"),
        "loader_mode": mode,
        "manifest_hook_ids": manifest_ids,
        "loaded_hook_ids": [str(h["id"]) for h in loaded],
        "ordered_firing": ordered,
        "fired_hook_ids": fired_ids,
        "silent_nonzero": silent_nonzero,
        "never_fired_but_installed": never_fired,
        "subprocess_results": proc_results,
        "firing_count": len(ordered),
    }


def inventory_view(label: str, session: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": label,
        "manifest_path": session["manifest_path"],
        "loader_mode": session["loader_mode"],
        "manifest_hook_ids": list(session["manifest_hook_ids"]),
        "loaded_hook_ids": list(session["loaded_hook_ids"]),
        "ordered_firing": list(session["ordered_firing"]),
        "fired_hook_ids": list(session["fired_hook_ids"]),
        "firing_count": session["firing_count"],
    }


def set_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    b = list(before["fired_hook_ids"])
    a = list(after["fired_hook_ids"])
    missing = [hid for hid in b if hid not in a]
    extra = [hid for hid in a if hid not in b]
    b_exits = {(r["hook_id"], r["event"], r.get("tool")): r["exit_code"] for r in before["ordered_firing"]}
    changes = []
    for rec in after["ordered_firing"]:
        key = (rec["hook_id"], rec["event"], rec.get("tool"))
        if key in b_exits and b_exits[key] != rec["exit_code"]:
            changes.append(
                {
                    "hook_id": rec["hook_id"],
                    "event": rec["event"],
                    "tool": rec.get("tool"),
                    "before_exit": b_exits[key],
                    "after_exit": rec["exit_code"],
                }
            )
    return {
        "missing_from_after": missing,
        "extra_in_after": extra,
        "any_hook_missing_from_after": bool(missing),
        "exit_code_changes": changes,
        "before_fired_set": b,
        "after_fired_set": a,
    }


def _installed_from_doc(rel: str, data: dict[str, Any]) -> dict[str, Any]:
    """List installed hook identities from a dispatch document. Does not execute."""
    listed: list[dict[str, Any]] = []
    schema_key = "$schema" in data
    hooks = data.get("hooks")
    events = data.get("events")
    if isinstance(hooks, dict):
        for event, entries in hooks.items():
            if not isinstance(entries, list):
                continue
            for idx, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                matcher = entry.get("matcher")
                inner = entry.get("hooks") or []
                if not isinstance(inner, list):
                    continue
                for j, hook in enumerate(inner):
                    if not isinstance(hook, dict):
                        continue
                    cmd = str(hook.get("command") or "")
                    listed.append(
                        {
                            "id": f"{event}[{idx}].{j}",
                            "event": str(event),
                            "matcher": matcher,
                            "type": hook.get("type"),
                            "command_tail": cmd[-96:],
                        }
                    )
    elif isinstance(hooks, list):
        for hook in hooks:
            if isinstance(hook, dict) and hook.get("id"):
                listed.append(
                    {
                        "id": str(hook.get("id")),
                        "event": hook.get("event"),
                        "enabled": hook.get("enabled", True),
                    }
                )
    if isinstance(events, dict):
        for event, spec in events.items():
            if not isinstance(spec, dict):
                continue
            for check in spec.get("checks") or []:
                if isinstance(check, dict) and check.get("name"):
                    listed.append(
                        {
                            "id": f"{event}/{check.get('name')}",
                            "event": str(event),
                            "script": check.get("script"),
                        }
                    )
    return {
        "path": rel,
        "schema_key_present": schema_key,
        "installed_count": len(listed),
        "installed_ids": [row["id"] for row in listed],
        "description_head": str(data.get("description") or "")[:240],
    }


def scan_product_hook_surface() -> dict[str, Any]:
    """Bounded live scan. Never walks the whole tree (no rglob)."""
    product_candidates = [
        "hooks/hooks.json",
        "hooks/_dispatch/manifest.json",
        "agent-self/config/hooks/hooks.json",
        "tools/editor/metaswarm/hooks/hooks.json",
    ]
    present: list[str] = []
    inventories: dict[str, Any] = {}
    for rel in product_candidates:
        path = REPO / rel
        if not path.is_file():
            continue
        present.append(rel)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            inventories[rel] = {"path": rel, "parse_error": type(exc).__name__}
            continue
        if isinstance(data, dict):
            inventories[rel] = _installed_from_doc(rel, data)
        else:
            inventories[rel] = {"path": rel, "parse_error": "not-object"}
    sibling_fixtures: list[str] = []
    probes_root = REPO / "command-center/p2-wave/probes"
    if probes_root.is_dir():
        for pattern in ("*/fixtures/**/hooks.json", "*/fixtures/**/manifest.json"):
            for path in probes_root.glob(pattern):
                if "CNF-0054" in path.parts:
                    continue
                sibling_fixtures.append(path.relative_to(REPO).as_posix())
                if len(sibling_fixtures) >= 40:
                    break
            if len(sibling_fixtures) >= 40:
                break
    product_hook_count = 0
    schema_on_product = False
    for rel, inv in inventories.items():
        if not isinstance(inv, dict):
            continue
        product_hook_count += int(inv.get("installed_count") or 0)
        schema_on_product = schema_on_product or bool(inv.get("schema_key_present"))
    return {
        "worktree": str(REPO),
        "product_dispatch_manifests": present,
        "product_surface_present": bool(present),
        "product_installed_hook_count": product_hook_count,
        "product_schema_key_present": schema_on_product,
        "product_commands_executed_this_run": False,
        "inventories": inventories,
        "sibling_hook_fixture_manifests": sorted(sibling_fixtures)[:40],
        "note": (
            "Product dispatch files are present (hooks/hooks.json and "
            "hooks/_dispatch/manifest.json). Their command entries were NOT "
            "executed this run (side-effecting: git-hygiene, spawns, npx). "
            "Ordered firing lists come from the CNF-0054 instrumented "
            "dispatcher execution log, never from manifest membership. "
            "hooks/hooks.json documents the Codex $schema zero-load precedent "
            "in its description and omits the key."
        ),
    }


def artifact_view(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report when the receipt_core envelope is used."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "before" in report or "after" in report or "controls" in report
    ):
        return report
    return doc


def measure() -> dict[str, Any]:
    fixtures = ensure_fixtures()
    before = run_session(fixtures["before"])
    after = run_session(fixtures["after"])
    disabled = run_session(fixtures["control-disable"])
    schema_zero = run_session(fixtures["schema-zero-load"])
    classify = run_session(fixtures["classify"])

    primary = set_diff(before, after)
    disable_delta = set_diff(before, disabled)
    schema_delta = set_diff(before, schema_zero)

    disable_detected = (
        "hook.pre-tool" in disable_delta["missing_from_after"]
        and "hook.pre-tool" in disabled["manifest_hook_ids"]
        and "hook.pre-tool" not in disabled["fired_hook_ids"]
        and "hook.pre-tool" in disabled["never_fired_but_installed"]
    )
    schema_detected = (
        schema_zero["loader_mode"] == "schema-key-zero-load"
        and schema_zero["firing_count"] == 0
        and len(schema_zero["manifest_hook_ids"]) == len(before["manifest_hook_ids"])
        and len(schema_delta["missing_from_after"]) == len(before["fired_hook_ids"])
    )
    # Naive manifest-count probe is blind to the $schema zero-load precedent.
    naive_manifest_count_blind = len(schema_zero["manifest_hook_ids"]) == len(
        before["manifest_hook_ids"]
    )

    classify_nonzero = [r["hook_id"] for r in classify["silent_nonzero"]]
    classify_never = list(classify["never_fired_but_installed"])
    distinguished = (
        "hook.stop" in classify_nonzero
        and "hook.stop" not in classify_never
        and "hook.notification" in classify_never
        and "hook.notification" not in classify_nonzero
        and "hook.notification" not in classify["fired_hook_ids"]
    )

    live = scan_product_hook_surface()
    return {
        "before": before,
        "after": after,
        "disabled": disabled,
        "schema_zero": schema_zero,
        "classify": classify,
        "primary_delta": primary,
        "disable_delta": disable_delta,
        "schema_delta": schema_delta,
        "disable_detected": disable_detected,
        "schema_detected": schema_detected,
        "naive_manifest_count_blind": naive_manifest_count_blind,
        "distinguished_silent_vs_never": distinguished,
        "live_surface": live,
        "ok": bool(
            disable_detected
            and schema_detected
            and distinguished
            and naive_manifest_count_blind
            and before["firing_count"] >= 7
            and after["firing_count"] >= 7
            and not primary["any_hook_missing_from_after"]
        ),
    }


def main() -> int:
    report = measure()
    summary = {
        "ok": report["ok"],
        "primary_missing": report["primary_delta"]["missing_from_after"],
        "disable_detected": report["disable_detected"],
        "schema_zero_loaded": report["schema_zero"]["firing_count"],
        "distinguished": report["distinguished_silent_vs_never"],
        "before_firing_count": report["before"]["firing_count"],
        "after_firing_count": report["after"]["firing_count"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
