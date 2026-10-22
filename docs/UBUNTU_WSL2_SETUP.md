# Ubuntu on WSL2: development setup

This guide replaces the previous Windows PowerShell development instructions.
It does not require Docker and does not change the connector's security model.
Use your normal Ubuntu user, not a root shell.

## 1. Check Ubuntu and Python first

In your Ubuntu terminal:

```bash
cat /etc/os-release
uname -r
python3 --version
command -v python3
```

The user's Ubuntu release is not yet known. Ubuntu 24.04 with Python 3.12 is the
project's documented deployment baseline. The package permits Python 3.12-3.14.
Do not assume Ubuntu 22.04's default Python meets that requirement, and do not
replace `/usr/bin/python3` or add an unapproved PPA to meet a deadline. Arrange an
IT-approved supported interpreter or a separate supported Ubuntu WSL distribution.
Do not delete your current distribution or work. A Windows venv cannot be reused.

On an approved Ubuntu workstation, install basic development tools:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git unzip ca-certificates curl
```

If the selected interpreter is separately installed, also obtain its matching venv
support. On Ubuntu 24.04 this can be `python3.12-venv`. Package installation may
need an approved proxy/package mirror. Never use `sudo pip`, `--break-system-packages`,
`--trusted-host`, or disabled TLS verification to get around installation errors.

## 2. Keep the repository on the Linux filesystem

Use `~/projects`, not an actively developed working copy under `/mnt/c`. You may
read the downloaded ZIP from Windows and extract it into Ubuntu. Example, using
your actual Windows username and download path:

```bash
mkdir -p ~/projects
unzip '/mnt/c/Users/YOUR_WINDOWS_USER/Downloads/Resolut_SharePoint_MCP_Connector_v0.1.0_Ubuntu_WSL2.zip' -d ~/projects
cd ~/projects/resolut-sharepoint-mcp
```

Extract into a fresh location. Do not overwrite an existing modified checkout.
For an existing company Git repository, clone it under `~/projects` instead and
apply these reviewed changes on a branch. The archive is not a remote Git push.

## 3. Open VS Code using WSL

Install the Windows VS Code application and Microsoft's WSL extension. From the
Ubuntu project directory run:

```bash
code .
```

Check the window's remote indicator says WSL/Ubuntu. Install the recommended
Python, Pylance, and Python Debugger extensions in that WSL environment. Select
`${workspaceFolder}/.venv/bin/python` after creating the venv, not a Windows
`python.exe`. Workspace settings now use Bash and Linux LF line endings.

## 4. Create the Linux development environment

From the repository root:

```bash
bash scripts/setup_ubuntu.sh --check
bash scripts/setup_ubuntu.sh
source .venv/bin/activate
python --version
command -v python
python -m pip --version
```

The helper prefers `python3.12`, otherwise `python3`, and validates compatibility.
You may explicitly select an installed approved interpreter:

```bash
PYTHON_BIN=/usr/bin/python3.12 bash scripts/setup_ubuntu.sh
```

It creates/reuses `.venv`, installs requirements and the editable application, and
creates `.env` from the mock template ONLY if absent. It does not modify existing
configuration, grant permissions, or start a server. If installation fails, stop
and retain the exact package error for local diagnosis. Do not edit pins blindly.

Manual equivalent, after verifying `python3` is supported:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip install --no-deps -e .
python -m pip check
if [ ! -e .env ] && [ ! -L .env ]; then
    (umask 077; cp .env.example .env)
fi
```

Do not run setup from an existing Windows-created `.venv`; create a fresh Linux
venv after reviewing/backing up any files you need. The helper will not silently
remove or overwrite an unsuitable environment.

## 5. Run local checks before real credentials

The initial `.env` must have `MODE=mock` and no live identity credentials.

```bash
python -m resolut_mcp validate-config
python -m resolut_mcp demo
python scripts/verify_release.py
```

Expected synthetic demo: Alice has human access to excluded job 1002, but the
connector only returns her approved job 1001 and denies excluded retrieval.
This is not a live Graph or Claude test.

The release checker verifies pinned dependencies, runs `pip check`, and makes
missing SDK/MSAL tests failures instead of skips. A failed install/release check
is a blocker. This revision does not waive the original package's verification
limitations. See `../UBUNTU_UPDATE_REPORT.md` for what ran on this revision.

To start the local authenticated mock endpoint after tests:

```bash
python -m resolut_mcp init-mock
python -m resolut_mcp serve
```

`init-mock` is a one-time operation and refuses to overwrite local tokens. Tokens
are written to `.local/mock_tokens.json`; keep them private and out of Git. The
server listens on `127.0.0.1:8000`. In another Ubuntu terminal:

```bash
curl --fail http://127.0.0.1:8000/healthz
```

Stop with Ctrl+C. Do not port-forward, publicly tunnel, or expose this mock service.
Remote Claude organization integration uses a separately deployed HTTPS endpoint.

## 6. Git and secrets

Use a company-controlled private repository. Before the first commit inspect:

```bash
git init
git status --short
git check-ignore .env .local/mock_tokens.json config/sites.json
```

The last command should list all three paths as ignored. Review file contents
before `git add .`; use the company's approved Git authentication and scanning.
A leaked secret must be rotated, not merely removed from the latest commit.
Do not paste tokens into public JWT decoders, screenshots, shell history, or chat.
Do not store company data in synthetic fixtures or a personal Git account.

## 7. Tomorrow's live values: separate configuration

Do not add real IDs or secrets to the mock `.env`; the application rejects mixed
mock/live identity settings. Record public identifiers in an approved internal
change record. Store secret values only in the company secret manager.

For production use `/etc/resolut-mcp/live.env` on the dedicated server, starting
from `deploy/live.env.example`. The live server template has absolute server paths;
it is not a drop-in `.env` for your WSL home directory. If an explicitly authorized
live configuration test is done locally, store it in ignored `.local/live.env`,
use Linux paths to a protected local registry, and pass it explicitly:

```bash
python -m resolut_mcp --env-file .local/live.env validate-config
```

This checks configuration/registry only; it performs no Microsoft or Claude
verification. Avoid exporting live variables into the same shell used for mock
tests because environment variables take precedence over `.env` values.

## 8. Why an administrative PowerShell script remains

`scripts/site_permissions.ps1` is a separate privileged provisioning utility.
Python development, local tests, deployment, and the running connector do not
require PowerShell. An authorized administrator may run it on a managed Windows
admin workstation, or install supported PowerShell 7 on Ubuntu and run it with
`pwsh`. Use the official Microsoft installation steps for the Ubuntu version.
Its existing interactive sign-in must be verified on that machine; if browser
login or Conditional Access prevents it, use the approved admin workstation.
Do not enable weaker authentication or grant its elevated scopes to the reader.
The same Graph permissions API can be used via another approved administration
tool; a new privileged app is not mandatory if the organization already has one.

## Official references

- WSL filesystem placement and environment: https://learn.microsoft.com/en-us/windows/wsl/setup/environment
- VS Code with WSL: https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-vscode
- Python virtual environments: https://docs.python.org/3/library/venv.html
- PowerShell on Ubuntu (admin utility only): https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu
