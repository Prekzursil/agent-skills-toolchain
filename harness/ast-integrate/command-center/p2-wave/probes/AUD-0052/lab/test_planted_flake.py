import os
from pathlib import Path

STATE = Path(__file__).resolve().parent / "_state"
COUNTER = STATE / "flake_counter.txt"


def test_planted_flake():
    if os.environ.get("AUD0052_REPEAT_MODE") != "1":
        assert True
        return
    STATE.mkdir(parents=True, exist_ok=True)
    n = int(COUNTER.read_text(encoding="utf-8")) if COUNTER.exists() else 0
    n += 1
    COUNTER.write_text(str(n), encoding="utf-8")
    assert n % 2 == 1, f"planted flake fail on identical-order repeat {n}"
