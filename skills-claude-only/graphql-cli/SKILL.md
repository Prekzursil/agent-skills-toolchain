---
name: graphql-cli
description: Query GraphQL endpoints using curl or graphql-cli. Use when the user
  mentions GraphQL, graphql query, graphql mutation, or graphql schema.
permalink: dqverify-repo-20261013/skills-claude-only/graphql-cli/skill
---

# GraphQL CLI

Query GraphQL endpoints directly via `curl` or `npx graphqurl` through the Bash tool. Replaces the GraphQL MCP server with native CLI calls.

## Prerequisites

No installation required -- `curl` is available on all systems. For a friendlier interface:

```bash
# Check if graphqurl is available
npx graphqurl --version 2>/dev/null || echo "graphqurl not cached; will be fetched on first use via npx"
```

### Default endpoint

If the `GRAPHQL_ENDPOINT` environment variable is set, use it. Otherwise default to `http://localhost:4000/graphql`:

```bash
ENDPOINT="${GRAPHQL_ENDPOINT:-http://localhost:4000/graphql}"
```

## Queries with curl

### Basic query

```bash
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ users { id name email } }"}'
```

### Query with variables

```bash
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query GetUser($id: ID!) { user(id: $id) { id name email } }",
    "variables": {"id": "123"}
  }'
```

### Query with authentication

```bash
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"{ me { id name } }"}'
```

### Pretty-print response

Pipe through `jq` for readable output (if available) or `python -m json.tool`:

```bash
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ users { id name } }"}' | jq .
```

## Mutations with curl

### Basic mutation

```bash
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation CreateUser($input: CreateUserInput!) { createUser(input: $input) { id name } }",
    "variables": {"input": {"name": "Alice", "email": "alice@example.com"}}
  }'
```

## Schema Introspection

### Full introspection query

```bash
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { types { name kind description } } }"}' | jq .
```

### List all types

```bash
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { types { name kind } } }"}' | jq '.data.__schema.types[] | select(.kind != "SCALAR" and (.name | startswith("__") | not))'
```

### Inspect a specific type

```bash
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __type(name: \"User\") { name fields { name type { name kind ofType { name } } } } }"}' | jq .
```

### List all queries and mutations

```bash
# Queries
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { queryType { fields { name description args { name type { name } } } } } }"}' | jq .

# Mutations
curl -s -X POST "$ENDPOINT" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ __schema { mutationType { fields { name description args { name type { name } } } } } }"}' | jq .
```

## Using graphqurl (Alternative)

`graphqurl` provides a more ergonomic interface via `npx`:

### Basic query

```bash
npx graphqurl "$ENDPOINT" -q '{ users { id name email } }'
```

### Query with variables

```bash
npx graphqurl "$ENDPOINT" \
  -q 'query GetUser($id: ID!) { user(id: $id) { id name email } }' \
  -v 'id=123'
```

### Query with headers

```bash
npx graphqurl "$ENDPOINT" \
  -H "Authorization: Bearer $TOKEN" \
  -q '{ me { id name } }'
```

### Introspection

```bash
npx graphqurl "$ENDPOINT" --introspect
```

## Tips

- Always use `-s` (silent) with curl to suppress progress output.
- Pipe responses through `jq .` for readable formatting.
- For large queries, write the query to a file and use `curl -d @query.json`.
- Use `jq` selectors to extract specific fields: `| jq '.data.users[].name'`.
- When debugging, add `-v` to curl to see request/response headers.

## Error Handling

**"Connection refused"**
- The GraphQL server may not be running. Check that the endpoint is correct and the server is up.
- Verify with: `curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT"`

**"400 Bad Request" or "Syntax Error"**
- Check the query syntax. GraphQL queries must be valid.
- Ensure JSON is properly escaped in the `-d` payload.

**"401 Unauthorized" or "403 Forbidden"**
- Include the correct authentication header.
- Verify the token is valid and has the required scopes.

**"Cannot query field" errors**
- Run an introspection query to check available fields on the type.
- The schema may have changed -- re-inspect with `__schema`.