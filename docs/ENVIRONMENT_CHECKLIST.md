# Workplace readiness checklist: Resolut Claude / SharePoint connector

Use with `UBUNTU_WSL2_SETUP.md`, `ENTRA_SETUP.md`, `DEPLOYMENT.md`,
`CLAUDE_SETUP.md`, and `LIVE_ACCEPTANCE.md`. This is an implementation checklist,
not an assertion that any company access or policy change has been approved.

## Target and critical path

The Tuesday target remains a limited, authorized pilot on a small set of existing
job sites. Each job has its own SharePoint site. Employees retain normal human
access; the connector independently excludes unapproved jobs.

Creating an application/client ID and entering a tenant ID is necessary but not
sufficient. The dependency chain is:

Approved host/domain + two app registrations + consent + selected site grants +
registry approval + installed/tested code + working OAuth/Graph + Claude setup +
negative security tests + business authorization.

| Priority | Task | Owner to arrange | Completion evidence |
|---|---|---|---|
| First | Confirm pilot/data policy and Claude organization owner | IT lead, business owner, privacy/legal as needed | Written authorization and owner available |
| First | Confirm approved HTTPS host and verified company domain | Infrastructure/DNS/network administrators | Host, domain, access and deployment approval |
| First | Create two separate single-tenant app registrations | Entra application administrator/authorized app creator | Two application client IDs; correct roles/scopes |
| First | Arrange consent and separate site-grant administration | Consent approver and SharePoint administrator | Approved permissions; admin has target-site membership |
| First | Select approved/excluded test sites and two ordinary users | Project owner and SharePoint administrator | Whole-site decisions, site IDs, test access matrix |
| Before live | Install and verify in Ubuntu WSL and on target build | You / IT reviewer | Full dependency/SDK test results, reviewed lock |
| Before live | Deploy protected service and public discovery | You / host and network administrators | HTTPS, metadata and anonymous 401 checks |
| Before live | Connect through company Claude and test both boundaries | Claude owner, you, pilot users | Live positive/negative results |
| Go/no-go | Sign off, restrict bypass, assign operations | IT lead / security / business owner | Accepted limitations, revocation test, named owner |

## 1. Confirm authority, data handling, and scope

- [ ] Identify the IT sponsor and the person who can authorize the pilot.
- [ ] Obtain a documented policy exception/revision when the existing AI policy
      does not permit company-storage integrations. Building locally with fake
      data is distinct from authorizing disclosure of real project information.
- [ ] Have the business/project owner approve the ENTIRE contents of each pilot
      job site for the intended processing; approving one test file is not enough.
- [ ] Confirm NDA/client terms, commercial vendor terms, retention, processing
      locations, and incident handling through the appropriate reviewers. Do not
      assume that 'no model training' means 'no processing or retention'.
- [ ] Set a small measurable pilot goal: list approved jobs, find filenames, read
      a TXT/DOCX/text PDF, summarize with a source reference, and deny excluded jobs.
- [ ] Record a second IT maintainer and the approved private repository.

**Done when:** there is a named sponsor, a permitted synthetic test scope, and a
clear decision process for real company content. No schedule pressure waives it.

## 2. Confirm Claude organization administration

- [ ] Record the actual company Claude plan and organization, not a personal plan.
- [ ] Have an owner or appropriately authorized administrator available to add a
      custom Web connector and configure 'Use your own OAuth client'.
- [ ] Confirm individual pilot users have access to the company organization.
- [ ] Review available connector controls. Prevent an unrestricted Microsoft 365
      connector or unapproved integration from bypassing this site's approval rules.
- [ ] Do not use a shared API key/static bearer credential as employee identity.
      This application's design needs per-user OAuth sign-in.

**Done when:** the administrator has verified the required options in the actual
organization and can complete connection setup after the HTTPS endpoint exists.

Reference: [Anthropic remote connectors][A1].

## 3. Choose production hosting and the final MCP URL early

- [ ] Select an approved, always-on company server/cloud VM. The supplied baseline
      is a dedicated Ubuntu 24.04 host with Python 3.12, one service process, systemd,
      and Caddy. It is not the user's WSL laptop or a personal home server.
- [ ] Obtain deployment/admin access, budget approval where needed, and an owner
      for OS updates and monitoring. Follow company capacity standards; validate
      actual memory/concurrency/large-file behavior during the pilot.
- [ ] Reserve a company-controlled hostname under a domain verified in Entra.
- [ ] Set the exact endpoint, including its path, for example:

```text
https://mcp.YOUR-VERIFIED-COMPANY-DOMAIN/mcp
```

- [ ] Use that same exact URL for `PUBLIC_MCP_URL`, the API Application ID URI,
      protected-resource metadata, and the Claude connector entry.
