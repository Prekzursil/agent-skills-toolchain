"""pentagi .env + decepticon-upstream .env audit-fix 2026-09-29."""
import re

BS = chr(92)
BACKUPS = [
    r'C:\Users\prekzursil\.agents\secrets\env-backups\2026-09-29\user.env',
    r'C:\Users\prekzursil\.agents\secrets\env-backups\2026-09-29\machine.env',
]
src_vals = {}
for f in BACKUPS:
    for line in open(f, encoding='utf-8', errors='replace'):
        if '=' in line:
            k, _, v = line.partition('=')
            k = k.strip()
            if k and k not in src_vals:
                src_vals[k] = v.rstrip('\r\n')

def patch(path, subs, appends=()):
    text = open(path, encoding='utf-8', newline='').read()
    changed = []
    for name, val in subs:
        pat = re.compile(r'(?m)^%s=.*$' % re.escape(name))
        if pat.search(text):
            text = pat.sub(lambda m: name + '=' + val, text, count=1)
            changed.append(name)
    for name, val in appends:
        if not re.search(r'(?m)^%s=' % re.escape(name), text):
            text = text.rstrip('\r\n') + '\n' + name + '=' + val + '\n'
            changed.append('+' + name)
    open(path, 'w', encoding='utf-8', newline='').write(text)
    return changed

# pentagi: loopback UI + real search keys (values sourced from the estate env backups)
p = r'D:\opt\pentagi\.env'
subs = [
    ('PENTAGI_LISTEN_IP', '127.0.0.1  # audit-fix 2026-09-29: was 0.0.0.0 - loopback-only per estate doctrine'),
    ('TAVILY_API_KEY', src_vals['TAVILY_API_KEY'] + '  # audit-fix 2026-09-29: was unexpanded ${TAVILY_API_KEY_2} template'),
    ('FIRECRAWL_API_KEY', src_vals['FIRECRAWL_API_KEY'] + '  # audit-fix 2026-09-29: was unexpanded self-referential template'),
]
appends = [
    ('OPENAI_API_KEY', src_vals['OPENAI_API_KEY'] + '  # audit-fix 2026-09-29: staged from estate env backup (was missing)'),
    ('EXA_API_KEY', src_vals['EXA_API_KEY'] + '  # audit-fix 2026-09-29: staged from estate env backup (was missing)'),
]
print('pentagi changed:', patch(p, subs, appends))

# decepticon-upstream: profile vars so the documented bring-up starts web+cli
p2 = r'D:\opt\decepticon-upstream\.env'
print('decepticon-upstream changed:', patch(p2, [], [
    ('COMPOSE_PROFILES', 'web,cli  # audit-fix 2026-09-29: documented bring-up needs web+cli profiles (were unset)'),
]))
