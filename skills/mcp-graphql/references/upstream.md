# Upstream Notes

- Upstream repo: `https://github.com/blurrah/mcp-graphql`
- Upstream runtime uses environment variables instead of CLI args.
- Key upstream variables:
  - `ENDPOINT` - GraphQL endpoint URL (default upstream value: `http://localhost:4000/graphql`)
  - `HEADERS` - JSON string for request headers
  - `ALLOW_MUTATIONS` - defaults to `false`
  - `NAME` - server name (default `mcp-graphql`)
  - `SCHEMA` - optional local file or remote schema URL
- Manual client config shape is `command: "npx"`, `args: ["mcp-graphql"]`, with env carrying the endpoint and any auth headers.
- If no endpoint is discoverable from local context, use the upstream default `http://localhost:4000/graphql` and call out that assumption.
