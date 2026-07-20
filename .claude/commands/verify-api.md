Verify the `$ARGUMENTS` API works against the real service.

Steps:
1. Read `example-api/.env` for credentials (`<SERVICE>_API_URL`, `<SERVICE>_USERNAME`, `<SERVICE>_PASSWORD`).
2. Read `app/v1/$ARGUMENTS/operations.py` to identify every HTTP call the API makes.
3. Reproduce each call with `curl -s -u <user>:<pass>` against the real URL.
4. After the create flow, make a GET/search call to confirm the resource exists with the expected permissions.
5. Report the HTTP status of every call and the final verified state.

For SonarQube group creation the three calls are:
- `POST /api/user_groups/create?name=<name>`
- `POST /api/permissions/add_group?groupName=<name>&permission=<perm>`
- `POST /api/permissions/add_group_to_template?groupName=<name>&templateName=<template>&permission=<perm>`

Verify with:
- `GET /api/permissions/groups?permission=admin` — group should appear with all expected permissions
