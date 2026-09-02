# Advanced examples

## Missing binary (documentation defect)

A command the docs claim exists. It must be filed with this path:line, never skipped.

```console
$ cnf0037-definitely-not-a-real-command --version
cnf0037 1.0.0
```

## Documented output that does not match

Output differences must be unified-diffed, not eyeballed.

```console
$ python3 -c "print('actual-line')"
documented-other-line
```

## Credential-gated (BLOCKED, never omitted)

Commands that need credentials are reported BLOCKED. The invocation is recorded
verbatim; the secret is not expanded or printed.

```console
$ curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
{"object": "list", "data": []}
```
