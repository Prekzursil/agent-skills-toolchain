# agentify-web-chatgpt-bridge

## Goal

Define a browser- or web-mediated tool surface for interacting with the ChatGPT web product without pretending it is the same class of system as MCP-native tooling.

## Why it belongs here now

This idea is important enough to track, but it is not yet a live runnable tool with a settled browser model, session model, or maintenance boundary.

## Questions to close before promotion

- what browser automation stack is used
- how session and login handling work
- what the supported interaction contract is
- what safety and maintenance limits are acceptable
- how DOM drift or web-product changes are detected and handled

## Promotion target

Promote this note into `tools/web/<project-name>/` only when the session model, browser runtime, and smoke tests are concrete.
