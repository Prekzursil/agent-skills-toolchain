"""Distinguish -I vs script-file vs spawn env for the bash timeout."""
import subprocess
import sys
import time

t0 = time.time()
try:
    p = subprocess.run(["bash", "-c", "printf 'x\\ty\\n'"], capture_output=True, text=True, timeout=8)
    print(f"script spawn: rc={p.returncode} {round(time.time()-t0,1)}s out={p.stdout!r}")
except subprocess.TimeoutExpired:
    print(f"script spawn: TIMEOUT {round(time.time()-t0,1)}s")
print("cwd:", __file__)
