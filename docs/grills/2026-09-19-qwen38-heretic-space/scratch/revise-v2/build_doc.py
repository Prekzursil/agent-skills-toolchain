#!/usr/bin/env python3
"""Assemble design-v2-final.md from the prose parts, embedding gate.sh / schemas.js / script.js verbatim."""
import hashlib, io, os, re

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = '/home/codespace/grills/2026-09-19-qwen38-heretic-space/evidence/orchestration/design-v2-final.md'

PARTS = [
    'part1-header-sec2.md',
    'part2-sec3-6.md',
    'part3-sec7.md',
    'part3-sec8.md',
    'part4-sec9.md',
    'part5-sec10-11.md',
    'part6-sec12.md',
    'part7-sec13-15.md',
    'part9-appendices.md',
]

EMBED_LANG = {'gate.sh': 'bash', 'schemas.js': 'js', 'script.js': 'js'}


def read(name):
    with io.open(os.path.join(DIR, name), 'r', encoding='utf-8') as f:
        return f.read()


def main():
    text = '\n'.join(read(p) for p in PARTS)

    def repl(m):
        name, lang = m.group(1), m.group(2)
        body = read(name).rstrip('\n')
        assert '```' not in body, 'fence marker inside ' + name
        return '```%s\n%s\n```' % (lang, body)

    text = re.sub(r'@@EMBED:([a-zA-Z0-9_.]+):(bash|js)@@', repl, text)

    with io.open(OUT, 'w', encoding='utf-8') as f:
        f.write(text)

    # ---- sanity checks ----
    # 1) sections 1..15 in order
    secs = re.findall(r'^## (\d+)\.', text, re.M)
    assert secs == [str(i) for i in range(1, 16)], secs
    # 2) no leftover embed markers
    assert '@@EMBED' not in text
    # 3) coverage rows: F-1..F-47, AP-1..17, T-AP-1..12, S-AP-1..14, SD-AP-1..12, CG-1..34 (+ V rows)
    n = sum(1 for line in text.splitlines()
            if re.match(r'^\| (F-\d+|AP-\d+|T-AP-\d+|S-AP-\d+|SD-AP-\d+|CG-\d+|V-\d+) ', line))
    assert n >= 136, n
    # 4) appendices present
    for h in ('## Appendix A', '## Appendix B', '## Appendix C'):
        assert h in text, h
    # 5) gate.sh embedded byte-identical (first ```bash fence is the gate embed)
    gate = read('gate.sh')
    m = re.search(r'```bash\n(.*?)\n```', text, re.S)
    assert m, 'no bash fence found'
    assert m.group(1) + '\n' == gate, 'gate.sh embed is not byte-identical'
    # 6) schemas.js + script.js embedded verbatim
    for name in ('schemas.js', 'script.js'):
        assert read(name).rstrip('\n') in text, name + ' not embedded verbatim'
    # 7) fences balanced
    fences = len(re.findall(r'^```', text, re.M))
    assert fences % 2 == 0, fences
    # 8) the C-1..C-38 appendix is complete
    cids = re.findall(r'^\| (C-\d+) \| ', text, re.M)
    assert sorted(set(cids)) == sorted('C-%d' % i for i in range(1, 39)), cids

    print('OK: sections 1-15 in order; coverage rows = %d; appendices A-C present; '
          'gate.sh byte-identical; schemas.js + script.js embedded verbatim; '
          'fences balanced (%d); C-1..C-38 complete' % (n, fences))
    print('output:', OUT)
    print('sha256:', hashlib.sha256(text.encode('utf-8')).hexdigest())
    print('lines:', text.count('\n') + 1, ' bytes:', len(text.encode('utf-8')))


if __name__ == '__main__':
    main()
