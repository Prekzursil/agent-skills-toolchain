restore = '''[mcp_servers."cve"]
url = "http://127.0.0.1:31111/mcp"
enabled = false  # audit-fix 2026-09-29: hub port 31111 dead; consume via cyberstrike-gateway :31100
startup_timeout_sec = 10

[mcp_servers."sliver"]
url = "http://127.0.0.1:31100/mcp"
enabled = true
startup_timeout_sec = 10

[mcp_servers."apify"]
url = "https://mcp.apify.com/"
enabled = true
bearer_token_env_var = "APIFY_TOKEN"
'''
P = r'C:\Users\prekzursil\.codex\config.toml'
src = open(P, encoding='utf-8', newline='').read()
if 'mcp_servers."apify"' not in src:
    src = src.rstrip() + '\n\n' + restore
    open(P, 'w', encoding='utf-8', newline='').write(src)
    print('restored cve/sliver/apify blocks')
else:
    print('already present')
