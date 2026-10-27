import subprocess, sys, time, os

def wsl_run(argv, outfile_linux, tries=4, sleep_s=5):
    """Run a command inside WSL with output redirected to a Linux file.
    argv: list of args AFTER 'bash -c', i.e. the shell string is our responsibility.
    Returns (ok, stdout_of_invocation). Read the outfile over UNC afterwards."""
    last = None
    for i in range(1, tries+1):
        try:
            # python subprocess with a LIST argv, never a shell string
            p = subprocess.run(
                ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc", argv],
                capture_output=True, timeout=1200)
            if p.returncode == 0:
                return True, p
            last = (i, p.returncode, p.stdout[-2000:], p.stderr[-2000:])
        except Exception as e:
            last = (i, 'exc', str(e).encode()[:2000], b'')
        if i < tries:
            time.sleep(sleep_s)
    ok = False
    return ok, last

if __name__ == "__main__":
    cmd = sys.argv[1]
    out = sys.argv[2]
    ok, res = wsl_run(cmd, out)
    print("OK" if ok else "FAIL")
    if isinstance(res, subprocess.CompletedProcess):
        print("rc:", res.returncode)
        sys.stdout.write(res.stdout.decode(errors="replace")[-3000:])
        sys.stdout.write(res.stderr.decode(errors="replace")[-3000:])
    else:
        print(res)
