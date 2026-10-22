# Delivery verification report

## Result

**113 tests passed; 10 tests skipped; 0 test failures** in the local suite.
This is **not** a passing live Microsoft 365 / Claude deployment result.

Command executed:

```text
PYTHONPATH=src pytest -q --junitxml=reports/local-tests.xml
```

See `reports/local-tests.txt` for the actual pytest output and
`reports/local-tests.xml` for the machine-readable results. The runtime environment
and installed versions are recorded in `reports/environment.json`.

## What actually ran

| Check | Result |
|---|---|
| Approved/excluded/pending/unknown site decisions | Passed against synthetic fixtures |
| Human-access vs AI-access distinction | Passed against synthetic fixtures |
| Per-user file access, revocation, cross-user isolation | Passed against synthetic fixtures |
| New files inherit site approval; version and move handling | Passed against synthetic fixtures |
| Mid-request registry blocking and atomic administrative replacement | Passed locally |
| Signed JWT tenant/issuer/audience/client/scope/time validation | Passed with real local RSA signatures and PyJWT |
| Fixed JWKS endpoint, caching, stale-key refusal | Passed with mocked HTTP transport |
| OBO assertions, Graph-scope checks, no broad/app-only fallback | Passed using an injected fake MSAL client |
| Graph pagination, redirect restrictions, safe errors, bounded retries | Passed using httpx MockTransport |
| No Graph bearer token forwarded to preauthenticated download host | Passed with mocked HTTP requests |
| TXT, DOCX, PDF extraction | Passed with actual local parser subprocesses |
| Unsupported, malformed, encrypted, empty, oversized input and output limits | Passed locally |
| Synthetic policy/demo CLI | Executed successfully; output in reports/synthetic-demo.txt |
| Configuration validation and Python syntax compilation | Executed successfully |
| Synthetic DOCX/PDF layout | Rendered and visually inspected, one page each |

These tests do not prove Microsoft's effective permissions or Claude's actual
OAuth client behavior. The synthetic identity and ACL fixtures are a test model,
not a substitute for those systems.

## Explicit skips and environment limits

**Nine official-MCP-SDK HTTP tests were skipped because `mcp` was not installed.**
**One actual-MSAL import test was skipped because `msal` was not installed.**
Package-index access was unavailable in the build environment, so these packages
could not be installed. No replacement/fake SDK was used to manufacture a pass.
The implementation's SDK API was checked against official v2.3.0 source, but the
ASGI adapter was not executed here.

Local PDF extraction ran with **pypdf 5.9.0**, while the delivery requirement is
**pypdf 6.21.2**. Repeat extraction tests with the deployment dependency set.
Other installed test versions are listed in the environment JSON. A clean complete
dependency resolution, hash lock, and vulnerability scan remain required.

The release checker was also executed. It **correctly failed with exit status 1**
for missing MCP; see `reports/release-gate.txt`. On the workstation/CI, it requires
MCP, MSAL, and the pinned PDF version and sets `REQUIRE_SDK_TESTS=1` so missing
integration dependencies become failures instead of skips.

## Not run and not claimed

- No actual Entra OAuth code/PKCE/refresh or MSAL token exchange.
- No real Graph requests, selected-resource grants, or tenant ACL verification.
- No Claude connector registration or end-to-end tool invocation.
- No company server, systemd, Caddy, DNS, TLS, or firewall deployment.
- No PowerShell execution; the provisioning script was not tenant-tested.
- No dependency supply-chain audit, penetration test, or legal/security sign-off.
- No production load/large-site performance validation.
- No changes to any company account, site, repository, or permission.

## Required next gate

On an approved, internet-enabled build workstation:

```text
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip install --no-deps -e .
python scripts/verify_release.py
```

Then resolve/review the deployment lock and complete `docs/LIVE_ACCEPTANCE.md`.
**Company-data deployment remains no-go until those installation and live checks
pass.** The delivered code and locally passed policy tests do not waive them.
