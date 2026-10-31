from pathlib import Path

BS = chr(92)
p = Path("baseline.py")
s = p.read_text(encoding="utf-8")
# runtime message must contain \.\NUL ; rf-string doubles nothing, so the
# file text must carry 4 backslashes + . + 2.
cur = 'rf"reserved device name ' + BS + BS + '.' + BS + BS + 'NUL at {path}"'
want = 'rf"reserved device name ' + BS*4 + '.' + BS*2 + 'NUL at {path}"'
assert cur in s, "message anchor missing"
s = s.replace(cur, want)
p.write_text(s, encoding="utf-8", newline="")
print("message fixed")
