"""Drive a bash script (written as a file over UNC) inside WSL with retries."""
import subprocess, sys, time, os

UNC = "//wsl.localhost/Ubuntu"
OUT_LINUX = "/home/prekzursil/p2-shard1-out"
OUT_WIN = UNC + "/home/prekzursil/p2-shard1-out"

def run_script(script_name, tag, retries=4, wait_secs=120, timeout=1800):
    outfile = OUT_LINUX + "/" + tag + ".out"
    winfile = OUT_WIN + "/" + tag + ".out"
    if os.path.exists(winfile):
        try:
            os.remove(winfile)
        except OSError:
            pass
    inner = "bash " + OUT_LINUX + "/" + script_name + " > " + outfile + " 2>&1"
    argv = ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-c", inner + "; echo EXITCODE:$? >> " + outfile]
    last = None
    for attempt in range(1, retries + 1):
        try:
            subprocess.run(argv, capture_output=True, timeout=timeout)
            deadline = time.time() + wait_secs
            while time.time() < deadline:
                try:
                    if os.path.exists(winfile):
                        data = open(winfile, "rb").read()
                        if b"EXITCODE:" in data:
                            return data.decode("utf-8", "replace")
                except OSError:
                    pass
                time.sleep(1.0)
            last = RuntimeError("no complete output file")
        except Exception as e:
            last = e
        time.sleep(5)
    raise RuntimeError("failed after " + str(retries) + " attempts: " + repr(last))

if __name__ == "__main__":
    print(run_script(sys.argv[1], sys.argv[2]))
