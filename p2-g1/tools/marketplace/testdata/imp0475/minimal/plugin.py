"""Well-scoped plugin: reads a local notes file."""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_notes() -> str:
    return (HERE / "notes.txt").read_text(encoding="utf-8")
