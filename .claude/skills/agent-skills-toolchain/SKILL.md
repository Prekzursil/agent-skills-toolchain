```markdown
# agent-skills-toolchain Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions used in the `agent-skills-toolchain` Python repository. You'll learn about file naming, import/export styles, commit message conventions, and how to structure and run tests. This guide is ideal for contributors looking to maintain consistency and quality in this codebase.

## Coding Conventions

### File Naming
- Use **snake_case** for all Python files.
  - Example: `agent_utils.py`, `data_loader.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import load_agent
    from .models import AgentModel
    ```

### Export Style
- Use **named exports** to explicitly control what is exposed by a module.
  - Example:
    ```python
    __all__ = ['AgentModel', 'load_agent']
    ```

### Commit Messages
- Follow **Conventional Commits** with prefixes like `feat` and `docs`.
  - Example:
    ```
    feat: add agent initialization logic
    docs: update usage instructions in README
    ```

## Workflows

### Adding a New Feature
**Trigger:** When implementing new functionality.
**Command:** `/add-feature`

1. Create a new Python file using snake_case if needed.
2. Implement the feature using relative imports for internal modules.
3. Add named exports to expose new functions/classes.
4. Write or update tests in a corresponding `*.test.*` file.
5. Commit changes using the `feat:` prefix.
   - Example: `feat: implement agent scoring algorithm`

### Updating Documentation
**Trigger:** When updating or adding documentation.
**Command:** `/update-docs`

1. Edit or create documentation files as needed.
2. Commit changes using the `docs:` prefix.
   - Example: `docs: add setup instructions to README`

### Running Tests
**Trigger:** To verify code correctness.
**Command:** `/run-tests`

1. Locate test files matching the `*.test.*` pattern.
2. Run tests using your preferred Python test runner (e.g., `pytest` or `unittest`).
   - Example:
     ```bash
     pytest
     ```
3. Ensure all tests pass before merging changes.

## Testing Patterns

- Test files follow the `*.test.*` naming pattern (e.g., `agent.test.py`).
- The specific testing framework is not enforced; use standard Python testing tools like `pytest` or `unittest`.
- Place test files alongside the modules they test or in a dedicated `tests/` directory.
- Example test file:
  ```python
  # agent.test.py
  from .agent_utils import load_agent

  def test_load_agent_returns_agent():
      agent = load_agent('test')
      assert agent is not None
  ```

## Commands
| Command        | Purpose                                         |
|----------------|-------------------------------------------------|
| /add-feature   | Scaffold and implement a new feature            |
| /update-docs   | Update or add documentation                     |
| /run-tests     | Run all test files to verify code correctness   |
```
