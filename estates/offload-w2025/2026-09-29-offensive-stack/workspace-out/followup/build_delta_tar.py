import os, hashlib, subprocess, sys

VAULT = r"D:\opt\vault\agent-skills-toolchain"
OLD   = r"C:\Users\PREKZU~1\AppData\Local\Temp\2\mirror0929"
assert os.path.exists(OLD), "mirror0929 extraction not found"

SOURCES = [("estates/offload-w2025",), ("cyberstrike/gateway/offload-w2025",)]

def sha(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

delta = []
for (sub,) in SOURCES:
    newroot = os.path.join(VAULT, sub)
    oldroot = os.path.join(OLD, sub)
    for root, dirs, files in os.walk(newroot):
        for f in files:
            if f.lower() in ("nul", "con", "prn", "aux"):
                continue
            nf = os.path.join(root, f)
            rel = os.path.relpath(nf, VAULT)
            of = os.path.join(OLD, rel)
            try:
                if not os.path.exists(of) or os.path.getsize(of) != os.path.getsize(nf) or sha(of) != sha(nf):
                    delta.append(rel)
            except OSError:
                delta.append(rel)

print(f"DELTA FILES: {len(delta)}")
with open(os.path.join(OLD, "delta-list.txt"), "w", newline="\n") as fh:
    fh.write("\n".join(d.replace("\\", "/") for d in delta))
print("LIST:", os.path.join(OLD, "delta-list.txt"))
