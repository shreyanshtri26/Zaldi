# Contributing to Zaldi

Thank you for helping. Zaldi is built to be understood, so small, well-tested changes are the easiest to merge.

## Ways to help

-   **Report a bug** or **suggest a feature** with the issue templates. For security problems, see [SECURITY.md](SECURITY.md) instead.
-   **Try Amazon or Flipkart** with real affiliate keys (`python scripts/check_marketplaces.py --live --record`) and tell us what the response
    looks like: those connectors have not been run against live accounts.
-   **Add a connector** for another platform ([docs/CONNECTORS.md](docs/CONNECTORS.md), section 7).
-   **Add evaluation cases**: real shopper questions that went wrong make the best tests ([docs/EVALUATION.md](docs/EVALUATION.md)).
-   **Improve the documentation.**

## Getting set up

See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): clone, create a virtual environment, `pip install -r requirements.txt`, build the frontend,
run `python wsgi.py`. No API keys are needed to run the tests.

## Making a change

1.  Open an issue first for anything large, so we can agree on the approach.
2.  Create a branch from `main`.
3.  Keep changes focused: one idea per pull request.
4.  **Write tests** for the behaviour, including failure cases and permission checks (401/403). Tests are offline: script the model, fake the
    network (`tests/fakes.py`).
5.  Run `python -m pytest -m "not live"` and `cd frontend && npm run build`. If you touched SQL or the data layer, run the affected tests on
    Postgres too (`ZALDI_TEST_DATABASE_URL`).
6.  Update the docs and the README configuration table if you add a setting or an endpoint, and add a line to [CHANGELOG.md](CHANGELOG.md).
7.  Open the pull request and describe what changed, why, and how you checked it.

## Standards we hold ourselves to

-   Never log or return a secret. New secret settings are write-only and encrypted.
-   Checks that protect money or data live in code, not only in a prompt.
-   Errors tell a person what to do next.
-   Claims are measured: if a README or docs sentence says something works, a test or a script shows it.
-   Be honest about limits in the docs ("tested against recorded responses only" beats an overclaim).

## Code of conduct

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
