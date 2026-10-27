from wslrun import wsl_bash
out = wsl_bash('find ~/p2-g1 -maxdepth 3 -name "_measure_one_delivered.py" 2>/dev/null; echo ---; find ~/p2-g1/command-center -maxdepth 2 -iname "*receipt*" 2>/dev/null | head -30; echo ---; ls ~/p2-g1/command-center/p2-wave/ 2>/dev/null | head -30', '/tmp/shard3_find.txt')
print(out if out else 'FIND FAILED')
