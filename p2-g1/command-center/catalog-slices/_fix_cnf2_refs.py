#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Remap internal CNF references in _gen_cnf2.py.

Two path-hostility units were merged into one during authoring, which shifted
every unit after index 25 down by one. References written against the
pre-merge numbering must be corrected. Rule:
  * CNF-0129..CNF-0154 -> unchanged (authored before the shift point)
  * CNF-0155..CNF-0189 -> minus one
  * the single quoted "CNF-0192" in a dependency list -> "CNF-0191"
    (the docstring occurrence CNF-0129..CNF-0192 is the slice range and stays)
"""
import io
import re
import sys

SRC = r"C:/Users/Prekzursil/source/ast-integrate/command-center/catalog-slices/_gen_cnf2.py"

with io.open(SRC, encoding="utf-8", newline="") as fh:
    text = fh.read()

before = dict()
for m in re.finditer(r"CNF-0(\d{3})", text):
    n = int(m.group(1))
    before[n] = before.get(n, 0) + 1


def shift(m):
    n = int(m.group(1))
    if 155 <= n <= 189:
        return "CNF-%04d" % (n - 1)
    return m.group(0)


text2 = re.sub(r"CNF-0(\d{3})", shift, text)

# targeted: the dependency-list occurrence only (quoted form)
count_quoted = text2.count('"CNF-0192"')
text2 = text2.replace('"CNF-0192"', '"CNF-0191"')

with io.open(SRC, "w", encoding="utf-8", newline="") as fh:
    fh.write(text2)

after = dict()
for m in re.finditer(r"CNF-0(\d{3})", text2):
    n = int(m.group(1))
    after[n] = after.get(n, 0) + 1

print("quoted CNF-0192 replaced:", count_quoted)
print("before:", sorted(before.items()))
print("after :", sorted(after.items()))
sys.exit(0)
