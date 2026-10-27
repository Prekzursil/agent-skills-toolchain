from wslrun import wsl_bash
out = wsl_bash('cp /mnt/c/Users/Prekzursil/source/ast-integrate/p2shard3/s32.sh /tmp/s32.sh && bash /tmp/s32.sh', '/tmp/s32.out', timeout=1800)
print(out if out else 'FAILED')
