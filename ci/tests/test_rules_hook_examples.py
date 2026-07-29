"""Every hook JSON example in `rules/**/hooks.md` must be structurally VALID.

A hook entry has three nesting levels — event -> matcher group ->
``hooks: [{"type": "command", …}]`` — and the builder that writes the live config
emits exactly that (``agent-self/harness/registration.py:82-102``). A ``command``
placed directly on the matcher group is not a recognized handler: the config is
invalid and the hook NEVER FIRES, with no error. A copy-pasteable example in the
"how to write a hook" rule that silently does nothing is worse than no example.

Second check: the examples must not reference ``$FILE_PATH``. Hooks receive
``tool_input.file_path`` as JSON on stdin; nothing exports that shell variable, so
a command interpolating it runs against an empty path.

Both checks carry a KNOWN-BROKEN control (``test_detector_fires_on_*``) so a green
run cannot mean "the detector matched nothing".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
# Both roots: `rules/` and the deploy mirror under `agent-self/config/rules/`.
HOOK_RULES = sorted(
    set(REPO.glob("rules/**/hooks.md"))
    | set(REPO.glob("agent-self/config/rules/**/hooks.md"))
)
_JSON_FENCE = re.compile(r"```json\n(.*?)```", re.DOTALL)


def _json_blocks(text: str) -> list[dict]:
    return [json.loads(m.group(1)) for m in _JSON_FENCE.finditer(text)]


def _flat_command_groups(doc: dict) -> list[str]:
    """Matcher groups carrying a bare ``command`` / lacking a typed handler."""
    bad: list[str] = []
    for event, groups in (doc.get("hooks") or {}).items():
        for idx, group in enumerate(groups):
            where = f"{event}[{idx}]"
            if "command" in group:
                bad.append(f"{where}: bare 'command' on the matcher group")
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list) or not handlers:
                bad.append(f"{where}: no 'hooks' handler array")
                continue
            for h_idx, handler in enumerate(handlers):
                if handler.get("type") != "command":
                    bad.append(f"{where}.hooks[{h_idx}]: missing type='command'")
                elif not handler.get("command"):
                    bad.append(f"{where}.hooks[{h_idx}]: empty command")
    return bad


def test_hook_rule_files_are_discovered():
    """Detector control: the glob must actually find the documents."""
    assert len(HOOK_RULES) >= 4, [str(p) for p in HOOK_RULES]


@pytest.mark.parametrize("path", HOOK_RULES, ids=lambda p: str(p.relative_to(REPO)))
def test_every_hook_example_uses_the_nested_typed_handler(path: Path):
    text = path.read_text(encoding="utf-8")
    blocks = _json_blocks(text)
    problems = [p for doc in blocks for p in _flat_command_groups(doc)]
    assert not problems, f"{path.relative_to(REPO)}: {problems}"


@pytest.mark.parametrize("path", HOOK_RULES, ids=lambda p: str(p.relative_to(REPO)))
def test_no_hook_example_references_a_nonexistent_file_path_variable(path: Path):
    """Scan the FENCES, not the prose -- these docs legitimately MENTION the
    token while telling you not to use it (use-vs-mention)."""
    fences = _JSON_FENCE.findall(path.read_text(encoding="utf-8"))
    offenders = [f for f in fences if "$FILE_PATH" in f]
    assert not offenders, f"{path.relative_to(REPO)}: {len(offenders)} example(s)"


def test_detector_fires_on_a_flat_command_group():
    """KNOWN-BROKEN control: the exact pre-fix shape must be REJECTED."""
    broken = {
        "hooks": {
            "PostToolUse": [
                {"matcher": "Write|Edit", "command": "pnpm prettier --write x"}
            ]
        }
    }
    assert _flat_command_groups(broken)


def test_detector_fires_on_a_handler_without_a_type():
    broken = {"hooks": {"Stop": [{"hooks": [{"command": "pnpm build"}]}]}}
    assert _flat_command_groups(broken)


def test_detector_fires_on_a_group_with_no_handler_array():
    assert _flat_command_groups({"hooks": {"Stop": [{"matcher": ".*"}]}})


def test_detector_fires_on_an_empty_command():
    broken = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": ""}]}]}}
    assert _flat_command_groups(broken)


def test_detector_accepts_the_shape_the_builder_emits():
    good = {
        "hooks": {
            "Stop": [
                {"hooks": [{"type": "command", "command": "pnpm build", "timeout": 5}]}
            ]
        }
    }
    assert _flat_command_groups(good) == []
