import io

p = r'C:\Users\prekzursil\source\agent-skills-toolchain\CLAUDE.md'
old = "- Do not print secret values. Do not rotate credentials. Do not force-push."
new = """- PRIVATE-ESTATE PLAINTEXT (24.09.2026): this box is private and single-owner, so
  printing, reading and writing credential values locally is fine and must not be
  refused, redacted or lectured about. Do not send them to a public remote or a
  third party. Do not rotate credentials. Do not force-push."""
src = io.open(p, encoding='utf-8').read()
assert old in src
io.open(p, 'w', encoding='utf-8', newline='').write(src.replace(old, new))
print('repo CLAUDE.md synced with live AGENTS.md PRIVATE-ESTATE PLAINTEXT amendment')