- [ ] Arrange DNS A/AAAA records, valid public TLS, and renewal ownership. Do not
      publish an IPv6 record unless that path actually works.
- [ ] Do not guess a company domain from the AD domain or company name. Confirm
      the actual verified domain, SharePoint hostname, and DNS ownership.

**Done when:** hostname and hosting are approved and the API URI can be registered.
A working WSL `localhost` endpoint does not satisfy remote hosting.

Reference: [Anthropic authentication][A2], [remote network requirements][A1].

## 4. Create the runtime API app registration

Suggested name: `Resolut Approved Job Sites API`.

- [ ] Create a single-tenant app registration; record Application (client) ID as
      `API_CLIENT_ID` and Directory (tenant) ID as `TENANT_ID`.
- [ ] Do not confuse either client GUID with the application Object ID or the
      Enterprise application's service-principal Object ID.
- [ ] In Expose an API, set the exact HTTPS MCP URL as Application ID URI.
- [ ] Expose delegated scope `access_as_user`, enabled, admin-consent-only in this
      design. Its full name is the MCP URL plus `/access_as_user`.
- [ ] Set `api.requestedAccessTokenVersion` to `2` without replacing the rest of
      the manifest. The application validates v2 API tokens.
- [ ] Add Microsoft Graph **Delegated** `Sites.Selected`, not the application
      variant, and obtain administrator consent for this deployment.
- [ ] Remove unnecessary default Graph permissions. Do not add `Sites.Read.All`,
      `Files.Read.All`, write permissions, or provisioning scope to the reader.
- [ ] Create a supported credential for Graph on-behalf-of requests: preferably
      a managed certificate/private-key process, or a tracked short-lived client
      secret for an approved pilot. Record the secret VALUE securely, not Secret ID.
- [ ] Configure exactly one credential type; the existing code supports
      `API_CLIENT_SECRET`, or PEM `API_CERTIFICATE_PATH` with its thumbprint.
- [ ] Set expiry/rotation ownership. The API credential belongs on the server,
      not in Claude or Git.

**Done when:** an administrator has reviewed the app, scope, API URI, v2 token
setting, delegated Graph consent, and protected credential handling.

Reference: [Selected permissions][M1], [OBO flow][M3].

## 5. Create the separate Claude OAuth client registration

Suggested name: `Resolut Claude Connector OAuth Client`.

- [ ] Create a distinct single-tenant registration. Record its application client
      GUID as `CLAUDE_CLIENT_ID`.
- [ ] Add the Web redirect URI for the hosted Claude interface exactly:

```text
https://claude.ai/api/mcp/auth_callback
```

- [ ] Use the authorization-code flow; do not enable implicit token issuance or
      invent a localhost callback for the hosted Claude connector.
- [ ] Add the runtime API's delegated `access_as_user` permission under My APIs.
      This client should not have direct SharePoint/Graph read scopes.
- [ ] Obtain required administrator consent and configure authorized-client
      preauthorization on the API according to the deployment guide/tenant policy.
- [ ] Create its own client secret, separate from the API app credential. Store
      it securely for the Claude organization administrator to enter there.
- [ ] Do not put the Claude OAuth secret in `API_CLIENT_SECRET`. There is no
      `CLAUDE_CLIENT_SECRET` variable in this server's configuration.
- [ ] Restrict pilot assignments on the relevant enterprise apps where supported.
      Use ordinary test accounts, not Global Administrator sessions.
- [ ] Test MFA/Conditional Access/device or location policies across sign-in and
      OBO. Keep them enabled. This build does not promise full claims-challenge
      recovery; a repeated step-up/consent failure is a live compatibility blocker.

**Done when:** both distinct IDs are recorded, credential placement is understood,
and the pilot identities can request access under the approved tenant policies.

Reference: [Anthropic authentication][A2], [consent roles][M4], [OBO][M3].

## 6. Arrange a separate administrator for selected site grants

Consent and site grants are separate tasks. Neither creates the other.

- [ ] Identify an approved provisioning tool/client, separate from both runtime
      registrations. An existing authorized admin tool may be reused.
- [ ] If using this package's Graph PowerShell helper without an existing
      provisioning client, create/configure the separate admin registration
      described in ENTRA_SETUP.md. This is an admin-only tool, not a third runtime
      service or permanent dependency of the connector.
- [ ] Arrange consent for the provisioning tool's delegated `Sites.FullControl.All`
      scope. Keep that elevated authority away from the runtime reader.
- [ ] Have a SharePoint Administrator (or authorized higher role) who is also a
      member of each target site execute the grant workflow, as documented by
      Microsoft for delegated site permission creation.
- [ ] Confirm the signed-in administrator has permission to consent if doing both
      tasks. SharePoint Administrator alone is not proof of Entra consent authority.
