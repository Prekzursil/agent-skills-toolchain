#!/bin/bash
find /home/prekzursil/p2-g1 -iname "*receipt_core*" 2>/dev/null
echo ---
grep -rln "failure.classification" /home/prekzursil/p2-g1/command-center --include="*.py" 2>/dev/null | head
echo ---
grep -rln "receipt_core" /home/prekzursil/p2-g1/command-center/p2-wave --include="*.py" 2>/dev/null | head
