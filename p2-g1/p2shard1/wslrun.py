import subprocess, sys, time, os

UNC = r"\wsl.localhost\Ubuntu"
LINUX_OUT = "/home/prekzursil/p2-shard1-out"
WIN_OUT = UNC + os.sep + "home" + os.sep + "prekzursil" + os.sep + "p2-shard1-out"

def wsl_exec(script, timeout=900, retries=4, tag="run", wait_secs=90):
    """Run a bash script inside WSL. Output redirected INSIDE WSL to a file;
    read back over the UNC path. Retry wsl invocation up to 4 times with 5s sleeps."""
    outfile = f"{LINUX_OUT}/{tag}.txt"
    winfile = os.path.join(WIN_OUT, tag + ".txt")
    wrapped = "{ " + script + "\n; } > " + outfile + " 2>&1; echo EXITCODE:$? >> " + outfile
    argv = ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-c", "mkdir -p " + LINUX_OUT + " && rm -f " + outfile + " && " + wrapped]
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            p = subprocess.run(argv, capture_output=True, timeout=timeout)
            deadline = time.time() + wait_secs
            while time.time() < deadline:
                try:
                    if os.path.exists(winfile):
                        with open(winfile, "rb") as f:
                            data = f.read()
                        if b"EXITCODE:" in data:
                            return data.decode("utf-8", "replace")
                except OSError:
                    pass
                time.sleep(1.0)
            last_err = RuntimeError(f"wsl rc={p.returncode} but no complete output file (attempt {attempt})")
        except Exception as e:
            last_err = e
        time.sleep(5)
    raise RuntimeError(f"WSL failed after {retries} attempts for {tag}: {last_err}")

if __name__ == "__main__":
    tag = sys.argv[1]
    script = sys.stdin.read()
    out = wsl_exec(script, tag=tag)
    sys.stdout.write(out)