- [ ] Use the Resolve/List/dry-run steps before making a change; review existing
      grants, including any broader grant to the reader that would need correction.
- [ ] Grant role **read** to `API_CLIENT_ID` on each approved site. Do not grant
      access to `CLAUDE_CLIENT_ID` instead and do not grant the entire tenant.
- [ ] Record each returned permission ID for independent revocation.
- [ ] Do not grant excluded/unknown jobs. Retire or restrict provisioning consent
      after use according to company practice.

The `.ps1` helper may run on a managed admin workstation or supported PowerShell 7
on Ubuntu. This does not require changing Python development back to PowerShell.
Use an approved administration mechanism rather than pasting bearer tokens into
curl commands or sharing them in chat.

**Done when:** each approved site's resource permissions show a read grant for the
correct API client, and excluded sites have no corresponding grant.

Reference: [Create site permission and required roles][M2], [Selected scopes][M1].

## 7. Inventory only the pilot sites and verify topology

- [ ] Confirm each job is an independent site collection, not merely a hub
      association, library/folder, or subsite in a collection shared with other jobs.
      `Sites.Selected` grants at the site-collection level.
- [ ] Record the exact `tenant.sharepoint.com` host; the code targets commercial
      Microsoft 365. Sovereign/national clouds need a reviewed code/config change.
- [ ] Resolve each known site URL to the composite Graph site identifier:

```text
tenant.sharepoint.com,site-collection-guid,web-guid
```

- [ ] Select one or two approved test sites, an excluded synthetic test site that
      the engineer can open, and a pending/unknown case. Never approve a real NDA
      site just to test the deny path.
- [ ] Identify unique library/folder/file permissions and build a test where pilot
      user A can read a file but pilot user B cannot.
- [ ] Use harmless synthetic TXT, DOCX, and text-PDF files. Entire-site eligibility
      still needs review before a site can be marked approved.
- [ ] Check the actual formats and workload. This version does not read native
      Revit/AutoCAD, OCR scanned PDFs, or provide full-text semantic search.
- [ ] Check for shortcuts/cross-site references and test denial.

**Done when:** actual IDs, owners, whole-site approvals, and human access test
expectations are recorded in the protected worksheet.

## 8. Configure the registry and live variables

- [ ] Create an empty protected registry, then add only reviewed pilot entries.
      The supplied `add` command starts them as pending.
- [ ] Mark approved only after whole-site business approval and the separate
      Microsoft read grant. Leave NDA/unknown jobs blocked or absent.
- [ ] Set actual values in `/etc/resolut-mcp/live.env` on the server. Start from
      `deploy/live.env.example`, not the local mock `.env`.

| Server setting | Obtain from / check |
|---|---|
| `MODE=live` | Explicit production mode; never publish mock |
| `TENANT_ID` | Directory tenant GUID |
| `API_CLIENT_ID` | Runtime API app client GUID |
| `CLAUDE_CLIENT_ID` | Separate Claude OAuth client GUID |
| `API_CLIENT_SECRET` OR certificate settings | Protected API credential only |
| `PUBLIC_MCP_URL` | Exact verified-domain HTTPS URL ending `/mcp` |
| `SHAREPOINT_HOST` | Actual commercial SharePoint hostname |
| `REGISTRY_PATH` | `/etc/resolut-mcp/sites.json` |
| `DOWNLOAD_HOSTS` | Exact verified SharePoint download hosts, no wildcard |

- [ ] Make service files/config root-managed and read-only to the service account.
- [ ] Set `DOWNLOAD_HOSTS` initially to the tenant host. If a legitimate file uses
      another host, verify it locally before adding the exact hostname. The code
      rejects arbitrary redirects; do not disable that check.
- [ ] Do not export live credentials into a shell used for the mock demo. Do not
      commit filled registries or env files.

**Done when:** `validate-config` succeeds with the explicit live configuration and
with service-user access. This command does NOT prove Microsoft connectivity.

## 9. Resolve dependency, network, and deployment requirements

- [ ] In Ubuntu WSL run the setup helper and full release checker. Keep any
      installation failures visible; do not interpret skipped SDK tests as a pass.
- [ ] Build/review the transitive dependency lock and vulnerability review as
      described in DEPENDENCIES.md, then test that dependency set on the target.
- [ ] Arrange approved package-index access, proxy configuration, DNS, system time,
      and trusted CA certificates. Corporate TLS inspection must use approved
      trust configuration; do not disable validation or bypass company controls.
- [ ] Permit server outbound HTTPS to Entra discovery/token/JWKS, Microsoft Graph,
      and verified SharePoint/download hosts. Provide approved OS/package update
      and certificate-renewal connectivity separately.
- [ ] Permit inbound HTTPS from Anthropic's current published cloud IP ranges,
      and approved external testing sources, if enforcing source restrictions.
      An engineer's VPN connection does not make a remote connector reachable.
