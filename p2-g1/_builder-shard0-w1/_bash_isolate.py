"""Isolate the bash batch construct that hangs on MSYS."""
import subprocess
import time

CASES = {
    "A command -v single": 'command -v python3',
    "B command -v with --": 'command -v -- python3',
    "C loop no-dash": 'for n in python3 git; do loc=$(command -v "$n") && printf \'%s\\t%s\\n\' "$n" "$loc"; done',
    "D loop with --": 'for n in python3 git; do loc=$(command -v -- "$n") && printf \'%s\\t%s\\n\' "$n" "$loc"; done',
    "E printf only": 'printf \'%s\\t%s\\n\' aa bb',
    "F cmdsub only": 'loc=$(command -v python3) && printf \'%s\\t%s\\n\' python3 "$loc"',
}
for label, script in CASES.items():
    t0 = time.time()
    try:
        p = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=12)
        print(f"{label}: rc={p.returncode} {round(time.time()-t0,1)}s out={p.stdout!r} err={p.stderr[:80]!r}")
    except subprocess.TimeoutExpired:
        print(f"{label}: TIMEOUT after 12s")
