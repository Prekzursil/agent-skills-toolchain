```markdown
# agent-skills-toolchain Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions used in the `agent-skills-toolchain` Python repository. You'll learn how to structure files, write imports and exports, follow commit conventions, and organize tests. The guide also outlines common workflows and provides command suggestions for streamlined development.

## Coding Conventions

### File Naming
- Use **snake_case** for all Python files.
  - Example: `agent_utils.py`, `data_loader.py`

### Import Style
- Prefer **relative imports** within the package.
  - Example:
    ```python
    from .utils import process_agent
    from .models import AgentModel
    ```

### Export Style
- Use **named exports**; explicitly define what is exported from each module.
  - Example:
    ```python
    __all__ = ['Agent', 'AgentManager']
    ```

### Commit Messages
- Follow **conventional commit** patterns.
- Use prefixes like `feat` for features and `docs` for documentation.
  - Example:
    ```
    feat: add agent registration utility
    docs: update README with usage instructions
    ```

## Workflows

### Adding a New Feature
**Trigger:** When implementing new functionality.
**Command:** `/add-feature`

1. Create a new Python file using snake_case if needed.
2. Implement the feature using relative imports for internal modules.
3. Add named exports to the module.
4. Write or update tests in a corresponding `*.test.*` file.
5. Commit using the `feat:` prefix.
   - Example: `feat: implement agent scoring logic`

### Updating Documentation
**Trigger:** When documentation needs improvement or updates.
**Command:** `/update-docs`

1. Edit or add documentation files as needed.
2. Commit changes using the `docs:` prefix.
   - Example: `docs: clarify agent setup instructions`

### Writing Tests
**Trigger:** When adding or updating code that requires testing.
**Command:** `/write-test`

1. Create or update a test file matching the pattern `*.test.*`.
2. Write tests for the new or modified code.
3. Run tests using your preferred Python test runner.
4. Commit test changes (can be included with feature or as a separate commit).

## Testing Patterns

- Test files follow the pattern: `*.test.*` (e.g., `agent_manager.test.py`).
- The specific testing framework is not enforced; choose your preferred one (e.g., `pytest`, `unittest`).
- Place tests alongside the code or in a dedicated `tests/` directory.
- Example test file:
  ```python
  # agent_manager.test.py
  import unittest
  from .agent_manager import AgentManager

  class TestAgentManager(unittest.TestCase):
      def test_registration(self):
          manager = AgentManager()
          self.assertTrue(manager.register('test_agent'))
  ```

## Commands
| Command         | Purpose                                      |
|-----------------|----------------------------------------------|
| /add-feature    | Start the workflow for adding a new feature  |
| /update-docs    | Update or improve documentation              |
| /write-test     | Create or update tests for your code         |
```
