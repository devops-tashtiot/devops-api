# Skill: Schema Update Best Practices

## Description
When updating Pydantic schemas (especially for external APIs like Bitbucket, Jira, or Confluence), it is crucial to ensure that the schema validations align with the external platform's documented constraints and best practices.

## Guidelines

1. **Project / Resource Keys**:
   - **Pattern**: External systems often enforce strict formatting for identifiers (like project keys). For example, Bitbucket keys should typically use the regex `^[A-Z][A-Z0-9_]*$` rather than allowing hyphens or lowercase characters.
   - **Length**: Keep keys short. Best practice for Atlassian keys is usually 3-10 characters. Avoid allowing large maximum lengths (like 255) for identifiers that form URLs or link to issue IDs.

2. **Project / Resource Names**:
   - **Pattern**: Display names can generally be more flexible. Allow spaces and standard characters (e.g., `^[a-zA-Z0-9_\-\s]+$`) to improve UI readability.
   - **Length**: Keep display names concise but flexible enough for human-readable titles (e.g., max 80-100 characters instead of 255).

3. **Validation Ranges**:
   - Always verify constraints against the target service's actual limits. If a DB schema allows 32k characters but UI components break past 1000 characters, enforce the practical limit (e.g., 1000 for descriptions).
   
4. **Implementation Steps**:
   - Modify the Pydantic `Field` attributes: update `max_length`, `min_length`, and `pattern` according to the researched limits.
   - Run tests to ensure validation constraints are properly applied.
   - Document any adjusted constraints in the corresponding module's `CLAUDE.md` and `README.md`.
