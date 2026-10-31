import subprocess, time, sys, os, json

B = chr(92)
UNC = B + B + 'wsl.localhost' + B + 'Ubuntu'
DISTRO = 'Ubuntu'

def wsl_bash(bash_cmd, outfile, timeout=3600):
    win_path = UNC + outfile.replace('/', B)
    last_err = None
    for attempt in range(1, 5):
        try:
            r = subprocess.run(
                ['wsl.exe', '-d', DISTRO, 'bash', '-c',
                 bash_cmd + ' > ' + outfile + ' 2>&1; echo "WEXIT:$?" >> ' + outfile],
                capture_output=True, timeout=timeout)
            if os.path.exists(win_path):
                with open(win_path, 'r', encoding='utf-8', errors='replace') as f:
                    data = f.read()
                if data.strip() != '':
                    return data
            last_err = 'wsl rc=%s stderr=%r' % (r.returncode, (r.stderr or b'')[-300:])
        except Exception as e:
            last_err = repr(e)
        time.sleep(5)
    sys.stderr.write('WSL RUN FAILED after 4 attempts: %s | last_err=%s' % (bash_cmd[:200], last_err))
    return None

def read_unc(linux_path, binary=False):
    win_path = UNC + linux_path.replace('/', B)
    if binary:
        with open(win_path, 'rb') as f:
            return f.read()
    with open(win_path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()

def write_unc(linux_path, data):
    win_path = UNC + linux_path.replace('/', B)
    d = os.path.dirname(win_path)
    if d:
        os.makedirs(d, exist_ok=True)
    if isinstance(data, str):
        with open(win_path, 'w', encoding='utf-8', newline='') as f:
            f.write(data)
    else:
        with open(win_path, 'wb') as f:
            f.write(data)

if __name__ == '__main__':
    out = wsl_bash('echo hello && ls ~/p2-g1 | head -20', '/tmp/shard3_smoke.txt')
    print(repr(out))
