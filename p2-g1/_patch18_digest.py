from pathlib import Path

p = Path("C:/Users/Prekzursil/p2-g1/_review_shard18_w2_verify.py")
lines = p.read_text(encoding="utf-8").splitlines(True)
new = [
    "def digest(path):" + chr(10),
    "    raw = path.read_bytes().replace(bytes([13, 10]), bytes([10]))" + chr(10),
    "    return hashlib.sha256(raw).hexdigest(), len(raw)" + chr(10),
    chr(10),
    chr(10),
]
lines[52:59] = new
p.write_text("".join(lines), encoding="utf-8", newline=chr(10))
print("PATCHED lines 53-57")
