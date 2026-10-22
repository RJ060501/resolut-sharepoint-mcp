# Environment worksheet - fill in locally, never enter secrets here

Keep completed real-environment records in the approved internal change system,
not in the source repository. IDs are not passwords, but they are internal
configuration. Store only secret references/expiry dates in that system.

| Item | Local answer / responsible owner |
|---|---|
| Ubuntu WSL release | |
| Python version used for local tests | |
| Company private Git repository and second maintainer | |
| Claude plan, organization, and authorized connector owner | |
| Entra tenant GUID (`TENANT_ID`) | |
| Runtime API app name and client GUID (`API_CLIENT_ID`) | |
| API credential vault reference and expiry (NOT value) | |
| Claude OAuth app name and client GUID (`CLAUDE_CLIENT_ID`) | |
| Claude OAuth credential vault reference and expiry (NOT value) | |
| Separate provisioning client/approved admin tool, if needed | |
| Consent approver | |
| SharePoint administrator with target-site membership | |
| Actual SharePoint tenant hostname (`SHAREPOINT_HOST`) | |
| Entra-verified company DNS domain | |
| Final public HTTPS MCP URL (`PUBLIC_MCP_URL`, ends `/mcp`) | |
| DNS owner | |
| Approved Ubuntu server, administrator, hosting cost approval | |
| Firewall/reverse-proxy owner | |
| Certificate/renewal owner | |
| Package mirror, proxy, or TLS inspection requirements | |
| Pilot user A and pilot user B (ordinary non-admin accounts) | |
| AI policy exception/revision reference | |
| Vendor/privacy/data-processing approval reference | |
| Logging destination and retention owner | |
| Credential rotation and incident-response owner | |
| Release test report and live-acceptance evidence locations | |

Site decisions must be whole-site decisions, not approval of one sample file.

| Job | Exact site URL | Composite Graph site ID | Independent site collection? | AI decision/approver | API read-grant ID | Human permissions checked? |
|---|---|---|---|---|---|---|
| Approved pilot | | | | | | |
| Excluded synthetic test | | | | blocked | no grant | |
| Unreviewed synthetic test | | | | pending/unknown | no grant | |

Record tests that independently exercise (a) the application registry and (b) the
Microsoft Selected resource boundary. A registry refusal alone does not prove
the Microsoft grant is restrictive. Do not temporarily grant real NDA access.
