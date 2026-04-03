---
name: codecov-cli
description: Upload and analyze code coverage reports using the Codecov CLI. Use when the user mentions codecov, coverage upload, coverage reports, or codecov flags.
---

# Codecov CLI

Upload and analyze code coverage reports directly via the `codecov` CLI or `npx codecov` through the Bash tool. Replaces the Codecov MCP server with native CLI calls.

## Prerequisites

Verify the Codecov CLI is available:

```bash
command -v codecov || npx codecov --version
```

If the dedicated CLI is not installed, `npx codecov` can be used as a fallback.

### Authentication

The `CODECOV_TOKEN` environment variable should be set before uploading:

```bash
# Check if token is set (do not print the actual value)
[ -n "$CODECOV_TOKEN" ] && echo "CODECOV_TOKEN is set" || echo "CODECOV_TOKEN is not set"
```

Tokens are available from https://app.codecov.io under repository settings.

## Upload Coverage

### Basic upload

```bash
codecov upload-process --token "$CODECOV_TOKEN" -f <coverage-file>

# Example: Upload lcov report
codecov upload-process --token "$CODECOV_TOKEN" -f coverage/lcov.info
```

### Upload with flags

Flags let you group coverage by test type (unit, integration, etc.):

```bash
codecov upload-process --token "$CODECOV_TOKEN" -f <coverage-file> --flag <flag-name>

# Example: Upload with unit test flag
codecov upload-process --token "$CODECOV_TOKEN" -f coverage/lcov.info --flag unit
```

### Upload multiple files

```bash
# Upload all coverage files in a directory
codecov upload-process --token "$CODECOV_TOKEN" -f coverage/

# Upload specific files
codecov upload-process --token "$CODECOV_TOKEN" \
  -f coverage/lcov.info \
  -f coverage/coverage-final.json
```

### Using npx (when CLI is not installed)

```bash
npx codecov --token "$CODECOV_TOKEN" -f <coverage-file>

# With flags
npx codecov --token "$CODECOV_TOKEN" -f coverage/lcov.info --flag unit
```

## Common Workflows

### Generate and upload (JavaScript/TypeScript)

```bash
# Generate coverage report
npx jest --coverage

# Upload to Codecov
codecov upload-process --token "$CODECOV_TOKEN" -f coverage/lcov.info
```

### Generate and upload (Python)

```bash
# Generate coverage report
python -m pytest --cov=src --cov-report=xml

# Upload to Codecov
codecov upload-process --token "$CODECOV_TOKEN" -f coverage.xml
```

### CI environment detection

Codecov auto-detects CI environments (GitHub Actions, GitLab CI, etc.) and populates commit SHA, branch, and build info. In CI, you typically only need:

```bash
codecov upload-process --token "$CODECOV_TOKEN" -f <coverage-file>
```

### Override commit SHA or branch

```bash
codecov upload-process --token "$CODECOV_TOKEN" \
  -f <coverage-file> \
  --commit-sha <sha> \
  --branch <branch-name>
```

## CLI Help

```bash
# General help
codecov --help

# Upload-specific help
codecov upload-process --help
```

## Supported Coverage Formats

Codecov accepts most standard coverage formats:

- **lcov** (lcov.info) -- JavaScript/TypeScript via Jest, Vitest, c8
- **Cobertura XML** (coverage.xml) -- Python, Java, .NET
- **Clover XML** -- PHP, Java
- **JaCoCo XML** -- Java, Kotlin
- **Go coverage** (coverage.out) -- Go
- **gcov/lcov** -- C/C++

## Error Handling

**"Upload failed: 401 Unauthorized"**
- Verify `CODECOV_TOKEN` is correct and has not expired.
- Ensure the token matches the repository.

**"No coverage files found"**
- Verify the coverage file path is correct.
- Run the test suite with coverage enabled first.

**"Could not detect CI provider"**
- Pass `--commit-sha` and `--branch` explicitly when running outside CI.

**CLI not found**
- Install globally: `pip install codecov-cli` or use `npx codecov`.
