import re,sys,html
h=open(sys.argv[1],encoding='utf-8',errors='replace').read()
seen=set()
for m in re.finditer(r'<cite>([^<]+)', h):
    seen.add(m.group(1).strip())
titles = re.findall(r'<h4[^>]*>\s*(?:<a[^>]*>)?(.*?)(?:</a>)?\s*</h4>', h, re.S)
print("RESULTS:", len(seen))
for c in sorted(seen): print(c)
