# Skill: External API Schema Update Best Practices

## Description
When updating Pydantic schemas for external APIs (e.g., Bitbucket, ArgoCD, Vault, Jira, etc.), the schema validations must align with the specific external platform's documented constraints and best practices. Do not assume general rules; always verify the constraints of the specific tool being integrated.

## General Guidelines

1. **Research Target System Constraints**:
   - Before updating any schema, search for the official documentation of the target service (e.g., ArgoCD object naming rules, Vault secret path constraints) to determine exact limits on length, characters, and formatting.
   - **Version Specificity**: Ensure that you are checking the best practices and constraints for the *specific version* of the tool that is currently deployed. Limits (like maximum lengths or allowed characters) can change between versions.

2. **Resource Identifiers (Keys/IDs)**:
   - **Pattern**: Identifiers used in URLs, IDs, or downstream integrations usually have strict formatting. Define explicit regex patterns (`pattern`) matching the tool's exact rules (e.g., must start with a letter, alphanumeric only, specific separators).
   - **Length**: Identifier lengths are typically constrained by the platform. Keep `max_length` strictly aligned with what the downstream tool safely accepts.

3. **Resource Display Names**:
   - **Pattern**: Display names can generally be more flexible. Allow spaces and standard characters to improve UI readability unless the tool specifically forbids them.
   - **Length**: Keep display names concise but flexible enough for human-readable titles, relying on the tool's database limits.

4. **RBAC & User/Group Constraints**:
   - **Admin Users**: If the target system restricts usernames (e.g., lowercase only, no purely numeric names), enforce these exact rules via regex.
   - **Admin Groups**: Group names often allow extensive characters (slashes, upper/lowercase, Hebrew letters, etc.). Do not artificially constrain them with a strict regex `pattern` unless the target service absolutely requires it.

5. **Validation Ranges & Practical Limits**:
   - Always verify constraints against the target service's actual limits. If a database schema allows 32k characters but UI components break past 1000 characters, enforce the practical limit (e.g., 1000 for descriptions).

6. **Implementation Workflow**:
   - Modify the Pydantic `Field` attributes: update `max_length`, `min_length`, and `pattern` according to the researched tool-specific limits.
   - Run tests to ensure validation constraints are properly applied locally.
   - Document any adjusted constraints in the corresponding module's `CLAUDE.md` and `README.md`.
