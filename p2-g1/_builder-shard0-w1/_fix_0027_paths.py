"""ADV-0027 matrix: resolve BOTH sides of the containment check.

Windows platform adaptation: tempfile paths arrive in 8.3 short form
(PREKZU~1) while Path.resolve() returns the long form, so the un-resolved
left side made every benign file look 'outside'. Resolving both sides keeps
the semantics exact (outside files still fail relative_to)."""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0027/matrix.py"
src = p.read_text(encoding="utf-8")
old = """        try:
            path.relative_to(dest.resolve())
        except ValueError:
            found.append(str(path))"""
new = """        try:
            # Resolve both sides: on Windows the rglob path may carry the 8.3
            # short temp-name while resolve() returns the long form, which
            # made every inside file look 'outside'.
            path.resolve().relative_to(dest.resolve())
        except ValueError:
            found.append(str(path))"""
assert old in src, "outside_files anchor missing"
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("matrix.py containment fixed")
