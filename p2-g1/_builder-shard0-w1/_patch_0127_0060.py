"""Two platform repairs: 0127 tzset guard, 0060 volatile tmp paths in raw payload."""
from pathlib import Path

# ---------- ADV-0127: time.tzset() is POSIX-only ----------
p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0127/clock_lib.py"
src = p.read_text(encoding="utf-8")
old = '''class _TzGuard:
    def __init__(self) -> None:
        self._orig = os.environ.get("TZ")

    def set(self, tz: str) -> None:
        os.environ["TZ"] = tz
        time.tzset()

    def restore(self) -> None:
        if self._orig is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._orig
        time.tzset()'''
new = '''class _TzGuard:
    def __init__(self) -> None:
        self._orig = os.environ.get("TZ")

    def set(self, tz: str) -> None:
        os.environ["TZ"] = tz
        # Windows platform adaptation: time.tzset() is POSIX-only and Windows
        # ignores the TZ env var in its time functions entirely, so set and
        # restore are symmetric no-ops there - the guarded reads are
        # TZ-independent on win32, which preserves the guard's correctness.
        if hasattr(time, "tzset"):
            time.tzset()

    def restore(self) -> None:
        if self._orig is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self._orig
        if hasattr(time, "tzset"):
            time.tzset()'''
assert old in src, "tzguard anchor missing"
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("0127 clock_lib tzset guarded")

# ---------- ADV-0060: redact volatile tmp roots from the probe1 payload ----------
p2 = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0060/lifecycle.py"
src2 = p2.read_text(encoding="utf-8")
old2 = '''def probe1_report(m: dict[str, Any]) -> str:
    payload = {'''
new2 = '''def _redact_tmp(obj: Any, marker: str = "<tmp>") -> Any:
    """Canonicalise volatile temp-dir paths so the recorded raw payload is
    deterministic across runs (the probe compares its own fresh payload to the
    artifact-embedded one; absolute tempfile paths differ every run)."""
    if isinstance(obj, str):
        return obj.replace(str(_TMP_ROOT), marker) if _TMP_ROOT else obj
    if isinstance(obj, list):
        return [_redact_tmp(x, marker) for x in obj]
    if isinstance(obj, dict):
        return {k: _redact_tmp(v, marker) for k, v in obj.items()}
    return obj


_TMP_ROOT = ""


def probe1_report(m: dict[str, Any]) -> str:
    global _TMP_ROOT
    _TMP_ROOT = str(m.get("tmp_root") or "")
    payload = {'''
assert old2 in src2, "probe1_report anchor missing"
src2 = src2.replace(old2, new2, 1)

old3 = '''    body = json.dumps(payload, indent=2, sort_keys=True)'''
new3 = '''    payload = _redact_tmp(payload)
    body = json.dumps(payload, indent=2, sort_keys=True)'''
assert old3 in src2, "body anchor missing"
src2 = src2.replace(old3, new3, 1)
p2.write_text(src2, encoding="utf-8")
ast.parse(src2)
print("0060 lifecycle redaction added")