- [ ] Configure Caddy/corporate reverse proxy and TLS renewal. ACME may need extra
      certificate-validation reachability; coordinate it with source allowlisting.
- [ ] Do not expose port 8000 publicly. Keep the service loopback-only, with HTTPS
      termination/proxy in front. Restrict administrative SSH by company policy.
- [ ] Ensure the WAF/proxy does not remove Authorization or WWW-Authenticate,
      block the discovery routes, impose an unrelated interactive login, or break
      streaming/timeout behavior. Do not log token headers or document bodies.
- [ ] Install/run the single-instance systemd service under its restricted account.
      Additional instances are outside the current registry-propagation design.

**Done when:** service health is live, external discovery works, and an anonymous
MCP request is rejected correctly. Check from outside the private network too.

```bash
# Run with the actual approved hostname from a permitted external network.
curl --fail https://YOUR_MCP_HOST/healthz
curl --fail https://YOUR_MCP_HOST/.well-known/oauth-protected-resource/mcp
curl -i -X POST https://YOUR_MCP_HOST/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expect live health, correct resource/tenant metadata, and **401** with the OAuth
challenge on the anonymous MCP request. Health/readiness alone does not prove
OAuth, employee authorization, or Graph access.

Reference: [Remote network requirements][A1], [OAuth discovery][A2].

## 10. Connect Claude and test the real authorization boundaries

- [ ] Organization owner adds the custom Web connector with the exact MCP URL.
- [ ] Select per-user sign-in and the organization's own OAuth client.
- [ ] Enter the Claude OAuth client ID and its own secret, NOT the API credential.
- [ ] Pilot user A connects with their ordinary work account and runs all three
      tools. Pilot user B signs in separately.
- [ ] Verify TXT/DOCX/text-PDF extraction and valid citations/source links.
- [ ] Verify excluded jobs stay unavailable even when the employee can open them
      in SharePoint, including requests by exact site/document identifiers.
- [ ] Verify unique file permissions using A and B. A site being approved cannot
      override an individual employee's lack of access to a file.
- [ ] Independently test Microsoft's selected-resource enforcement. The local
      registry rejecting an excluded job does not by itself prove Graph would
      reject it. Use harmless synthetic scope and protected local tooling; keep
      tokens and returned metadata private. Do not add broad runtime scopes.
- [ ] Test removal of a Microsoft grant while the synthetic site remains locally
      approved, then test a local block separately. Verify each layer denies.
- [ ] Verify revoked employee access, unknown sites, cross-site moves/shortcuts,
      source content changes, unsupported/oversized files, token expiry, and
      cross-user isolation. Record propagation delays instead of hiding them.
- [ ] Test a harmless prompt-injection instruction inside a synthetic document;
      it must not expand the reader's permissions or edit approvals.
- [ ] Confirm search coverage/time limits with a representative job. Default scan
      limits may truncate large sites; explain coverage in the pilot, not as a
      complete tenant search result.

**Done when:** real Claude -> MCP -> Entra -> Graph -> SharePoint tests pass with
ordinary users under actual tenant policies. Keep evidence separate from mocks.

## 11. Document bypass controls, operations, and the go/no-go decision

- [ ] Confirm no unrestricted connector is available as a workaround for NDA access
      in this pilot. Apply available organizational/Entra controls and verify them.
- [ ] Address manual upload, clipboard/paste, personal AI accounts, and copied
      documents through separate policy and applicable endpoint/browser controls.
      This connector does not block those channels by itself.
- [ ] Teach users that site approval covers future additions. Restricted material
      copied into an approved site may become eligible; content placement matters.
- [ ] Assign owners for site approval, permissions, app secrets/certificates,
      monitoring, updates, cost, and incident response.
- [ ] Protect audit access and define log retention without logging document bodies.
- [ ] Demonstrate block/revoke and emergency stop; keep the current blocked registry
      during rollback. Revocation cannot retract existing Claude conversation text.
- [ ] Obtain the actual launch decision from IT/business/security owners.

**Tuesday go:** full required local tests, live identity/Graph/Claude tests, denial
checks, approved data handling, and named operational ownership are complete.
**Tuesday no-go:** dependency/SDK failures, unknown consent/grants, broken OAuth,
untested employee isolation, missing hosting, or absent policy authorization.
A working synthetic demo remains useful but is not a production approval.

## Official references

[M1]: https://learn.microsoft.com/en-us/graph/permissions-selected-overview
[M2]: https://learn.microsoft.com/en-us/graph/api/site-post-permissions?view=graph-rest-1.0
[M3]: https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow
[M4]: https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/grant-admin-consent
[A1]: https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
[A2]: https://claude.com/docs/connectors/building/authentication
