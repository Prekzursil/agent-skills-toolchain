"""L13 regression proof: the recorded harness corpus must execute in quality CI."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "quality.yml"
STEP_NAME = "gate-tests-coverage adversarial harness corpus"
EXPECTED_TARGETS = (
    "ci/tests/test_harness_corpus_wiring.py",
    "tools/harness-corpus/test_hook_telemetry.py",
    "hooks/git-hygiene/test_docs_hygiene.py",
)
CORPUS_FIXTURE = REPO_ROOT / "hooks" / "_shared" / "use-vs-mention-corpus.jsonl"


def test_quality_workflow_executes_recorded_harness_corpus() -> None:
    """Known-broken pre-L13 [almost-certain 90-99%; measured]: no CI corpus step."""
    assert CORPUS_FIXTURE.is_file(), f"missing checked-in corpus: {CORPUS_FIXTURE}"
    assert CORPUS_FIXTURE.read_text(encoding="utf-8").strip(), (
        f"checked-in corpus is empty: {CORPUS_FIXTURE}"
    )

    workflow = QUALITY_WORKFLOW.read_text(encoding="utf-8")
    marker = f"- name: {STEP_NAME}"
    _before, found, remainder = workflow.partition(marker)
    assert found, f"quality CI has no {STEP_NAME!r} step"

    step_body = remainder.partition("\n      - name:")[0]
    assert "python -m pytest" in step_body
    missing = [path for path in EXPECTED_TARGETS if path not in step_body]
    assert not missing, f"adversarial corpus CI step omits: {missing}"
