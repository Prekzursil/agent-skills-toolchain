import json

P = r'C:\Users\prekzursil\.agents\agents.json'
d = json.load(open(P, encoding='utf-8'))
sv = d['mcp']['servers']

BS = chr(92)  # backslash

# intended literal paths
p_breach = 'D:' + BS + 'opt' + BS + 'breach-mcp' + BS + 'breach_intel_mcp.py'
p_burp = 'D:' + BS + 'opt' + BS + 'burp' + BS + 'launch_burp_headless.ps1'
p_bolt = 'D:' + BS + 'bolt' + BS + 'credentials' + BS + 'breach-vendor-keys.json'

sv['breach-intel']['args'][0] = p_breach

bd = sv['burp']['description']
# current mangled: 'D:\optburp\launch_burp_headless.ps1'
bd = bd.replace('D:' + BS + 'optburp' + BS + 'launch_burp_headless.ps1', p_burp)
sv['burp']['description'] = bd

cd = sv['breach-intel']['description']
# current mangled tail: 'D:bolt\\credentials\breach-vendor-keys.json' variants
cd = cd.replace('D:bo' + 'lt', p_bolt.replace(BS + 'credentials' + BS + 'breach-vendor-keys.json', ''))
# rebuild cleanly: strip any previous attempt, append canonical revival line
import re
cd = re.sub(r'Revival: restore .*?re-enable\.', '', cd, flags=re.S)
if 'D:' + BS + 'bolt' not in cd:
    cd = cd.rstrip() + ' Revival: restore ' + p_breach.replace('breach_intel_mcp.py', '') + ' and ' + p_bolt + ' and re-enable.'
sv['breach-intel']['description'] = cd

json.dump(d, open(P, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
open(P, 'a', encoding='utf-8').write('\n')

print('args0 ==', repr(sv['breach-intel']['args'][0]))
print('burp ok ==', p_burp in sv['burp']['description'])
print('bolt ok ==', p_bolt in sv['breach-intel']['description'])
