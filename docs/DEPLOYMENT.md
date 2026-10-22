# Deployment: one Ubuntu VM, systemd, Caddy, no Docker

This is an explicit default, **not an assertion that Resolut has approved a VM,
cloud subscription, public endpoint, or firewall change**. Use an approved Ubuntu
24.04 host with Python 3.12, a company-controlled DNS record under an Entra-verified
domain, and a named maintainer. One instance/process is supported for this pilot.
An Azure VM or an existing approved Linux server can host it; no VM is provisioned
by this package. Do not expose a personal laptop or home server for company data.

## 1. Validate the build on your workstation

Follow README.md and UBUNTU_WSL2_SETUP.md in your Ubuntu WSL environment.
The dedicated deployment host is separate from WSL on your workstation.
Run `python scripts/verify_release.py` in the installed Linux venv.
All tests, including official-SDK HTTP tests, must pass. Inspect TEST_REPORT.md to
understand what was and was not run in the delivery environment. The package is
source code, not a prevalidated container or vendored dependency bundle.

Resolve a hash-locked dependency set on your approved network build host as
explained in DEPENDENCIES.md. Audit it and commit the reviewed lock. Do not use a
failed or untested installation as the live server.

## 2. Prepare the host and read-only runtime account

Use the administrator account, not the eventual service identity. Back up or
review existing configuration before overwriting files; these commands assume a
new dedicated host/service.

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv ca-certificates git
sudo useradd --system --user-group --home-dir /nonexistent \
  --shell /usr/sbin/nologin resolut-mcp
sudo install -d -o root -g root -m 0755 /opt/resolut-mcp/releases
sudo install -d -o root -g resolut-mcp -m 0750 /etc/resolut-mcp
```

If the account already exists, inspect it rather than recreating it. Transfer the
reviewed source using company-approved Git/artifact tooling. For example, after
extracting this release into your administrator's staging directory:

```bash
sudo cp -a ./resolut-sharepoint-mcp /opt/resolut-mcp/releases/0.1.0
sudo chown -R root:root /opt/resolut-mcp/releases/0.1.0
sudo chmod -R go-w /opt/resolut-mcp/releases/0.1.0
sudo ln -s /opt/resolut-mcp/releases/0.1.0 /opt/resolut-mcp/current
cd /opt/resolut-mcp/current
sudo python3.12 -m venv .venv
```

Install the reviewed lock generated on an internet-enabled build host:

```bash
sudo .venv/bin/python -m pip install --require-hashes -r requirements.lock
sudo .venv/bin/python -m pip install --no-deps .
```

The delivery archive contains pinned direct requirements, not a fabricated verified
transitive lock. For an initial **synthetic build-validation environment only**,
install `-r requirements.txt -r requirements-dev.txt`, install the package, and run
the release tests; then create/review a lock before production. Prefer an approved
internal package index/wheelhouse when required. Verify the final deployment with
`pip check`. Tests and admin scripts do not run as the service account.

## 3. Install protected configuration

```bash
sudo install -o root -g resolut-mcp -m 0640 deploy/live.env.example /etc/resolut-mcp/live.env
printf '{"schema_version":1,"jobs":[]}\n' | sudo tee /etc/resolut-mcp/sites.json > /dev/null
sudo chown root:resolut-mcp /etc/resolut-mcp/sites.json
sudo chmod 0640 /etc/resolut-mcp/sites.json
sudoedit /etc/resolut-mcp/live.env
```

Fill in actual values locally. Main variables:

| Variable | Required value |
|---|---|
| `MODE` | `live` |
| `PUBLIC_MCP_URL` | Exact HTTPS URL including `/mcp`, also registered as API URI |
| `TENANT_ID` | Your Entra tenant GUID |
| `API_CLIENT_ID` | Runtime API registration GUID |
| `CLAUDE_CLIENT_ID` | Separate front-end OAuth client GUID |
| `API_CLIENT_SECRET` | Runtime API secret only, or use certificate fields instead |
| `SHAREPOINT_HOST` | Exact `YOURTENANT.sharepoint.com` |
| `DOWNLOAD_HOSTS` | Exact approved SharePoint download hostnames; no wildcards |
| `REGISTRY_PATH` | `/etc/resolut-mcp/sites.json` |

Entra/Graph hosts and TLS verification are fixed in code. SharePoint content
redirects must match the configured exact hosts and never receive the Graph
Authorization header. Start with your tenant SharePoint host; inspect a legitimate
failed download locally before adding another **specific** tenant host. Do not
allow arbitrary Microsoft-looking domains, user URLs, or wildcard domains.

Use an approved secret manager if your environment requires one. The supplied
baseline is a root-managed, group-readable environment file, excluded from Git;
it is not equivalent to a managed vault. Set credential expirations and rotation
owners. For a certificate, the service must read the private key without being
able to modify it. Do not copy the front-end OAuth client secret onto this server.

Follow ENTRA_SETUP.md to create pending registry entries, grant selected read
access separately, and approve only entire sites that have authorization.

## 4. Install and check the application service

```bash
sudo install -m 0644 deploy/resolut-mcp.service /etc/systemd/system/resolut-mcp.service
sudo systemctl daemon-reload
sudo -u resolut-mcp .venv/bin/python -m resolut_mcp \
  --env-file /etc/resolut-mcp/live.env validate-config
