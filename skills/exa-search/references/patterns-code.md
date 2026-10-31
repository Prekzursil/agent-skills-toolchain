---
title: patterns-code
type: note
permalink: dqverify-repo-20261013/skills/exa-search/references/patterns-code
---

# Query Patterns: Code and Documentation

Always include programming language and framework/library in your query.

```
// API usage
web_search_exa { "query": "Stripe API create subscription Node.js code example", "numResults": 5 }

// Error resolution
web_search_exa { "query": "React hydration mismatch server client explanation fix", "numResults": 10 }

// GitHub implementations
web_search_exa { "query": "GitHub repository [library] example project open source", "numResults": 10 }
```

Use `web_fetch_exa` to read official docs when you know the URL.