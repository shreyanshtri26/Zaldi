## What changed and why

## How it was checked
- [ ] `python -m pytest -m "not live"` passes
- [ ] `cd frontend && npm run build` passes
- [ ] If SQL or the data layer changed: the affected tests pass on Postgres (`ZALDI_TEST_DATABASE_URL`)
- [ ] New behaviour has tests, including failure and permission (401/403) cases

## Docs
- [ ] README configuration table / `docs/` updated if a setting, endpoint or behaviour changed
- [ ] Line added to `CHANGELOG.md`

## Safety
- [ ] No secrets, databases, indexes or `.env` files in the diff
- [ ] No secret is logged or returned by any endpoint
