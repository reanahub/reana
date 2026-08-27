# Contributing

## Issues

Bug reports, issues, feature requests, and other contributions are welcome. If
you find a demonstrable problem that is caused by the REANA code, please:

1. Search for
   [already reported problems](https://github.com/search?q=org%3Areanahub+is%3Aissue+is%3Aopen).
2. Check if the issue has been fixed or is still reproducible on the latest
   `master` branch.
3. Create an issue, ideally with **a test case**.

If you create a pull request fixing a bug or implementing a feature, you can run
the tests to ensure that everything is operating correctly:

```console
$ ./run-tests.sh
```

Each pull request should preserve or increase code coverage.

If you are working on OIDC authentication or the BFF session flow, you can
additionally run `scripts/test-auth-workflow-e2e.py` by hand against a
disposable local cluster with the bundled development Keycloak (see
[deploying a REANA cluster locally](https://docs.reana.io/administration/deployment/deploying-locally/)).
It provisions two temporary Keycloak identities, drives a real browser-based BFF
login, runs the Hello World demo workflow end to end, and checks a few
auth-hardening properties, before cleaning everything up again -- useful as a
manual smoke test that unit tests alone cannot cover. It is not part of CI.
Activate the environment containing `reana-client`, clone the Hello World demo
if it is not already next to this repository, and run for example:

```console
$ python scripts/test-auth-workflow-e2e.py \
    --server-url https://localhost:30443 \
    --reana-client "$(command -v reana-client)" \
    --demo-dir ../reana-demo-helloworld
```

Both paths are validated before disposable users are created; run the script
with `--help` for the namespace, release-prefix, and cleanup options.
