def test_put():
    from pathlib import Path

    state = Path(__file__).resolve().parent / "_state"
    state.mkdir(parents=True, exist_ok=True)
    box = state / "box.txt"
    box.write_text("token\n", encoding="utf-8")
    assert box.read_text(encoding="utf-8") == "token\n"


def test_get():
    from pathlib import Path

    box = Path(__file__).resolve().parent / "_state" / "box.txt"
    assert box.is_file(), "order-dependent: test_get requires test_put first"
    assert box.read_text(encoding="utf-8") == "token\n"
