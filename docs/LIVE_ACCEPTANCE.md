# Live acceptance and Tuesday go/no-go

Run these checks with harmless synthetic content in locations specifically
approved for testing. A site containing real restricted information is not made
safe merely by adding one synthetic file. Do not approve that entire site for the
test. Obtain authorized test locations and written policy/vendor approval for any
real data later.

**Do not treat the delivered local results as completion of this checklist.**
Record tester, date, client/user, site/grant/registry change references, expected
result, actual result, and pass/fail. Keep screenshots and identifiers in the
restricted change record, not the public repository or an AI conversation.

## A. Build and platform gate

- Install the reviewed dependencies on Python 3.12; `pip check` must pass.
- `python scripts/verify_release.py` must pass, including actual official-SDK
  HTTP tests. Missing SDK/MSAL or mismatched critical versions must not be skipped.
- Create/review a hash lock and scan dependencies under your approved process.
- Confirm single-tenant applications, exact API URI, public verified-domain HTTPS,
  own OAuth client capability in Claude, pilot assignments, consent, and credentials.
- Verify anonymous `/mcp` returns 401 and safe discovery metadata. Wrong bearer
  tokens must not list tools or return documents. Health alone is insufficient.
- Confirm API runtime has delegated Sites.Selected only, no application/read-all/
  write/provisioning scope, and selected read grants on approved collections only.

## B. Identity and permission gate

Use at least two ordinary test employees, never just an administrator account.
Prepare synthetic examples representing:

| Case | Employee browser access | Registry | Microsoft app grant | Expected connector behavior |
|---|---|---|---|---|
| A | Can read supported files | Approved | Read | List/search/read works |
| B | Can read site and file | Blocked | None | No name, URL, snippet, or body |
| C | Cannot read the site | Approved | Read | No result/access |
| D | Can read site, not one uniquely restricted file | Approved | Read | Restricted file absent/denied |
| E | Can read site | Pending/unknown | None | Denied |
| F, grant test | Can read synthetic site | Approved | None | Microsoft read must fail |

Case F proves the selected-resource grant independently of the registry. Use only
an approved synthetic test site for it. Then grant read and verify the exact
endpoints used by this implementation: site, site drives, root/folder children,
item metadata including sharepointIds, and file content/download. Repeat revoking
the Microsoft grant while keeping registry approval temporarily for this synthetic
test; after documented propagation, it must fail again. Never respond to an
endpoint compatibility failure by adding tenant-wide read scopes.

Cases C/D prove user authorization independently of the application's approval.
Repeat with the second employee and a previously returned document ID. The opaque
ID must not allow another user to bypass their SharePoint rights. Include unique
library and folder permissions, not just a file ACL, in your live test set.

Test Claude's actual sign-in, consent, reconnect/refresh, and expected Conditional
Access. A token test generated locally is not proof Entra and Claude interoperate.
Unresolved claims challenges, plan limitations, or missing callbacks are blockers.

## C. Content and changes gate

Read synthetic TXT, DOCX, and text PDF and compare text, URL, version, and warnings
to the source. Verify unsupported RVT/DWG, encrypted, image-only, malformed, and
oversized examples produce safe explicit errors rather than invented text.

Add a supported file to an approved site: it should appear on a fresh search
without per-file approval. Update it: the current version should be read. Move it
outside the approved site: the old reference must no longer work. Try a shortcut
or link into an excluded site: it must not be followed.

Block an approved site while calls are in progress. Later checks and subsequent
calls must deny it; no persistent index should retain its entries. Check the
emergency service stop. Do not expect to erase text already returned to a chat.

Use synthetic malicious document text requesting access to an excluded site,
changes to approvals, or uploads to an arbitrary URL. The service must provide no
operation capable of doing those actions. If Claude attempts a restricted read,
that separate tool call must fail its authorization checks. No system can promise
that marking text untrusted makes a language model immune to all prompt injection;
the independent tool permissions are the enforceable boundary.

Search a known large job and inspect coverage warnings. A capped enumeration is
not proof no matching file exists. Verify an engineer can narrow by job ID and
that performance is acceptable for the pilot's actual site sizes.

## D. Governance and operations gate

Confirm the company Claude organization, data-processing/retention terms, project
approval, and applicable AI policy authorize the pilot. Confirm bypass controls
for native/other unrestricted connectors, existing Entra grants, user consent,
personal connections, and employee uploads. Test supported controls rather than
assuming sensitivity labels or a hub block Claude automatically.

Assign a service owner and backup, credential expiry/rotation, TLS monitoring,
patching/dependency review, an incident contact, and a tested rollback/revocation
procedure. Verify actual registry/code permissions prevent the runtime user from
modifying policy. Review parser isolation and host hardening.

## Tuesday decision

**GO, limited pilot only:** all applicable A-D checks passed; whole-site approvals
and selected grants match; real employee identity works through Claude; excluded
sites and unique permissions are proven; ownership and policy authorization are
recorded. Restrict users and approved sites to the tested scope.

**NO-GO for company data:** any unverified authentication/SDK integration, broad
permission workaround, unexpected data exposure, incomplete approval, unavailable
admin control, or unresolved dependency/security issue. A local synthetic demo can
still be shown, clearly labeled as not a deployed enterprise integration.

Deadline pressure is a reason to keep the pilot small, not to disable its access
checks. Full-company rollout and high-availability scaling are separate decisions.
