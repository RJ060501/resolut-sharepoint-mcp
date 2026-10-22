# Ubuntu / WSL2 revision verification

This is a development-workflow and documentation update to application 0.1.0,
not a newly verified Microsoft 365 deployment.

## Checks performed on this revision

- Application suite rerun: **113 passed, 10 skipped**, 13.56 seconds.
- Shell script syntax check passed (`bash -n`).
- `setup_ubuntu.sh --check` passed on this Linux container with Python 3.13.5.
- Help output, unknown-option rejection, and missing-interpreter rejection passed.
- VS Code JSON settings/launch/extensions parsed successfully.
- Runtime source files, direct requirements, dev requirements, and pyproject were
  byte-for-byte compared with the original archive and are unchanged.
- Archive integrity and SHA-256 manifest were checked during packaging.

Results are in `reports/ubuntu-update-tests.txt`, `reports/ubuntu-update-tests.xml`,
and `reports/ubuntu-workflow-checks.json`.

## What was not verified

This test host is a Linux container, NOT the user's Ubuntu-on-WSL2 machine.
The actual WSL integration, VS Code UI, apt package installation, helper's full
pip installation path, and full dependency release gate were not executed here.
The helper's preflight success does not prove dependency installation succeeds.

Nine SDK HTTP tests remain skipped because the `mcp` package is absent; one MSAL
import test remains skipped because `msal` is absent. The local PDF parser is
pypdf 5.9.0, not the delivery pin 6.21.2. The existing release checker continues
to require the pinned packages and non-skipped SDK tests before deployment.
No live OAuth, Graph, selected site grant, Claude tool, DNS, TLS, firewall,
PowerShell provisioning, systemd host, or company-policy verification was performed.

No changes were made to the user's Microsoft tenant, remote repository, host,
permissions, or Claude organization. A local synthetic pass is not a live release.

## Required next steps

In Ubuntu, install the supported Python environment and run:

```bash
bash scripts/setup_ubuntu.sh
source .venv/bin/activate
python scripts/verify_release.py
```

Then complete `docs/ENVIRONMENT_CHECKLIST.md` and `docs/LIVE_ACCEPTANCE.md` in the
company environment. Retain the original `TEST_REPORT.md` as historical evidence.
