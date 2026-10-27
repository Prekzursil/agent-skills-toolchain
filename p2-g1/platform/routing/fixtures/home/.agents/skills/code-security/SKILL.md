---
name: code-security
description: "Security guidelines for writing secure code. Use when writing code, reviewing code for vulnerabilities, or asking about secure coding practices like 'check for SQL injection' or 'review security'. IMPORTANT: Always consult this skill when writing or reviewing any code that handles user input, authentication, file operations, database queries, network requests, cryptography, or infrastructure configuration (Terraform, Kubernetes, Docker, GitHub Actions) — even if the user doesn't explicitly mention security. Also use when users ask to 'review my code', 'check this for bugs', or 'is this safe'."
---

# Code Security Guidelines

Comprehensive security rules for writing secure code across 15+ languages. Covers OWASP Top 10, infrastructure security, and coding best practices with 28 rule categories.

## How to Use This Skill

**Proactive mode** — When writing or reviewing code, automatically check for relevant vulnerabilities based on the language and patterns present. You don't need to wait for the user to ask about security.

**Reactive mode** — When the user asks about security, use the categories below to find the relevant rule file, then read it for detailed vulnerable/secure code examples.

### Workflow
1. Identify the language and what the code does (handles input? queries a DB? reads files?)
2. Check the relevant rules below — focus on Critical and High impact first
3. Read the specific rule file from `rules/` for detailed code examples in that language
4. Apply the secure patterns, or flag the vulnerable patterns if reviewing

## Language-Specific Priority Rules

When writing code in these languages, check these rules first:

| Language | Priority Rules to Check |
|----------|------------------------|
| **Python** | SQL injection, command injection, path traversal, code injection, SSRF, insecure crypto |
| **JavaScript/TypeScript** | XSS, prototype pollution, code injection, insecure transport, CSRF |
| **Java** | SQL injection, XXE, insecure deserialization, insecure crypto, SSRF |
| **Go** | SQL injection, command injection, path traversal, insecure transport |
| **C/C++** | Memory safety, unsafe functions, command injection, path traversal |

### Categories
### Critical Impact
### High Impact
### Infrastructure
### Medium/Low Impact
### Quick Reference
