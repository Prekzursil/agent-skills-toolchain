import json, os, re, shutil, socket

AGENTS = r'C:\Users\prekzursil\.agents\agents.json'
d = json.load(open(AGENTS, encoding='utf-8'))
sv = d['mcp']['servers']

ABS = re.compile(r'^[A-Za-z]:[\\/]')

def ctrl(s):
    return any(ord(c) < 32 and c not in '\n\r\t' for c in s)

problems = []
for name, s in sorted(sv.items()):
    en = s.get('enabled', False)
    tr = s.get('transport')
    prob = []
    if tr == 'stdio':
        cmd = s.get('command', '')
        if ctrl(cmd):
            prob.append('command has control chars: %r' % cmd)
        elif ABS.match(cmd):
            if not os.path.exists(cmd):
                prob.append('command path missing: %s' % cmd)
        elif not shutil.which(cmd):
            prob.append('command not on PATH: %s' % cmd)
        for i, a in enumerate(s.get('args', [])):
            if ctrl(a):
                prob.append('args[%d] control chars: %r' % (i, a))
            elif ABS.match(a) and not os.path.exists(a):
                prob.append('args[%d] missing: %s' % (i, a))
        for k, v in (s.get('env') or {}).items():
            v = str(v)
            if ABS.match(v) and not os.path.exists(v):
                prob.append('env %s path missing: %s' % (k, v))
    elif tr in ('http', 'sse'):
        m = re.match(r'https?://(127[.]0[.]0[.]1|localhost)(?::(\d+))?', s.get('url', ''))
        if m and m.group(2):
            sk = socket.socket(); sk.settimeout(1.0); ok = False
            try:
                sk.connect(('127.0.0.1', int(m.group(2)))); ok = True
            except Exception:
                pass
            sk.close()
            if not ok:
                prob.append('endpoint down: %s' % s.get('url'))
    if prob:
        problems.append((name, tr, en, prob))

n_en = sum(1 for s in sv.values() if s.get('enabled'))
print('total servers: %d, enabled: %d' % (len(sv), n_en))
print('--- ALL servers with problems (%d) ---' % len(problems))
for name, tr, en, prob in problems:
    tag = 'ENABLED' if en else 'disabled'
    for p in prob:
        print('[%s/%s] %s: %s' % (tag, tr, name, p))

# control char scan over every string in the file
print('--- control chars anywhere in mcp.servers strings ---')
def walk(o, path):
    if isinstance(o, dict):
        for k, v in o.items(): walk(v, path + '.' + k)
    elif isinstance(o, list):
        for i, v in enumerate(o): walk(v, path + '[%d]' % i)
    elif isinstance(o, str) and ctrl(o):
        print('  %s: %r' % (path, o))
for name, s in sv.items():
    walk(s, name)

# env var inventory
print('--- env vars referenced (requiredEnv union env ${VAR}) ---')
req, sub = set(), set()
for name, s in sv.items():
    for r in s.get('requiredEnv', []): req.add(r)
    for k, v in (s.get('env') or {}).items():
        for m2 in re.findall(r'\$\{([^}]+)\}', str(v)): sub.add(m2)
print('requiredEnv:', sorted(req))
print('substituted :', sorted(sub))
