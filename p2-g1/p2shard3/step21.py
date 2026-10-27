from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s21.sh /tmp/s21.sh && bash /tmp/s21.sh', '/tmp/s21.out', timeout=1500)
print(out if out else 'FAILED')
