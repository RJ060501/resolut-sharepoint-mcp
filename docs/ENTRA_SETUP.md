# Entra and SharePoint administrator setup

Do this with company authorization and initially with harmless synthetic content.
The application does not grant permissions automatically. Permission/admin roles,
Claude plan features, and Conditional Access compatibility require confirmation in
your tenant. Never paste secrets or access tokens into a chat or a public decoder.

## 1. Establish the public identifier first

Choose a hostname under an **Entra-verified company domain**, for example
`mcp.YOUR-COMPANY-DOMAIN`. Configure DNS and HTTPS as described in DEPLOYMENT.md.
The public resource identifier will be exactly:

```text
https://mcp.YOUR-COMPANY-DOMAIN/mcp
```

Do not use the literal example or the assistant's guessed company domain.
Anthropic documents that Entra must register this exact MCP URL as an Application
ID URI because Claude sends it as the OAuth resource indicator. Otherwise Entra
can reject the request with AADSTS9010010. A default third-party hosting hostname
may not satisfy your tenant's Application ID URI policy; do not bypass that policy.

Record your actual tenant GUID, public MCP URL, and exact SharePoint tenant host.
All subsequent registrations are **single tenant**.

## 2. Create the runtime API / middle-tier registration

In Entra admin center, **Identity > Applications > App registrations > New
registration** (navigation names may vary):

- Name: `Resolut Approved Job Sites API`.
- Supported accounts: this organizational directory only.
- No interactive redirect URI is needed for the API registration itself.
- Record Application (client) ID as `API_CLIENT_ID` and Directory (tenant) ID as
  `TENANT_ID`.

Under **Expose an API**:

- Set Application ID URI to the exact public MCP URL including `/mcp`.
- Add scope `access_as_user`, enabled, admin consent only.
- Suggested display: `Use Resolut's approved job-site connector as the employee`.
- Full scope: `https://mcp.YOUR-COMPANY-DOMAIN/mcp/access_as_user`.

In the manifest/API configuration set `api.requestedAccessTokenVersion` to `2`.
Do not overwrite the rest of the manifest. Tokens for this API must be v2 and have
the API client GUID as `aud`.

Under **API permissions**:

- Remove the automatically added Microsoft Graph `User.Read` if present.
- Add **Microsoft Graph > Delegated permissions > Sites.Selected**.
- Do not add Application permissions, Sites.Read.All, Files.Read.All, write scopes,
  or Sites.FullControl.All to this registration.
- Have an appropriately authorized tenant administrator grant consent.

The runtime refuses Graph token responses containing unexpected broader scopes.
Admin consent alone grants no site content: selected resource grants are separate.

Under **Certificates & secrets**, provision one runtime credential. A certificate
is preferable for maintained deployment; a short-lived, tracked client secret is
supported for an authorized pilot. Store it only on the server or in an approved
secret store. Configure either `API_CLIENT_SECRET` or
`API_CERTIFICATE_PATH` plus `API_CERTIFICATE_THUMBPRINT`, not both. The certificate
private key must be PEM and match the uploaded certificate. Never send this API
credential to Claude; it belongs only to the middle tier.

## 3. Create a distinct Claude OAuth client registration

Create `Resolut Claude Connector OAuth Client`, single tenant.
Under **Authentication > Add a platform > Web**, add this exact redirect URI:

```text
https://claude.ai/api/mcp/auth_callback
```

Use the hosted Claude callback, not localhost, wildcard URLs, or an API callback
that the application does not implement. Use authorization code flow; do not
enable implicit access-token issuance. Claude supplies PKCE.

Under **API permissions > Add a permission > My APIs**, select the API above,
then delegated `access_as_user`; grant the necessary administrator consent.
Remove default Graph User.Read. This client does not need direct Graph scopes.
Under Certificates & secrets create a separate OAuth client secret.

Record its application ID as `CLAUDE_CLIENT_ID`. Its secret is entered by the
Claude organization administrator in the connector's **own OAuth client**
configuration. Do not put that front-end client secret into `API_CLIENT_SECRET`.
The two registrations and two credentials serve different purposes.

In the API's **Expose an API > Authorized client applications**, preauthorize this
Claude client for `access_as_user` where your consent policy requires it. This is
not a substitute for Graph consent on the API registration.

In **Enterprise applications**, restrict pilot use through user/group assignment
where supported by your license/policies; enable assignment-required and assign
pilot users/groups to the relevant service principals. Keep normal MFA and
Conditional Access protections. Test the whole OBO flow with those controls;
consent, assignments, and Conditional Access are independent checks.

## 4. Provision selected site read grants from a separate admin session

An authorized administrator must resolve each known job URL and explicitly grant
read access to the **API_CLIENT_ID**, not the Claude client ID. Check that each is
an independent job site collection and that approving it means the whole site.

