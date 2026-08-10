---
name: llm-security
description: "Security guidelines for LLM applications based on OWASP Top 10 for LLM 2025. Use when building LLM apps, reviewing AI security, implementing RAG systems, or asking about LLM vulnerabilities like 'prompt injection' or 'check LLM security'. IMPORTANT: Always consult this skill when building chatbots, AI agents, RAG pipelines, tool-using LLMs, agentic systems, or any application that calls an LLM API (OpenAI, Anthropic, Gemini, etc.) — even if the user doesn't explicitly mention security. Also use when users import 'openai', 'anthropic', 'langchain', 'llamaindex', or similar LLM libraries."
---

# LLM Security Guidelines (OWASP Top 10 for LLM 2025)

Security rules for building secure LLM applications, based on the OWASP Top 10 for LLM Applications 2025.

## How to Use This Skill

**Proactive mode** — When building or reviewing LLM applications, automatically check for relevant security risks based on the application pattern. You don't need to wait for the user to ask about LLM security.

**Reactive mode** — When the user asks about LLM security, use the mapping below to find relevant rule files with detailed vulnerable/secure code examples.

### Workflow
1. Identify what the user is building (see "What Are You Building?" below)
2. Check the priority rules for that pattern
3. Read the specific rule files from `rules/` for code examples
4. Apply the secure patterns or flag vulnerable ones

## What Are You Building?

Use this to quickly identify which rules matter most for the user's task:

| Building... | Priority Rules |
|-------------|---------------|
| **Chatbot / conversational AI** | Prompt Injection (LLM01), System Prompt Leakage (LLM07), Output Handling (LLM05), Unbounded Consumption (LLM10) |
| **RAG system** | Vector/Embedding Weaknesses (LLM08), Prompt Injection (LLM01), Sensitive Disclosure (LLM02), Misinformation (LLM09) |
| **AI agent with tools** | Excessive Agency (LLM06), Prompt Injection (LLM01), Output Handling (LLM05), Sensitive Disclosure (LLM02) |
| **Fine-tuning / training** | Data Poisoning (LLM04), Supply Chain (LLM03), Sensitive Disclosure (LLM02) |

### Categories
### Critical Impact
### High Impact
### Quick Reference
### Key Principles
### References
