# Start here: Resolut Claude / SharePoint connector

## What you received

A Python source repository for an IT-owned, read-only remote MCP connector. Each
engineering job's existing SharePoint site is the approval boundary. The existing
software director's search is not required or changed. No Docker is required.

**Read the verification limit first:** 113 local tests passed and 10 were skipped.
This environment lacked installable MCP/MSAL packages, so the actual MCP server,
Microsoft login, and Claude integration have NOT been verified here. The project
includes those tests and a release gate that refuses to pass without them. See
TEST_REPORT.md. This is source and deployment tooling, not an already deployed
company service.

## Your next actions

Open this folder from Ubuntu on WSL2 using `code .`. Follow
`docs/UBUNTU_WSL2_SETUP.md` and the README Bash commands to install the Linux
virtual environment, run the synthetic demonstration, and run
`python scripts/verify_release.py`. A green synthetic demo is useful but is not
proof of a live connector.

Before live setup, obtain the actual Claude plan/owner access, Entra/SharePoint
administrator help, an approved Linux host, a DNS name under an Entra-verified
company domain, and a small whole-site-approved synthetic test scope. These are
external prerequisites; no tenant IDs, secrets, approvals, or hosting were assumed.

This revision changes the development workflow, not the live authorization design.
The optional site-provisioning `.ps1` is an administrator utility, not a runtime or
Python development dependency. An authorized admin may run it on a managed admin
workstation or with PowerShell 7 on Ubuntu. See the new environment checklist.

First complete `docs/ENVIRONMENT_CHECKLIST.md`, then follow the guides in order:

| Guide | Outcome |
|---|---|
| docs/ENTRA_SETUP.md | Two runtime-related app registrations; separate admin grants; registry |
| docs/DEPLOYMENT.md | Protected single-instance Python service and HTTPS |
| docs/CLAUDE_SETUP.md | Own OAuth client and per-employee Microsoft sign-in |
| docs/LIVE_ACCEPTANCE.md | Positive and negative live tests and Tuesday go/no-go |
| docs/OPERATIONS.md | Blocking, revocation, ownership, rotation, incident/rollback |

## Two details that can block the deadline

The exact public MCP URL, including `/mcp`, must be registered as an acceptable
Entra Application ID URI. Arrange the verified company-domain hostname early.

`Sites.Selected` is a site-COLLECTION grant. Confirm each job is its own independent
collection, not a subsite within a collection shared with restricted jobs. The
source also checks the exact site/web boundary, but topology must be verified.

## Scope of the pilot

Three tools: list approved jobs, keyword-search filenames/folder paths, read
supported TXT/DOCX/text-PDF content with citations. No semantic index, CAD/Revit
interpretation, OCR, writes, per-file approval, or broad tenant search.

Employees keep normal SharePoint access. The connector additionally requires a
current job-site approval and a matching Microsoft selected read grant, while
Microsoft evaluates the employee's permissions. A file copied into an approved
site can inherit that site's AI eligibility; classification and other disclosure
channels still need company controls.

The Tuesday goal is a small tested deployment, not a premature company-wide
release. Do not enable real company retrieval until the live acceptance and policy
approval gates are complete.
