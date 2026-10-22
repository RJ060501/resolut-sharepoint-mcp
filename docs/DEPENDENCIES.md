# Dependencies and reproducibility

## What is pinned

`requirements.txt` pins the direct runtime dependencies, including official
`mcp==2.3.0`, `msal==1.39.0`, and `pypdf==6.21.2`. SDK API signatures were checked
against the official v2.3.0 source. This code uses `MCPServer`, not the old v1
FastMCP interface. Do not silently install a different major version.

The MCP SDK brings its own dependencies, including mcp-types and httpx2. This
application separately uses httpx 0.28.1 for its bounded Graph adapter. They are
different import namespaces; do not manually rename one to the other. Review
transitive versions and security advisories when resolving the release.

## What could not be verified here

The delivery environment had no working package-index network access and lacked
MCP and MSAL. It had pypdf 5.9.0, so local PDF tests exercised that installed parser,
not the pinned deployment parser 6.21.2. Core tests used the installed libraries
reported in `reports/environment.json`. Official-SDK HTTP tests and actual MSAL
import tests were explicitly skipped here, not replaced with fake SDK modules.

Consequently **a clean resolved installation and transitive lock are not claimed
as already verified**. The archive does not contain a fabricated uv.lock or an
invented hash manifest for uninstalled wheels. This is an external build-validation
gate, distinct from tenant-specific live acceptance.

## Create the approved deployment lock

On an approved internet-enabled build workstation matching the Linux/Python 3.12
deployment target, install the maintained `uv` CLI through your organization's
normal software procedure. Review its version and package-index policy. Then:

```bash
python scripts/lock_dependencies.py --python-version 3.12
python3.12 -m venv .venv-lockcheck
.venv-lockcheck/bin/python -m pip install --require-hashes -r requirements.lock
.venv-lockcheck/bin/python -m pip install -r requirements-dev.txt
.venv-lockcheck/bin/python -m pip install --no-deps -e .
.venv-lockcheck/bin/python scripts/verify_release.py
```

`requirements.lock` pins and hashes runtime transitive dependencies for the chosen
resolution. Review it before committing it to the private repository. Use the
same reviewed lock or approved wheelhouse for deployment. Generate a separate
platform lock if deployment platform/environment markers differ. Development
requirements are pinned separately; do not install a test-only tool into the
production runtime simply because it was present on the build workstation.

Run your approved software-composition/dependency-vulnerability scanner. A useful
optional local workflow is `pip-audit` against the resolved environment/lock after
installing that tool through your approved process. Neither a successful resolver
nor a green unit suite establishes absence of dependency vulnerabilities. Do not
freeze a known vulnerable transitive release solely for reproducibility.

`verify_release.py` checks the three critical pinned versions, `pip check`, the
full local suite with `REQUIRE_SDK_TESTS=1`, and Python source compilation. That
flag turns missing SDK/MSAL into failures, so CI cannot call mock-only coverage a
release pass. Follow this with the separate Microsoft/Claude live acceptance.
