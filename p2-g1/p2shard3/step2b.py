from wslrun import wsl_bash
out = wsl_bash(
  'find ~/p2-g1 -name "_measure_one_delivered.py" 2>/dev/null | head -5; '
  'echo ---RECEIPT---; '
  'find ~/p2-g1 -iname "*receipt_core*" 2>/dev/null | head -10; '
  'echo ---PROBESDIR---; '
  'ls ~/p2-g1/command-center/p2-wave/probes/ 2>/dev/null | head -20; '
  'echo ---P2WAVE-DIRS---; '
  'find ~/p2-g1 -maxdepth 4 -type d -name "probes" 2>/dev/null | head -10',
  '/tmp/shard3_find2.txt')
print(out if out else 'FIND2 FAILED')
