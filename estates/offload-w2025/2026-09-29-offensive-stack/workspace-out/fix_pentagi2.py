import re

src_vals = {}
for f in [r'C:\Users\prekzursil\.agents\secrets\env-backups\2026-09-29\user.env',
          r'C:\Users\prekzursil\.agents\secrets\env-backups\2026-09-29\machine.env']:
    for line in open(f, encoding='utf-8', errors='replace'):
        if '=' in line:
            k, _, v = line.partition('=')
            k = k.strip()
            if k and k not in src_vals:
                src_vals[k] = v.rstrip('\r\n')

p = r'D:\opt\pentagi\.env'
lines = open(p, encoding='utf-8', newline='').read().splitlines(keepends=False)
out = []
for ln in lines:
    if ln.startswith('PENTAGI_LISTEN_IP='):
        out.append('# audit-fix 2026-09-29: was 0.0.0.0 - loopback-only per estate doctrine')
        out.append('PENTAGI_LISTEN_IP=127.0.0.1')
    elif ln.startswith('TAVILY_API_KEY='):
        out.append('# audit-fix 2026-09-29: was unexpanded ${TAVILY_API_KEY_2} template; real key from estate env backup')
        out.append('TAVILY_API_KEY=' + src_vals['TAVILY_API_KEY'])
    elif ln.startswith('FIRECRAWL_API_KEY='):
        out.append('# audit-fix 2026-09-29: was unexpanded self-referential template; real key from estate env backup')
        out.append('FIRECRAWL_API_KEY=' + src_vals['FIRECRAWL_API_KEY'])
    elif ln.startswith('OPENAI_API_KEY='):
        out.append('# audit-fix 2026-09-29: staged from estate env backup (was missing)')
        out.append('OPENAI_API_KEY=' + src_vals['OPENAI_API_KEY'])
    elif ln.startswith('EXA_API_KEY='):
        out.append('# audit-fix 2026-09-29: staged from estate env backup (was missing)')
        out.append('EXA_API_KEY=' + src_vals['EXA_API_KEY'])
    else:
        out.append(ln)
open(p, 'w', encoding='utf-8', newline='\r\n').write('\n'.join(out) + '\n')
print('pentagi .env rewritten without inline comments')