Use a separate, company-approved provisioning registration: single tenant public
client, Mobile/Desktop redirect `http://localhost`, delegated Graph
`Sites.FullControl.All` with administrator consent. Enable the applicable public
client sign-in configuration if required by your approved Graph PowerShell flow.
This privileged registration is **not a runtime dependency** and its credentials
must not be available to the MCP service. Restrict its use to authorized admins;
remove consent or retire it after provisioning if appropriate.

This privileged step is separate from Ubuntu/Bash application development.
The existing `.ps1` can run on an approved Windows administrator workstation or
in supported PowerShell 7 (`pwsh`) on Ubuntu. Its interactive Graph sign-in must
be tested in that environment. An existing approved provisioning client/tool may
be reused; creating a third registration is only necessary when there is no such
administrative mechanism. Never reuse the runtime API or Claude client for this.

Install Graph PowerShell authentication in that administrative environment:

```powershell
Install-Module Microsoft.Graph.Authentication -Scope CurrentUser
```

Set actual non-secret IDs and a known synthetic pilot site URL:

```powershell
$Tenant = 'YOUR-TENANT-GUID'
$AdminApp = 'SEPARATE-PROVISIONING-APP-GUID'
$ReaderApp = 'API-APP-GUID'
.\scripts\site_permissions.ps1 -Action Resolve -TenantId $Tenant `
  -AdminClientId $AdminApp -SiteUrl 'https://YOURTENANT.sharepoint.com/sites/YOURJOB'
```

The output includes the Graph site ID in the form
`hostname,site-collection-guid,web-guid`. Record it; do not substitute the site URL
or just one GUID. Confirm the site collection topology in SharePoint admin center.

```powershell
$SiteId = 'YOURTENANT.sharepoint.com,COLLECTION-GUID,WEB-GUID'
.\scripts\site_permissions.ps1 -Action List -TenantId $Tenant `
  -AdminClientId $AdminApp -SiteId $SiteId
.\scripts\site_permissions.ps1 -Action GrantRead -TenantId $Tenant `
  -AdminClientId $AdminApp -SiteId $SiteId -ReaderAppId $ReaderApp -WhatIf
# After reviewing the intended scope, repeat WITHOUT -WhatIf and confirm.
```

This runs a delegated administrator sign-in. Microsoft documents privileged
provisioning requirements; use a SharePoint Administrator who also meets target
site access requirements and the applicable scope/consent rules. Do not grant
those administrative roles to engineers just so they can use the connector.
Grant propagation and exact Graph endpoint compatibility must be tested live.

The script refuses to silently accept an existing broader grant. Save the
permission ID in your restricted change record for later revocation. Do not grant
anything to excluded job sites. `List` and `Resolve` can reveal admin-only metadata:
run them locally, never expose them as Claude tools or paste their results into AI.

## 5. Populate the protected local registry

On the deployment server, begin with an empty registry, not approved samples:

```json
{"schema_version": 1, "jobs": []}
```

Use the administrator CLI (full commands in DEPLOYMENT.md):

```bash
sudo /opt/resolut-mcp/current/.venv/bin/python -m resolut_mcp.admin \
  --registry /etc/resolut-mcp/sites.json --host YOURTENANT.sharepoint.com \
  add --job-id JOB123 --site-id 'YOURTENANT.sharepoint.com,COLLECTION-GUID,WEB-GUID' \
  --site-url 'https://YOURTENANT.sharepoint.com/sites/JOB123' \
  --name 'Job 123' --owner 'Project owner'
```

`add` creates a pending entry. After whole-site authorization and the separate
Microsoft read grant:

```bash
sudo /opt/resolut-mcp/current/.venv/bin/python -m resolut_mcp.admin \
  --registry /etc/resolut-mcp/sites.json --host YOURTENANT.sharepoint.com \
  approve --job-id JOB123 --approver 'Authorized approver' \
  --confirm-entire-site-reviewed
```

Add known NDA jobs as pending and then block them if maintaining a full register.
They need no Microsoft grant. Unknown sites remain denied without being listed.
An optional `--expires-at 2026-11-01T00:00:00Z` sets a review deadline; use your
actual approved date. Administrative notes in JSON are not sent to Claude.

## 6. Check before connecting real users

Verify Graph runtime permissions show delegated Sites.Selected only; selected
resource grants show read on reviewed site collections only; front-end permission
is the API's access_as_user; no runtime provisioning permission exists. Confirm
both applications are single tenant and the public API URI matches exactly.

Common blockers: unverified custom domain, wrong app used for site grant, default
User.Read left on the API, missing admin consent, API token version 1, missing
pilot assignments, expired credential, Conditional Access challenge, or an endpoint
that does not behave as expected under delegated Selected scopes. Resolve the
actual cause; do not add broad read scopes as a troubleshooting shortcut.
