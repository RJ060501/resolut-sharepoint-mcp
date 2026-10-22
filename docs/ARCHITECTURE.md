# Architecture and scope

## The selected implementation

```text
Employee in company Claude organization
  | OAuth authorization code + PKCE, handled by Claude and Entra
  | access token intended for the Resolut API (not Microsoft Graph)
  v
HTTPS reverse proxy -> official MCP Python SDK resource server
  | validate tenant / issuer / audience / azp / user / scope / lifetime
  | read current IT-controlled site approval registry
  | MSAL delegated on-behalf-of exchange
  v
Microsoft Graph: delegated Sites.Selected
  | API app has an explicit READ grant on approved job site collections
  | Microsoft also enforces the signed-in employee's permissions
  v
Existing SharePoint job sites and supported document libraries
```

The runtime API has no application-mode read permissions, tenant-wide read scope,
write scope, provisioning scope, or approval-management tool. The separate
provisioning script is for an authorized administrator only. The software
director's search application is not a dependency and is not modified.

Three independent gates apply: a valid employee identity, a current registry
approval, and Microsoft authorization for the selected app plus employee. Library,
folder, and file restrictions are checked through delegated Graph reads; knowing a
site ID or opaque document ID is not authorization.

**Important terminology:** `Sites.Selected` grants access at the **site collection**
level. Confirm each job is an independent site collection, not a subsite beneath a
collection shared with NDA jobs. The registry rejects duplicate collection IDs
among its entries, but that check cannot discover unregistered subsites. An admin
must verify the topology before granting access. The connector also validates the
exact web ID and job URL and does not traverse subsites.

## Why no shared index in this version

Search re-enumerates permitted libraries on each request, breadth-first, and
matches filename/folder-path keywords. It does not call Microsoft Search or
DriveItem search, maintain a tenant-wide index, store document bodies, or send
files to an embeddings service. A new supported file inherits its approved site's
eligibility as soon as it is visible through Graph; no document approval is needed.

This is intentionally a small pilot. Defaults: 10 sites per call, 2,000 enumerated
items, 25 matches, 100 pages per collection, 150-second tool deadline, 4 concurrent
tools. Search reports truncated/partial coverage. Narrow searches with `job_id`.
Enumeration may be too slow for large jobs; do not solve that by adding broad
permissions. A future approved-only index requires revocation and ACL design.

## Tools

| Tool | Purpose |
|---|---|
| `list_approved_jobs()` | Approved jobs discoverable by the current employee |
| `search_approved_documents(query, job_id=None)` | Live filename/path keyword matches |
| `read_approved_document(document_id)` | Fresh authorized read, text extraction, source URL and version |

TXT supports UTF-8 or BOM-marked UTF-16. DOCX extracts paragraphs and tables plus
header/footer paragraphs. Text PDFs return page-labeled text. These are not visual
CAD, Revit, calculation, or engineering drawing interpreters. Text boxes, drawings,
revision markup, complex layouts, and other content may not be represented.
Unsupported, encrypted, empty/image-only, and oversized files return explicit
errors. No OCR and no external parser service.

The document identifier encodes a job/site/drive/item reference. It is not secret,
not a signed permission, and not sufficient to read anything. Every use is
reauthorized against current site approval, drive membership, SharePoint site
collection/web IDs, URL boundaries, and employee access.

## Authentication details

The public MCP URL is also the API's Entra Application ID URI. Entra issues a v2
access token whose audience is the API client GUID. The SDK delegates verification
to `EntraValidator`, which verifies that exact GUID with PyJWT and Microsoft's
fixed tenant JWKS. Therefore SDK URL-audience checking is explicitly disabled;
audience checking itself is **not** disabled. The checked `access_as_user` claim
is normalized to the fully qualified scope advertised in discovery.

Only the configured Claude OAuth client (`azp`) is accepted. MSAL exchanges that
API token for a Graph token scoped to delegated `Sites.Selected`. It never relays
the incoming token blindly to Graph. App-only tokens, wrong tenants, wrong
clients/audiences, invalid lifetimes, and unexpected Graph scopes are denied.

Conditional Access policies can require interactions that this minimal connector
cannot complete automatically. A failed OBO exchange fails closed. Do not weaken
Conditional Access or switch to a shared privileged identity to work around it.

## What remains an assumption

Hosting is assumed to be one company-approved Ubuntu VM, one service instance,
with a company-verified custom DNS name and HTTPS. Windows PowerShell is the
primary development walkthrough. Neither environment nor any subscription,
administrator role, job approval, or security-policy exception is presumed to
already exist. See IMPLEMENTATION_STATUS.md and LIVE_ACCEPTANCE.md.
