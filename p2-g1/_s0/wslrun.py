import subprocess, time, sys, os, uuid

B = chr(92)  # backslash
UNC_ROOT = B + B + "wsl.localhost" + B + "Ubuntu"
TMP = "/tmp/s0_" + uuid.uuid4().hex + ".txt"

def run_wsl(bash_cmd, retries=4, sleep_s=5.0, timeout=None):
    """Run bash inside WSL; output redirected INSIDE WSL to a unique file,
    read back over UNC. Retries up to 4 times with 5s sleeps."""
    global TMP
    TMP = "/tmp/s0_" + uuid.uuid4().hex + ".txt"
    out_unc = UNC_ROOT + B + "tmp" + B + os.path.basename(TMP)
    inner = ("rm -f " + TMP + "; { " + bash_cmd +
             " ; } > " + TMP + " 2>&1; echo __EXIT__:$? >> " + TMP)
    argv = ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc", inner]
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(argv, capture_output=True, timeout=timeout)
            with open(out_unc, "rb") as f:
                raw = f.read()
            text = raw.decode("utf-8", "replace")
            if "__EXIT__:" in text:
                return text
            last_err = "marker missing (%d bytes)" % len(raw)
        except Exception as e:
            last_err = repr(e)
        sys.stderr.write("[wslrun] attempt %d/4 failed: %s\n" % (attempt, last_err))
        time.sleep(sleep_s)
    raise RuntimeError("wsl failed after 4 attempts: %s" % last_err)

def exit_code(text):
    for line in text.rsplit("__EXIT__:", 1)[1].splitlines():
        line = line.strip()
        if line.isdigit():
            return int(line)
    return None

def out_only(text):
    i = text.rfind("__EXIT__:")
    lines = text[:i].splitlines()
    while lines and lines[-1].strip().startswith("__EXIT__:"):
        lines.pop()
    return "\n".join(lines)

if __name__ == "__main__":
    t = run_wsl(sys.argv[1] if len(sys.argv) > 1 else "echo hello")
    sys.stdout.write(t)
