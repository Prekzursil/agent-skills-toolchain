from session_liveness.liveness import VERDICT_ALIVE, classify, Observation, EVIDENCE_WINDOW_SECONDS


def test_both_signals_alive():
    a = Observation("a", 1, True, 1, 10, 0)
    b = Observation("a", 1, True, 5, 40, 1)
    r = classify(a, b, window_seconds=EVIDENCE_WINDOW_SECONDS)
    assert r.verdict == VERDICT_ALIVE
