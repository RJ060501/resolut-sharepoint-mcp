# Connect the deployed application to Claude

This package targets an organization-managed remote MCP connector. Your actual
Claude plan, administrator privileges, and organization settings have not been
verified. An organization owner must confirm that **custom Web connectors and
using your own OAuth client** are available. Do not substitute a personal account
or shared privileged bearer token if the required controls are missing.

## Prerequisites

Complete ENTRA_SETUP.md and DEPLOYMENT.md. Confirm the endpoint has working HTTPS,
returns proper OAuth resource metadata, and denies anonymous tool access. The
public URL must be the registered Entra API URI. The API credential belongs on the
server; the **separate Claude OAuth client** ID/secret belongs in Claude's approved
connector settings. Both are confidential administrative configuration.

## Organization administrator steps

Anthropic's current help instructions use these labels; navigation can change:

1. In the company Claude organization, open **Organization settings > Connectors**.
2. Choose **Add > Custom > Web**.
3. Name it `Resolut Approved Job Sites`.
4. Enter `https://YOUR-MCP-HOST/mcp`, including `/mcp`. Continue.
5. Review discovered authentication. Select **Sign in now** (OAuth), not No sign in.
6. Under OAuth client choose **Use your own OAuth client**.
7. Enter the distinct `CLAUDE_CLIENT_ID` and that registration's client secret.
   Do not enter `API_CLIENT_ID` or its server-side secret here.
8. Do not configure a fixed Authorization header or shared API key.
9. Save/add the connector and restrict availability to the pilot through the
   supported organization access controls and Entra assignments.

This uses Entra's authorization-code flow with PKCE and Claude's hosted callback
`https://claude.ai/api/mcp/auth_callback`. The service is a resource server, not a
homemade OAuth provider. Entra handles credential entry and refresh tokens.

## Employee steps

In the company Claude organization, open **Customize > Connectors**, find the
custom connector, and select **Connect**. Sign in with the employee's company
Microsoft account. Verify the consent prompt names the intended applications.
Do not use a Global Administrator account to demonstrate ordinary employee access.
Enable the connector in the conversation/tool controls where required by your UI.

Try these prompts against harmless approved test sites, substituting the real
approved pilot job identifier:

- `Use Resolut Approved Job Sites to list the jobs I can access through this connector.`
- `Search approved job TEST1001 for filenames containing HVAC. Report any coverage limits.`
- `Read the matching test document and summarize it. Include the source link and extraction warnings.`

Verify the tool calls actually used this custom connector. A fluent answer from
Claude without a connector invocation is not proof of retrieval. Compare the
returned source and version to SharePoint. Never test using actual NDA content.

## Negative tests

Use synthetic restricted canaries at a site the same employee can open in a
browser but the connector excludes. Search by exact filename, job ID, and text;
then try an excluded opaque document ID built by the authorized tester. No
restricted title, snippet, URL, or content may return. Repeat for an approved site
with a file this employee cannot open, and test a second employee.

Follow LIVE_ACCEPTANCE.md for Microsoft resource-grant denial separately from the
registry gate. A registry-only denial does not prove the Graph grant boundary.

## Bypass prevention is separate administration

Disable/unapprove the native Microsoft 365 connector and any alternative connector
that would expose the same prohibited sites in the pilot organization. Review the
associated Entra enterprise applications, existing grants/consents, user-consent
policy, assignments, and personal-account connection risks with your administrator.
Use only controls actually available and tested for your licenses and Claude plan.
This package does not change those settings or claim their presence in your tenant.

Manual uploads, downloads, clipboard use, personal AI accounts, Teams/email copies,
and files copied into approved sites are separate channels requiring policy and,
where licensed and applicable, endpoint/browser/data-loss prevention controls.
Do not claim a SharePoint sensitivity label or this connector blocks all channels.

## Connection problems

- **AADSTS9010010:** public MCP resource URL does not match an acceptable registered
  API URI. Check the verified domain and exact `/mcp` path, not just DNS reachability.
- **Wrong client / invalid client:** distinguish the two app registrations/secrets.
- **Wrong issuer/audience:** confirm the single tenant and v2 API access tokens.
- **Missing scopes/consent:** approve the front-end API scope and middle-tier Graph
  delegated Sites.Selected; do not add broad scopes.
- **Repeated sign-in required:** check Conditional Access and OBO eligibility. An
  unhandled claims challenge is a live blocker, not authorization to weaken policy.
- **Unreachable:** remember the connection originates from Anthropic's cloud, not
  the user's laptop or VPN connection.

Do not include tokens or secrets in support screenshots or messages.
