import pathlib
import re

p = pathlib.Path(r'C:\Users\Prekzursil\source\ast-integrate\command-center\audit\AUD-0051-coverage-baseline.json')
t = p.read_text(encoding='utf-8')
for m in re.finditer(r'\n(\s*)"headline": \{', t):
    print('headline at', m.start(), 'indent', len(m.group(1)))
    print(repr(t[m.start():m.start() + 460]))
    print('~~~~')
