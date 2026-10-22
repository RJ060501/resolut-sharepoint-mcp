# Ubuntu / WSL2 development revision

Based on application version 0.1.0. This is a development-workflow/documentation
revision, not a new or live-validated connector implementation.

- README and START_HERE now use Ubuntu Bash rather than Windows PowerShell.
- Added a guarded `scripts/setup_ubuntu.sh` for a Linux virtual environment.
- Added WSL interpreter/Bash/LF settings and Python extension recommendations.
- Added `.gitattributes` with binary exceptions.
- Added detailed Ubuntu setup, workplace prerequisites, and a no-secrets worksheet.
- Kept the separate privileged admin utility, with its role made explicit.
- Added protection against accidentally committing `deploy/live.env`.
- Preserved all `src/resolut_mcp` application files and dependency pins unchanged.
- Original test report remains historical. Revision checks are recorded separately.

No company app registration, permission, DNS, firewall, Claude, Git remote, or
hosting configuration was changed. Live acceptance is still required.
