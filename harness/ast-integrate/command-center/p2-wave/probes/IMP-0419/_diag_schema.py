import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from schema_ok import errors, validator  # noqa: E402

v = validator()
print("schema keys:", sorted(v.schema.keys()))
garbage = {"totally": "unrelated", "passing_tests": 999999}
errs = errors(garbage)
print("n_errors:", len(errs))
for e in errs[:5]:
    print(" ", e[:160])
try:
    resolved = v.resolver.resolve(v.schema.get("$ref"))
    print("ref resolves to keys:", sorted(list(resolved[1].keys()))[:8])
except Exception as exc:
    print("resolve error:", type(exc).__name__, exc)
