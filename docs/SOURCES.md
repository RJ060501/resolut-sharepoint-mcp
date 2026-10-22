# Official technical references

Reviewed for this build on October 21-22, 2026 (local/UTC boundary). Recheck changing
UI labels, package versions, and tenant/plan features at deployment. These sources
support the design; they do not prove it has been tested in your environment.

- Microsoft Selected permission model: delegated/application availability,
  site-collection scope, explicit grants, and interaction with user permissions:
  https://learn.microsoft.com/en-us/graph/permissions-selected-overview
- Microsoft delegated on-behalf-of flow and token separation:
  https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow
- Microsoft site grant creation and privileged provisioning requirements:
  https://learn.microsoft.com/en-us/graph/api/site-post-permissions?view=graph-rest-1.0
- Microsoft drive children enumeration and pagination:
  https://learn.microsoft.com/en-us/graph/api/driveitem-list-children?view=graph-rest-1.0
- Microsoft content retrieval and preauthenticated redirect behavior:
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0
- Microsoft SharePoint identifier semantics (site collection GUID vs web GUID):
  https://learn.microsoft.com/en-us/graph/api/resources/sharepointids?view=graph-rest-1.0
- Microsoft DriveItem search limitations; this application avoids that API:
  https://learn.microsoft.com/en-us/graph/api/driveitem-search?view=graph-rest-1.0
- Anthropic connector OAuth, callback, resource metadata, Entra resource URI:
  https://claude.com/docs/connectors/building/authentication
- Anthropic custom connector setup, own OAuth client, organization roles and network:
  https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp
- Official MCP Python SDK v2.3.0 source and published package:
  https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0
  https://pypi.org/project/mcp/2.3.0/
- Official MCP resource-server authorization and ASGI guidance:
  https://py.sdk.modelcontextprotocol.io/run/authorization/
  https://py.sdk.modelcontextprotocol.io/run/asgi/
- Microsoft MSAL Python release:
  https://pypi.org/project/msal/1.39.0/
- pypdf deployment parser release:
  https://pypi.org/project/pypdf/6.21.2/
- Caddy official installation and automatic HTTPS:
  https://caddyserver.com/docs/install
  https://caddyserver.com/docs/automatic-https

Selected permissions must be checked with every actual endpoint in the live
acceptance plan; endpoint documentation tables do not always enumerate the entire
Selected model. Do not use that documentation gap to silently add broad scopes.
