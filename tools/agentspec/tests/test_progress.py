"""A progress/status stream is NEVER a result.

The measured failure: an agent forwarded a raw ``[codex] …`` progress stream as its terminal
answer, and another returned "started in the background as task-…" while the real finding was
discarded unread. The type split makes that unrepresentable: :func:`classify` returns either a
``ResultText`` or a ``ProgressLog``, and only a ``ResultText`` can become a result.
"""

from __future__ import annotations

import dataclasses

import pytest

from agentspec.progress import (
    BACKGROUND_PHRASES,
    ProgressLog,
    ProgressStreamRejected,
    ResultText,
    as_result,
    classify,
    looks_like_progress,
)


def test_background_phrases_are_the_declared_closed_set() -> None:
    assert BACKGROUND_PHRASES == (
        "check /codex:status",
        "check the job status",
        "launched in the background",
        "running in the background",
        "started in the background",
    )


def test_a_real_answer_classifies_as_a_result() -> None:
    got = classify("The bug is in validate.py: the cycle finder skips self-edges.")
    assert isinstance(got, ResultText)
    assert as_result(got).startswith("The bug is in")


@pytest.mark.parametrize("phrase", BACKGROUND_PHRASES)
def test_each_background_phrase_is_rejected(phrase: str) -> None:
    got = classify(f"Job accepted. {phrase} as task-91af.")
    assert isinstance(got, ProgressLog)
    assert got.marker == phrase


def test_the_phrase_match_is_case_insensitive() -> None:
    got = classify("STARTED IN THE BACKGROUND as task-1")
    assert isinstance(got, ProgressLog)


def test_a_payload_that_is_only_bracketed_progress_lines_is_rejected() -> None:
    payload = "[codex] thinking\n[codex] reading files\n[codex] done\n"
    got = classify(payload)
    assert isinstance(got, ProgressLog)
    assert got.marker == "progress-line-only"


def test_a_progress_prefix_followed_by_real_content_is_a_result() -> None:
    """Detector control: the prefix rule must NOT swallow a payload with real content."""
    got = classify("[codex] thinking\nThe answer is 42.\n")
    assert isinstance(got, ResultText)


def test_blank_lines_do_not_make_a_real_answer_look_like_progress() -> None:
    got = classify("\n\nThe answer is 42.\n\n")
    assert isinstance(got, ResultText)


def test_an_all_blank_payload_is_a_result_not_progress() -> None:
    """Emptiness is the ORACLE's receipt-empty clause, not a progress verdict."""
    assert isinstance(classify("   \n  \n"), ResultText)


def test_as_result_on_a_progress_log_raises_with_the_taxonomy_reason() -> None:
    got = classify("started in the background as task-2")
    with pytest.raises(ProgressStreamRejected) as caught:
        as_result(got)
    assert caught.value.reason == "progress-stream"
    assert caught.value.marker == "started in the background"


def test_looks_like_progress_is_the_boolean_shorthand() -> None:
    assert looks_like_progress("Check /codex:status for the result") is True
    assert looks_like_progress("The answer is 42.") is False


def test_result_text_and_progress_log_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ResultText(text="a").text = "b"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ProgressLog(text="a", marker="m").marker = "n"  # type: ignore[misc]


def test_as_result_refuses_an_object_that_is_neither_variant() -> None:
    """Total function: an unexpected type is a loud TypeError, never a silent passthrough."""
    with pytest.raises(TypeError, match="ResultText"):
        as_result("just a string")  # type: ignore[arg-type]
