"""K04 regression for the saved Workflow worktree partition policy."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / "workflows"
WORKFLOW = WORKFLOWS / "rtv-pdr.js"

_AGENT_CALL = re.compile(
    r"\bagent\(\s*`(?:\\.|[^`])*`\s*,\s*\{(?P<options>.*?)\}\s*\)",
    re.DOTALL,
)
_LABEL = re.compile(r"\blabel\s*:\s*(?P<quote>['\"`])(?P<label>.*?)(?P=quote)")
_WORKTREE = re.compile(r"\bisolation\s*:\s*['\"]worktree['\"]")

ALL_LABELS = {
    "rollout:R${idx}",
    "judge:${a.id}vs${b.id}:r${roundNum}",
    "judge-retry:${a.id}vs${b.id}:r${roundNum}",
    "pdr-refine",
    "judge:winner-vs-pdr",
}
MUTATING_LABELS = {"rollout:R${idx}", "pdr-refine"}


def _agent_options_by_label() -> dict[str, str]:
    source = WORKFLOW.read_text(encoding="utf-8")
    calls: dict[str, str] = {}
    for match in _AGENT_CALL.finditer(source):
        options = match.group("options")
        label_match = _LABEL.search(options)
        assert label_match is not None, (
            "every saved-workflow agent call needs a label for K04 classification"
        )
        label = label_match.group("label")
        assert label not in calls, f"duplicate agent label: {label}"
        calls[label] = options
    return calls


def _assert_exact_partition(target_label: str) -> None:
    workflow_surface = {
        path.relative_to(WORKFLOWS).as_posix()
        for pattern in ("*.js", "*.mjs")
        for path in WORKFLOWS.rglob(pattern)
    }
    assert workflow_surface == {"rtv-pdr.js"}, (
        "classify every added saved workflow as part of the K04 partition policy"
    )

    calls = _agent_options_by_label()

    # Known-present control: prove the detector sees every call before trusting
    # its report about the isolation option.  This assertion and the partition
    # assertion intentionally share one test, so the pre-K04 tree is RED.
    assert set(calls) == ALL_LABELS

    partitioned = {
        label for label, options in calls.items() if _WORKTREE.search(options)
    }
    assert partitioned == MUTATING_LABELS, (
        "known-broken pre-K04 state: rollout and pdr-refine had no worktree "
        f"isolation; got {sorted(partitioned)}"
    )
    assert target_label in partitioned


def test_parallel_rollouts_use_worktree_isolation() -> None:
    """Known broken before K04: every rollout shared the parent git index."""
    _assert_exact_partition("rollout:R${idx}")


def test_pdr_refine_uses_worktree_isolation() -> None:
    """Known broken before K04: the mutation-capable refine agent shared the index."""
    _assert_exact_partition("pdr-refine")
