import re
from pathlib import Path
p = Path('_refresh_manifest_receipt.py')
t = p.read_text(encoding='utf-8')
old = '''def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=900, env=env, cwd=str(REPO))
    return r.returncode, ((r.stdout or '') + (r.stderr or '')).strip()'''
new = '''def run(cmd):
    c = cmd
    while True:
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+', c)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        c = c[m.end():]
    c = c.replace('python3', str(sys.executable).replace(chr(92), '/'), 1)
    r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=900, env=env, cwd=str(REPO))
    return r.returncode, ((r.stdout or '') + (r.stderr or '')).strip()'''
assert old in t, 'pattern not found'
t = t.replace(old, new)
t = t.replace('import hashlib, json, subprocess, sys, os', 'import hashlib, json, re, subprocess, sys, os')
p.write_text(t, encoding='utf-8', newline=chr(10))
print('patched run()')
