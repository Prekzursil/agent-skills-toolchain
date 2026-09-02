import hashlib
import sys

for p in sys.argv[1:]:
    b = open(p, "rb").read()
    n = b.replace(b"\r\n", b"\n")
    print(len(b), hashlib.sha256(n).hexdigest(), p)
