import re,sys,glob,json,html
out={}
for f in glob.glob('out/research/_ahmia_*.html'):
    try: h=open(f,encoding='utf-8',errors='replace').read()
    except: continue
    for m in re.finditer(r'<h4>\s*<a\s+href="/search/redirect\?search_term=([^&]*)&redirect_url=([^"]+)">\s*(.*?)\s*</a>\s*</h4>\s*(?:<p>(.*?)</p>)?\s*<cite>([^<]+)</cite>\s*(?:&mdash;|—)?\s*<span class="lastSeen" data-timestamp="([^"]*)"', h, re.S):
        term,url,title,desc,addr,seen=m.groups()
        title=html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',title))).strip()
        desc=html.unescape(re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',desc or ''))).strip()
        e=out.setdefault(addr,{'addr':addr,'hits':[]})
        if (title,url,desc,seen) not in e['hits']: e['hits'].append({'q':term,'url':url[:200],'title':title[:200],'desc':desc[:250],'last_seen':seen})
json.dump(list(out.values()),open('out/research/ahmia_candidates.json','w',encoding='utf-8'),indent=1)
print(len(out),'unique addresses parsed')