sudo systemctl enable --now resolut-mcp
sudo systemctl status resolut-mcp --no-pager
curl --fail http://127.0.0.1:8000/healthz
curl --fail http://127.0.0.1:8000/readyz
```

Health must show mode `live`. Readiness means only that the process and registry
are valid; it does not prove Graph authorization, OAuth, or Claude integration.
The service binds **127.0.0.1:8000**, not a public interface. Its files and registry
are read-only to the service account. The unit refuses `MODE=mock`.

## 5. Configure HTTPS

Follow the official Caddy install instructions linked in SOURCES.md. On Ubuntu,
review and use its stable package repository instructions, then install Caddy.
For example, the documented package setup is:

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
  sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
  sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

Use your normal software-source approval process; do not overwrite an existing
key/config without review. Set the DNS A/AAAA record to the approved host. If IPv6
is not configured end-to-end, do not publish a broken AAAA record.

```bash
sudo install -m 0644 deploy/Caddyfile.example /etc/caddy/Caddyfile
sudoedit /etc/caddy/Caddyfile
# Replace ONLY the example hostname with the approved verified-domain hostname.
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy manages TLS for that hostname. Permit necessary certificate issuance/renewal
traffic (normally inbound TCP 80/443 for automatic HTTPS) under your firewall
policy. Permit inbound 443 from Anthropic's **current published** ranges if using
source allowlisting, plus approved administrators for tests. Outbound 443 is needed
for Entra discovery/token/JWKS, Microsoft Graph, approved SharePoint hosts, and
certificate management. Do not expose 8000 or broadly expose SSH. Do not blindly
change a firewall and lock out administrators.

Keep request-body/header logging and external tracing disabled. The example does
not publish other application paths. Do not add a login form or HTTP Basic Auth
in front of MCP; it would interfere with OAuth discovery.

## 6. Verify public discovery before Claude

From an allowed external network:

```bash
curl --fail https://YOUR-MCP-HOST/healthz
curl --fail https://YOUR-MCP-HOST/.well-known/oauth-protected-resource/mcp
curl -i -X POST https://YOUR-MCP-HOST/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Expected: live health, protected-resource metadata with exact resource URL and
correct Entra tenant issuer, and **401** plus `WWW-Authenticate` for the anonymous
MCP request. A 200 tool response without a valid token is a stop-ship security
failure. A healthy localhost result does not establish Anthropic reachability.

Then follow CLAUDE_SETUP.md. Do not put production data through the connector until
the full live acceptance checklist is completed.

## Troubleshooting and rollback

Inspect `sudo journalctl -u resolut-mcp --since '15 minutes ago' --no-pager` locally.
Logs show pseudonymous actor, tool, safe error code, and request reference, not
query/document bodies or tokens. Do not enable indiscriminate debug logging.

`authentication_required`: verify registrations, v2 token audience/issuer/client,
consent, pilot assignment, credential validity, and Conditional Access locally.
`authorization_configuration`: review actual Graph scopes; remove broad defaults.
`policy_unavailable`: fix registry syntax/permissions; there is no cached approval
fallback. `unavailable`: review approved-site grant and user's effective access
without revealing denied document names to the requester.

Emergency stop: `sudo systemctl stop resolut-mcp`, then disable the connector in
Claude and follow incident response. For code rollback, stop the service, repoint
`/opt/resolut-mcp/current` to a reviewed previous release, and restart. Keep the
current blocked registry; do **not** roll back policy to re-enable excluded sites.
Microsoft grant changes must be separately reviewed, not restored automatically.
