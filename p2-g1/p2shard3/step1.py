from wslrun import wsl_bash, read_unc
import json

out = wsl_bash('cat ~/p2-g1/command-center/READY-UNITS.json', '/tmp/shard3_ready.txt')
print(out[:3000] if out else 'FAILED TO READ READY-UNITS.json')
