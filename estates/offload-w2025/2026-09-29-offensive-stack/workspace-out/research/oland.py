import re,sys,html
h=open(sys.argv[1],encoding='utf-8',errors='replace').read()
for m in re.finditer(r'data-category="text-result"[^>]*href="[^"]*">(.*?)</a>\s*</div>\s*<div class="link">\s*(.*?)\s*</div>\s*<div class="desc">\s*(.*?)\s*</div>', h, re.S):
    t=re.sub(r'<[^>]+>','',m.group(1)).strip()
    u=re.sub(r'<[^>]+>','',m.group(2)).strip()
    d=re.sub(r'<[^>]+>','',m.group(3)).strip()
    print(f"{u[:75]:75s} | {html.unescape(t)[:70]} | {html.unescape(re.sub('<[^>]+>',' ',d))[:110]}")
