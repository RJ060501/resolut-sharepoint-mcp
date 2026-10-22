# Implementation status and handoff

The source package implements the requested minimum application. It is not a
configured or verified installation in Resolut's tenant. No tenant changes,
remote Git pushes, DNS/hosting purchases, application consent, permissions, or
Claude connector registrations were performed.

| Area | Delivered | Verification boundary |
|---|---|---|
| Site approval | Reloaded protected registry; atomic admin CLI | Local policy/admin tests |
| User identity | Tenant-specific JWT validation and MSAL OBO adapter | Signed local JWT tests; OBO injected client tests; live Entra pending |
| Graph access | Bounded delegated site/drive/item/content reads | Mock HTTP transport tests; actual Selected endpoint behavior pending |
| MCP | Official SDK v2 authenticated resource-server adapter, 3 tools | Source API checked; actual SDK HTTP tests supplied but not run in offline build |
| Search | Live approved-site enumeration, filenames/paths, pagination/limits | Synthetic traversal tests; large-site performance pending |
| Extraction | TXT/DOCX/text PDF subprocess | Actual local extraction tests; deployment pypdf version differs |
| Deployment | systemd, Caddy, private config, instructions | Configuration reviewed; not installed on an actual company host |
| Provisioning | Separate PowerShell admin grant/revoke script | Not executed against a tenant; PowerShell unavailable here |
| Governance | Plan, ownership, approvals, bypass and incident checklists | Requires company decisions and license/plan checks |

No live authentication/retrieval/authorization implementation is intentionally
stubbed out. Mock mode is an explicit synthetic test mode, not an automatic
fallback. Source completeness must not be described as proven end-to-end operation.
The critical SDK/MSAL installation and tenant tests remain blockers to that claim.

## Deliberate scope choices

No Docker, frontend, existing-search integration, OCR, vector database, Anthropic
model API calls, tenant crawler, write tools, application-only content reader,
per-file approval workflow, or shared document cache. Those are intentional scope
choices rather than missing pieces of the selected design. Site-approved copies
inherit approval; content classification is not inferred automatically.

## Expected handoff assignments

IT developer: install dependencies, complete release tests, review source, maintain
private Git repository. Entra/SharePoint administrator: identity, selected grants,
ordinary employee test accounts, topology and permissions. Infrastructure owner:
verified DNS/HTTPS, approved host, patching and restricted configuration. Claude
owner: connector setup, access and bypass controls. Business/policy owner: whole-
site data-use approval and vendor/retention authorization.

Use TEST_REPORT.md for actual delivery-time counts. Use LIVE_ACCEPTANCE.md for the
unrun tenant tests. A Tuesday demonstration should be labeled synthetic unless
those live gates have actually passed.
