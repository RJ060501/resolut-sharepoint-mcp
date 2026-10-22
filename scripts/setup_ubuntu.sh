#!/usr/bin/env bash
# Local development only. No Microsoft requests, site grants, or live deployment.
set -euo pipefail
umask 077

usage() {
    cat <<'HELP'
Usage: bash scripts/setup_ubuntu.sh [--check | --help]

Run from any directory. Creates/reuses this repository's Linux .venv, installs
requirements and the editable package, and creates .env ONLY when absent.
No sudo, no tenant operations, no server exposure, no existing .env overwrite.

--check  Check the interpreter/environment without installing or writing files.
PYTHON_BIN=/path/to/python3.12 may override interpreter selection.
Python 3.12 is the deployment baseline; package-supported versions are 3.12-3.14.
HELP
}

check_only=0
case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    --check) check_only=1 ;;
    '') ;;
    *) usage >&2; exit 2 ;;
esac
if (( $# > 1 )); then usage >&2; exit 2; fi

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$root"
if [[ -n "${PYTHON_BIN:-}" ]]; then
    py="$PYTHON_BIN"
elif command -v python3.12 >/dev/null 2>&1; then
    py=python3.12
else
    py=python3
fi
command -v "$py" >/dev/null 2>&1 || {
    printf 'Python not found: %s. Install an IT-approved Python 3.12 interpreter and venv support.\n' "$py" >&2
    exit 1
}
"$py" - <<'CHECK'
import sys
if sys.platform != 'linux':
    raise SystemExit('Use the Ubuntu interpreter, not Windows Python through WSL interop.')
if not (3, 12) <= sys.version_info[:2] < (3, 15):
    raise SystemExit('Requires Python 3.12-3.14. Do not replace Ubuntu system Python; arrange an approved interpreter.')
try:
    import venv
except ImportError:
    raise SystemExit('Install the Ubuntu venv package matching this interpreter.')
print(f'Interpreter: {sys.executable}; Python {sys.version.split()[0]}')
if sys.version_info[:2] != (3, 12):
    print('Note: this version is allowed by pyproject.toml; Python 3.12 remains the documented production baseline.')
CHECK

case "$root" in
    /mnt/[a-z]/*) printf 'Warning: keep the working copy under ~/projects in Ubuntu, not a Windows-mounted drive.\n' >&2 ;;
esac
if [[ -L .venv ]]; then
    printf 'Refusing a symlinked .venv. Review it and create a repository-local Linux virtual environment.\n' >&2
    exit 1
fi
if [[ -d .venv ]]; then
    if [[ ! -x .venv/bin/python ]]; then
        printf 'Existing .venv is not a usable Linux virtual environment. Do not reuse a Windows venv.\n' >&2
        exit 1
    fi
    .venv/bin/python - <<'CHECK'
import sys
if sys.platform != 'linux' or sys.prefix == sys.base_prefix or not (3, 12) <= sys.version_info[:2] < (3, 15):
    raise SystemExit('Existing .venv is not a supported Linux virtual environment. Review and recreate it.')
CHECK
fi
if (( check_only )); then
    printf 'Environment checks passed. No package installation or file changes performed.\n'
    exit 0
fi
if (( EUID == 0 )); then
    printf 'Run development setup as your normal Ubuntu user, not root or sudo.\n' >&2
    exit 1
fi
if [[ ! -d .venv ]]; then
    "$py" -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip check
if [[ ! -e .env && ! -L .env ]]; then
    cp .env.example .env
    chmod 600 .env
    printf 'Created .env from the synthetic mock template.\n'
else
    printf 'Preserved existing .env; no credentials or settings overwritten.\n'
fi
cat <<'NEXT'
Local installation finished. This does NOT verify Microsoft or Claude.
Next, in your Ubuntu terminal:
  source .venv/bin/activate
  python -m resolut_mcp validate-config
  python -m resolut_mcp demo
  python scripts/verify_release.py

The demo requires MODE=mock. Do not add real tenant credentials to mock mode.
Read docs/UBUNTU_WSL2_SETUP.md and docs/ENVIRONMENT_CHECKLIST.md before live setup.
NEXT
