# Operations, changes, and incident response

## Ownership

Name an IT service owner and backup maintainer, an Entra/SharePoint administrator,
a Claude organization administrator, and project/business approvers. IT owns the
runtime, repository, identity configuration, monitoring, and security tests.
Project/contract owners decide whether an entire job may be processed by the
approved external provider. Engineering's existing search stays independent.

## Single-instance policy publication

The pilot uses one process on one VM and one root-managed local registry. Every
check rereads the file; an invalid/missing registry fails closed. The admin CLI
validates a temporary file and replaces the registry atomically on the same
filesystem. The runtime identity can read, not write, the registry or application.
Use one administrator/change operation at a time; concurrent admin edits are not
merged. Preserve the registry's root ownership, group, and restrictive permissions.

A new file within an approved site needs no per-document approval. Search sees it
on a fresh enumeration; Graph propagation still applies. Updating a file does not
revoke site approval. Reads compare ETags before/after download/extraction and
reject an inconsistent mid-read version.

Renaming a site URL requires an administrator to update the protected registry
while retaining the stable ID after review; until then the URL consistency check
denies it. A move/copy outside an approved site cannot be accessed through the old
reference. Cross-site shortcuts are not followed. A copy placed in an approved
site inherits that site's eligibility; human data-handling rules must prevent
restricted data from being copied there.

## Block a site immediately in the connector

Run as the deployment administrator:

```bash
sudo /opt/resolut-mcp/current/.venv/bin/python -m resolut_mcp.admin \
  --registry /etc/resolut-mcp/sites.json --host YOURTENANT.sharepoint.com \
  block --job-id JOB123
```

No service restart is needed for a valid atomic block on this single instance.
The next authorization check fails; reads recheck after retrieval and parsing,
and search rechecks results before return. There is no persistent index/body
cache. Request-local metadata is discarded when the request ends.

This cannot recall bytes already sent or eliminate every timing race between a
final check and network delivery. For an urgent incident, **stop the service first**
to interrupt requests, disable the connector, and then apply/review revocations.
If adding replicas later, a shared authoritative policy mechanism and tested
coordinated revocation are mandatory. Copying this local file onto unsynchronized
servers is not an acceptable multi-instance design.

## Revoke the independent Microsoft grant

From the separate authorized admin workstation:

```powershell
.\scripts\site_permissions.ps1 -Action List -TenantId $Tenant `
  -AdminClientId $AdminApp -SiteId $SiteId
.\scripts\site_permissions.ps1 -Action Revoke -TenantId $Tenant `
  -AdminClientId $AdminApp -SiteId $SiteId -ReaderAppId $ReaderApp `
  -PermissionId 'EXACT-GRANT-ID' -WhatIf
# Review, then repeat without -WhatIf and confirm.
```

The script verifies the grant belongs to that app on that site. Confirm denial
again after Microsoft propagation. Keep a restricted change record. Remove an
entry only after blocking/revoking; absence remains denied. Reapproval requires
review and both the registry approval and selected Microsoft read grant.

## Monitoring and secrets

Audit entries contain a request reference, tool, pseudonymous actor hash, decision,
and safe error code. They intentionally omit queries, filenames, site names,
document bodies, access tokens, and credentials. Correlate with authorized Entra
sign-in and Microsoft audit records where available. Do not promise a document-
level audit log from this minimized log format. Store administrative grant changes
and approvals in a separate restricted change record.

Monitor process restarts, memory pressure, repeated safe failure codes, invalid
registry/readiness, sign-in failures, request durations at the proxy without
sensitive payload logging, credential expiry, and TLS renewal. `/readyz` is not a
Microsoft connectivity test. Run periodic synthetic acceptance checks separately.

Rotate the API credential and the Claude OAuth client credential independently.
Update the correct location, reconnect affected users if needed, and invalidate
old secrets after verification. Certificate private keys remain server-side.
Do not enable third-party telemetry that captures request headers or document text.

## Incident and rollback

Stop `resolut-mcp`; disable the Claude connector; block affected sites; revoke
selected grants and compromised credentials; preserve restricted audit/change
records; follow company security and client-notification procedures. Review
conversations/vendor retention under authorized administration. Changing Graph
permissions does not delete earlier answers, chat history, exports, or uploads.

Restore reviewed code only after investigation and tests. Keep current denials
when rolling back software. Back up the registry and deployment configuration in
an approved encrypted administrative location, not the Git repository. Never
restore an older permissive registry simply because it shipped with an earlier
code release.
