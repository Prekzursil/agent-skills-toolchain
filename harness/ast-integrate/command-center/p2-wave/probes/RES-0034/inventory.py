#!/usr/bin/env python3
"""Run the same tasks on two vendor rails; classify leaks vs control."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from rails import CLAUDE, CODEX, RAIL_IDS, run_rail

HERE = Path(__file__).resolve().parent

TASKS: tuple[dict[str, Any], ...] = (
    {
        "id": "leak-hooks-unknown-key",
        "kind": "leak",
        "handler": "hooks",
        "root": "fixtures/leak-hooks",
        "task": (
            "Load hooks.json and report the armed hook ids. The file carries "
            "a $schema key plus one PreToolUse hook."
        ),
        "loud_degradation": (
            "Adapter MUST NOT treat an empty Codex hook inventory as "
            "'hooks are not configured'. Emit DEGRADED, name "
            "leak-hooks-unknown-key, and preserve both inventories."
        ),
    },
    {
        "id": "leak-instruction-locator",
        "kind": "leak",
        "handler": "instructions",
        "root": "fixtures/leak-instructions",
        "task": (
            "Read the unit instruction file and report the MUST-NOT token. "
            "Both CLAUDE.md and AGENTS.md are present with different tokens."
        ),
        "loud_degradation": (
            "Adapter MUST NOT pick one MUST-NOT token as portable policy. "
            "Emit DEGRADED, name leak-instruction-locator, list files read "
            "per vendor, and preserve both tokens."
        ),
    },
    {
        "id": "leak-plugin-discovery-path",
        "kind": "leak",
        "handler": "plugins",
        "root": "fixtures/leak-plugin",
        "task": (
            "Enumerate loaded plugin ids. The plugin exists only at "
            ".claude-plugin/plugin.json."
        ),
        "loud_degradation": (
            "Adapter MUST NOT treat a missing Codex plugin list as "
            "'this unit has no plugins'. Emit DEGRADED, name "
            "leak-plugin-discovery-path, list search paths, and preserve "
            "both inventories."
        ),
    },
    {
        "id": "control-portable-json",
        "kind": "control",
        "handler": "portable",
        "root": "fixtures/control",
        "task": (
            "Parse portable.json containing only name and version, the "
            "documented portable core for this pair of JSON loaders."
        ),
        "loud_degradation": (
            "Not a leak. Both rails must agree; adapter may treat the "
            "shared name/version as portable."
        ),
    },
)


class OverclaimError(RuntimeError):
    pass


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_answer(handler: str, output: dict[str, Any]) -> Any:
    """The correct-looking portable result an adapter would be tempted to take."""
    if handler == "hooks":
        return {"ok": output.get("ok"), "armed_hook_ids": output.get("armed_hook_ids")}
    if handler == "instructions":
        return {
            "ok": output.get("ok"),
            "must_not": output.get("must_not"),
            "found": output.get("found"),
        }
    if handler == "plugins":
        return {"ok": output.get("ok"), "plugin_ids": output.get("plugin_ids")}
    if handler == "portable":
        return {
            "ok": output.get("ok"),
            "name": output.get("name"),
            "version": output.get("version"),
        }
    raise OverclaimError(f"unknown handler {handler}")


def loud_degrade(task_id: str, claude_ans: Any, codex_ans: Any) -> dict[str, Any]:
    if canonical(claude_ans) == canonical(codex_ans):
        return {
            "verdict": "PORTABLE",
            "result": deepcopy(claude_ans),
            "task_id": task_id,
        }
    return {
        "verdict": "DEGRADED",
        "reason": f"abstraction-leak:{task_id}",
        "task_id": task_id,
        "vendor_outputs": {
            CLAUDE: deepcopy(claude_ans),
            CODEX: deepcopy(codex_ans),
        },
        "adapter_must_not": "select either output as the portable result",
        "adapter_must": "emit DEGRADED and preserve both captured outputs",
    }


def run_task(
    task: dict[str, Any],
    *,
    codex_hooks_fail_closed: bool = True,
) -> dict[str, Any]:
    root = HERE / str(task["root"])
    kwargs_by_rail: dict[str, dict[str, Any]] = {CLAUDE: {}, CODEX: {}}
    if task["handler"] == "hooks":
        kwargs_by_rail[CODEX] = {"fail_closed": codex_hooks_fail_closed}
    outputs: dict[str, Any] = {}
    for rail in RAIL_IDS:
        outputs[rail] = run_rail(
            rail, str(task["handler"]), root, **kwargs_by_rail[rail]
        )
    claude_out = outputs[CLAUDE]
    codex_out = outputs[CODEX]
    handler = str(task["handler"])
    claude_ans = extract_answer(handler, claude_out)
    codex_ans = extract_answer(handler, codex_out)
    divergent = canonical(claude_ans) != canonical(codex_ans)
    return {
        "id": task["id"],
        "kind": task["kind"],
        "task": task["task"],
        "loud_degradation_spec": task["loud_degradation"],
        "root": str(task["root"]),
        "handler": handler,
        "claude": claude_out,
        "codex": codex_out,
        "claude_answer": claude_ans,
        "codex_answer": codex_ans,
        "rails": [CLAUDE, CODEX],
        "divergent": divergent,
        "output_sha256": {
            CLAUDE: sha256_text(canonical(claude_ans)),
            CODEX: sha256_text(canonical(codex_ans)),
        },
        "loud_degradation": loud_degrade(str(task["id"]), claude_ans, codex_ans),
    }


def capture_all(*, codex_hooks_fail_closed: bool = True) -> list[dict[str, Any]]:
    return [
        run_task(task, codex_hooks_fail_closed=codex_hooks_fail_closed)
        for task in TASKS
    ]


def assert_inventory(pairs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """A leak without both captured outputs is not a leak (overclaim)."""
    leaks: list[dict[str, Any]] = []
    controls: list[dict[str, Any]] = []
    for pair in pairs:
        pid = str(pair.get("id") or "<missing>")
        kind = str(pair.get("kind") or "")
        claude = pair.get("claude")
        codex = pair.get("codex")
        has_both = claude is not None and codex is not None
        if kind == "leak":
            if not has_both:
                raise OverclaimError(
                    f"leak {pid} asserted without a captured divergent pair"
                )
            if not pair.get("divergent"):
                raise OverclaimError(
                    f"leak {pid} outputs agree; that is not a leak"
                )
            leaks.append(pair)
        elif kind == "control":
            if not has_both:
                raise OverclaimError(f"control {pid} missing a captured pair")
            if pair.get("divergent"):
                raise OverclaimError(
                    f"control {pid} diverged; the agreeing control failed"
                )
            controls.append(pair)
        else:
            raise OverclaimError(f"unknown pair kind {kind!r} for {pid}")
    if len(leaks) < 3:
        raise OverclaimError(f"need at least 3 leaks, got {len(leaks)}")
    if len(controls) < 1:
        raise OverclaimError("need one agreeing control pair")
    return leaks, controls


def snapshot_sha256(pairs: list[dict[str, Any]]) -> str:
    blob = canonical(
        [
            {
                "id": p["id"],
                "kind": p["kind"],
                "divergent": p["divergent"],
                "output_sha256": p["output_sha256"],
            }
            for p in pairs
        ]
    )
    return sha256_text(blob)


def main() -> int:
    pairs = capture_all()
    leaks, controls = assert_inventory(pairs)
    print(f"leaks={len(leaks)} controls={len(controls)} snapshot={snapshot_sha256(pairs)}")
    for pair in pairs:
        print(
            f"{pair['id']} kind={pair['kind']} divergent={pair['divergent']} "
            f"loud={pair['loud_degradation']['verdict']}"
        )
    print("SUCCESS:RES-0034-inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
