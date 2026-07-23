"""I5 -- prove the routing benchmark is called by a shadow CI lane."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "routing-benchmark.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_routing_benchmark_workflow_exists() -> None:
    # Known-broken: no workflow referenced harness-bench or semantic-router/eval.
    assert WORKFLOW.is_file(), f"missing {WORKFLOW}"


def test_workflow_runs_the_gate_and_its_targeted_self_tests() -> None:
    # Known-broken: repo CI had neither an evaluator call-site nor targeted bench tests.
    text = workflow_text()
    assert "python hooks/harness-bench/gate.py --runs 5" in text
    assert "python -m pytest" in text
    for path in (
        "hooks/harness-bench/test_bench.py",
        "hooks/harness-bench/test_gate.py",
        "hooks/semantic-router/test_eval.py",
        "ci/tests/test_routing_benchmark_wiring.py",
    ):
        assert path in text


def test_regression_probe_ships_in_shadow() -> None:
    # Known-broken: there was no CI lane in shadow or enforce mode.
    text = workflow_text()
    assert "name: routing-benchmark (shadow)" in text
    assert "continue-on-error: true" in text
    assert "routing regression probe (5-run; shadow)" in text


def test_workflow_pins_actions_engine_and_model() -> None:
    # Known-broken: absent workflow meant no pinned runtime for the model-shaped router.
    text = workflow_text()
    uses = [
        line.split("uses:", 1)[1].strip()
        for line in text.splitlines()
        if "uses:" in line
    ]
    assert uses
    for ref in uses:
        action, _, sha = ref.partition("@")
        sha = sha.split()[0]
        assert len(sha) == 40 and all(char in "0123456789abcdef" for char in sha), (
            f"{action} is not SHA-pinned: {ref}"
        )
    assert (
        "image: ollama/ollama@sha256:"
        "a5409cb903d30f9cd67e9f430dd336ddc9274e16fd78f75b675c42065991b4fd" in text
    )
    # The model digest is recorded as OLLAMA_MODEL_DIGEST, not as a `name@sha256:` pull ref:
    # `ollama pull` rejects that form with `400 Bad Request: invalid model name` (measured in CI
    # on this workflow's first run). The pin is still asserted here so it cannot drift silently;
    # what changed is where it lives, not whether it exists.
    assert (
        "OLLAMA_MODEL_DIGEST: sha256:"
        "0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f" in text
    )
    # ...and the pull must use the tag, or the job dies before it measures anything.
    assert 'ollama pull "$SEMROUTER_EMBED_MODEL"' in text
