# Security design and limitations

## Enforced by application code

- Explicit site approval plus delegated Microsoft access; no broad runtime scope.
- Single-tenant signed RS256 access tokens, fixed tenant JWKS, expected API audience,
  allowed front-end client, user object ID, scope, expiry, and token version.
- Separate API and Graph tokens, MSAL OBO, no app-only fallback or user-email trust.
- Current registry checks; stable site/collection/web/drive/item and URL validation.
- No arbitrary fetch, tenant-wide discovery, writes, grant-management tools, or
  cross-site remote-item traversal. Pagination cannot change collection or host.
- Safe errors and minimized logs; no raw upstream error descriptions to the model.
- Strict file/output limits, bounded retries/timeouts, disposable extraction worker,
  no persistent document-body cache or external extraction service.
- Prompt text inside files is data. It cannot directly change grants or the registry.

## Trust and remaining risk

**This is not an independently audited product or verified live deployment.**
Tests reduce implementation risk but do not prove an enterprise policy compliant.
The selected endpoint permissions, Microsoft grant behavior, authentication flow,
Claude compatibility, and operational controls must pass live acceptance.

The protected local registry and administrators are trusted. Compromised host/root
administrators or runtime credentials can undermine controls. Restrict local and
repository access; review changes. Site approvals cover the whole site: they do
not detect NDA phrases or recognize copies of restricted content automatically.

A parser subprocess provides time, memory (on Linux), and output constraints and
receives a scrubbed environment. It is **not a complete OS security sandbox**:
it runs as the service user and shares the host filesystem/network permissions.
Dependency vulnerabilities and malicious documents require security review,
patching, and potentially stronger separate parser isolation before a broader
rollout. Mock tests are not a penetration test. Windows does not apply Linux
resource limits; the supported deployment baseline is Linux with the supplied unit.

TLS, firewall, cloud-host hardening, operating-system patching, identity policy,
third-party data-processing approval, retained conversations, manual copy/paste,
personal accounts, other connectors, and external document copies are outside
this service's sole control. No automatic DLP or legal approval is claimed.

Fresh access checks narrow, but do not eliminate, time-of-check/time-of-use races.
Microsoft permissions/revocations can take time to propagate. ETags improve version
consistency, not atomic authorization across different services. Already-returned
data cannot be retracted. Stop the connector during urgent revocation incidents.

## Known supported-scope limits

Commercial Microsoft 365 cloud; one tenant; independent job site collections;
one service instance; standard document libraries; TXT/DOCX/text PDF; simple
filename/path search; four concurrent tool requests. No sovereign-cloud endpoint
configuration, CAD/Revit interpretation, OCR, metadata classification AI, durable
search index, or full-content semantic retrieval. Unsupported cases fail or report
coverage/extraction limitations; do not widen permissions to make them work.

## Reviewer checklist

Review API scopes/grants and scope response enforcement; validate key/audience/
issuer/client logic; test OAuth through Claude; verify root-managed configuration;
inspect safe error/log behavior; test excluded sites and unique file permissions;
check preauthenticated-download handling; scan dependencies; review parser
isolation; test rollback/revocation; and approve external processing in writing.
