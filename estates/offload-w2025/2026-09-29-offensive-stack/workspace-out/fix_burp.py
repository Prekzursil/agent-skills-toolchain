import json

P = r'C:\Users\prekzursil\.agents\agents.json'
d = json.load(open(P, encoding='utf-8'))
BS = chr(92)
burp = d['mcp']['servers']['burp']
desc = burp['description']
p_burp = 'D:' + BS + 'opt' + BS + 'burp' + BS + 'launch_burp_headless.ps1'
# kill any control char, then normalize the segment
clean = ''.join(c for c in desc if ord(c) >= 32 or c in '\n\r\t')
clean = clean.replace('D:' + BS + 'opturp' + BS + 'launch_burp_headless.ps1', p_burp)
clean = clean.replace('D:' + BS + 'optburp' + BS + 'launch_burp_headless.ps1', p_burp)
burp['description'] = clean
json.dump(d, open(P, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
open(P, 'a', encoding='utf-8').write('\n')
print('burp ok ==', p_burp in burp['description'])
ctrl = [c for c in burp['description'] if ord(c) < 32 and c not in '\n\r\t']
print('control chars left ==', len(ctrl))
