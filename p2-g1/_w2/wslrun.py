#!/usr/bin/env python3
"""Run a command inside WSL with retries. Returns (rc, stdout, stderr)."""
import subprocess, sys, time

def wsl(args, tries=4, timeout=90):
    last = None
    for i in range(tries):
        try:
            p = subprocess.run(["wsl.exe", "--"] + args,
                               capture_output=True, text=True,
                               errors="replace", timeout=timeout)
            blob = ((p.stdout or "") + (p.stderr or ""))
            stripped = blob
            for ch in (chr(0), chr(0xfffd)):
                stripped = stripped.replace(ch, "")
            squeezed = "".join(stripped.split()).lower()
            if ("0x8007274c" not in squeezed
                    and "connectionattemptfailed" not in squeezed
                    and "wslservice" not in squeezed):
                return p.returncode, p.stdout, p.stderr
            last = RuntimeError("wedge: " + stripped[:160])
        except Exception as e:
            last = e
        print(f"[wslrun] retry {i+1}/{tries}: {last}", flush=True)
        time.sleep(5)
    return 1, "", repr(last)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--":
        args = ["bash", "-c", " ".join(sys.argv[2:])]
    else:
        args = sys.argv[1:]
    rc, o, e = wsl(args)
    sys.stdout.write(o)
    if e:
        sys.stderr.write(e)
    sys.exit(rc)
