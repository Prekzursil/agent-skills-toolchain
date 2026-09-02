---
name: "source-command-e2e"
description: "Generate and run end-to-end tests with Playwright. Creates test journeys, runs tests, captures screenshots/videos/traces, and uploads artifacts."
---

# source-command-e2e

Use this skill when the user asks to run the migrated source command `e2e`.

## Command Template

# E2E Command

This command invokes the **e2e-runner** agent to generate, maintain, and execute end-to-end tests using Playwright.

## What This Command Does

1. **Generate Test Journeys** - Create Playwright tests for user flows
2. **Run E2E Tests** - Execute tests across browsers
3. **Capture Artifacts** - Screenshots, videos, traces on failures
4. **Upload Results** - HTML reports and JUnit XML
5. **Identify Flaky Tests** - Quarantine unstable tests

## When to Use

Use `/e2e` when:
- Testing critical user journeys (login, trading, payments)
- Verifying multi-step flows work end-to-end
- Testing UI interactions and navigation
- Validating integration between frontend and backend
- Preparing for production deployment

## How It Works

The e2e-runner agent will:

1. **Analyze user flow** and identify test scenarios
2. **Generate Playwright test** using Page Object Model pattern
3. **Run tests** across multiple browsers (Chrome, Firefox, Safari)
4. **Capture failures** with screenshots, videos, and traces
5. **Generate report** with results and artifacts
6. **Identify flaky tests** and recommend fixes

## Example Usage

```
User: /e2e Test the market search and view flow

Agent (e2e-runner):
# E2E Test Generation: Market Search and View Flow

## Test Scenario Identified

**User Journey:** Market Search → View Results → Click Market → View Details

**Test Coverage:**

### Generated Test Code
### Running Tests
### Run the generated test
### Test Report
### Test Artifacts
