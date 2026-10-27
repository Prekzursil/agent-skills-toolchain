from wslrun import wsl_bash
cmds = [
 ('measure', 'find ~/p2-g1 -name "*measure_one_delivered*" -type f 2>/dev/null'),
 ('receipt', 'grep -rl "reviewer-absent" ~/p2-g1 --include="*.py" --include="*.md" --include="*.json" 2>/dev/null | head -20'),
 ('probdir', 'ls ~/p2-g1/command-center/p2-wave/probes/ | head; echo COUNT=$(ls ~/p2-g1/command-center/p2-wave/probes/ | wc -l)'),
 ('myprobes', 'for u in ADV-0005 AUD-0031 AUD-0043 AUD-0044 AUD-0055 AUD-0095 BLD-0010 BLD-0013 BLD-0014 BLD-0031 BLD-0032 BLD-0037 BLD-0044 BLD-0048 BLD-0057; do echo "== $u"; ls ~/p2-g1/command-center/p2-wave/probes/$u/ 2>/dev/null || echo MISSING; done'),
]
for name, cmd in cmds:
    out = wsl_bash(cmd, '/tmp/shard3_%s.txt' % name)
    print('### %s ###' % name)
    print(out if out else 'FAILED')
    print()
