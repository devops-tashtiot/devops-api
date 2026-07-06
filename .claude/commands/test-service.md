Write tests for the `$ARGUMENTS` service module in `tests/v1/$ARGUMENTS/`.

Follow the pattern from `tests/v1/sonarqube/` exactly:

1. Read `app/v1/$ARGUMENTS/routes.py`, `operations.py`, `schemas.py`, and `conf.py` to understand all endpoints and operations.

2. Create `tests/v1/$ARGUMENTS/conftest.py`:
   - `mock_<service>_client` fixture: `MagicMock()` with `AsyncMock` on each HTTP method used (post/put/delete), returning a `MagicMock` with `status_code=200`
   - `client` fixture: minimal `FastAPI()` app with only this service's router, wrapped in `TestClient`

3. Create `tests/v1/$ARGUMENTS/test_<service>_routes.py`:
   - One test per endpoint asserting status 200 and `{"status": "successful"}`
   - One test asserting `mock.call_count` equals the number of operations the route triggers
   - One test per permission/operation using `call_args_list` to verify endpoint URLs and `params`/`json` payloads
   - One test for each invalid schema input (expects 422)

4. Create `tests/v1/$ARGUMENTS/test_<service>_schema.py`:
   - Valid input passes
   - Empty/missing required fields raise `ValidationError`
   - Invalid patterns (spaces, special chars) raise `ValidationError`
   - Field length boundaries raise `ValidationError`

5. Run `pytest tests/v1/$ARGUMENTS/ -v` and confirm all tests pass before reporting done.
