# Resolut Approved Job Sites MCP Connector

An IT-owned, read-only Python connector between Claude and existing SharePoint job
sites. Site approval is independent of employee access. The existing engineering
search application is not required or changed.

**Status:** application source, synthetic fixtures, deployment configuration, and
local tests are included. This is **not a tenant-connected or production-verified
installation**. Read [TEST_REPORT.md](TEST_REPORT.md): the delivery environment
could not install MCP/MSAL, so official-SDK transport tests were skipped here.
They must pass on your workstation, followed by Microsoft/Claude live acceptance.
No company data or credentials were used.

## Start in Ubuntu on WSL2 / VS Code

Use the Ubuntu Bash terminal, not Windows PowerShell. Keep the working copy under
`~/projects/resolut-sharepoint-mcp` in Ubuntu's filesystem and open it using
`code .` with VS Code's WSL extension. Do not reuse a Windows virtual environment.

Read [Ubuntu/WSL2 setup](docs/UBUNTU_WSL2_SETUP.md) for prerequisites and extraction.
Python 3.12 is the documented production baseline. The package supports Python
3.12-3.14; the helper rejects unsupported interpreters instead of changing pins.

```bash
bash scripts/setup_ubuntu.sh --check
bash scripts/setup_ubuntu.sh
source .venv/bin/activate
python -m resolut_mcp validate-config
python -m resolut_mcp demo
python scripts/verify_release.py
```

The helper creates a local Linux `.venv`, installs dependencies and the package,
and copies `.env.example` only when `.env` does not already exist. It does not run
sudo, modify tenant permissions, connect to Claude, or start a public server.
Package installation requires the approved package network/index. Do not use
`sudo pip`, bypass TLS verification, or change pinned versions to hide errors.

The synthetic demo is not an OAuth/MCP network test. `verify_release.py` requires
the pinned SDK/MSAL/PDF versions and the actual SDK tests; a failure is a blocker.
The original verification limits are recorded in TEST_REPORT.md. New Ubuntu
revision checks are recorded in UBUNTU_UPDATE_REPORT.md.

After installation/tests, to run the authenticated local mock endpoint:

```bash
python -m resolut_mcp init-mock  # Once; refuses to overwrite existing tokens.
python -m resolut_mcp serve
```

Keep tokens in `.local/mock_tokens.json` private. Local mock mode binds only to
loopback; do not publish it. Your shared live connector is a separate deployed
service, not a laptop WSL session. Use Ctrl+C to stop the local server.

For tomorrow's administrator work, use the detailed
[environment checklist](docs/ENVIRONMENT_CHECKLIST.md) and record the two distinct
application client IDs in [the environment worksheet](docs/ENVIRONMENT_WORKSHEET.md).

## Live setup: execute in this order

1. [Architecture and assumptions](docs/ARCHITECTURE.md): confirm independent job
   site collections, approved hosting, owner access, and a small synthetic pilot.
2. [Entra and SharePoint setup](docs/ENTRA_SETUP.md): API app, separate Claude OAuth
   client, selected site grants, protected registry, and pilot assignments.
3. [Deployment](docs/DEPLOYMENT.md): single Ubuntu VM, systemd, company DNS, HTTPS,
   private credentials and read-only application files. No Docker.
4. [Claude setup](docs/CLAUDE_SETUP.md): register the remote connector with the
   separate OAuth client, and connect each employee's Microsoft account.
5. [Live acceptance and Tuesday gate](docs/LIVE_ACCEPTANCE.md): prove both allowed
   retrieval and employee-visible/AI-excluded job denial before company use.

Supporting references: [operations](docs/OPERATIONS.md),
[security boundaries](docs/SECURITY.md), [dependencies](docs/DEPENDENCIES.md),
[official sources](docs/SOURCES.md), [implementation status](docs/IMPLEMENTATION_STATUS.md).

## Repository layout

```text
src/resolut_mcp/    MCP adapter, Entra/OBO, registry, Graph, tools, parsers, CLI
config/            Fabricated example registry and separate synthetic policy
fixtures/          Harmless TXT, DOCX, PDF and mock permission data
tests/             Policy, JWT, Graph transport, extraction, admin, actual SDK tests
scripts/           Separate admin grant script; dependency and release checks
deploy/            Live environment template, systemd unit, Caddy configuration
docs/              Setup, operations, security, acceptance, sources
reports/           Local test results and dependency versions
.github/workflows/ CI that requires SDK tests, not just mocks
```

## Search limitations

Search matches filenames and folder paths, not document contents. It enumerates
only approved sites, with pagination and coverage limits. There is no persistent
catalog or body cache to purge. Search results and reads are checked again before
return. Supported files added to approved sites need no separate approval. A
copied NDA file placed in an approved site can become eligible; site-level
controls do not classify content automatically.

## Git

Keep this in a company-owned private repository, with a second IT maintainer.
Review `git status --short` before committing. `.env`, local tokens, real registry
files, logs, and local databases are ignored. Files named `*.example` contain only
placeholders. Do not put real project files into fixtures. Creating/pushing a
remote repository requires your organization's normal authorization; this archive
has not changed any remote repository.

```bash
git init
git add .
git status --short
git commit -m "Add IT-owned approved-job SharePoint MCP connector"
```

Add the authorized company remote afterward. Do not use a personal public repo
for company code, credentials, configuration, or engineering content.
# resolut-sharepoint-mcp
# resolut-sharepoint-mcp
