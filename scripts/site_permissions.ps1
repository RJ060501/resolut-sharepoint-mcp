<#
Administrator-only provisioning. Never run as the MCP reader identity.
Requires Microsoft.Graph.Authentication and a separately authorized admin app.
This script intentionally requests an elevated delegated provisioning scope;
the runtime API registration must NEVER receive that scope.
#>
[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='High')]
param(
    [Parameter(Mandatory=$true)][ValidateSet('Resolve','List','GrantRead','Revoke')][string]$Action,
    [Parameter(Mandatory=$true)][Guid]$TenantId,
    [Parameter(Mandatory=$true)][Guid]$AdminClientId,
    [string]$SiteUrl,
    [string]$SiteId,
    [Guid]$ReaderAppId,
    [string]$PermissionId
)
$ErrorActionPreference = 'Stop'
Import-Module Microsoft.Graph.Authentication -ErrorAction Stop

# Delegated admin session isolated to this PowerShell process. AdminClientId is
# a separate public-client provisioning registration; never the runtime API ID.
Connect-MgGraph -TenantId $TenantId.ToString() -ClientId $AdminClientId.ToString() `
    -Scopes 'Sites.FullControl.All' -ContextScope Process -NoWelcome
try {
    $Base = 'https://graph.microsoft.com/v1.0'
    if ($Action -eq 'Resolve') {
        if (-not $SiteUrl) { throw 'Resolve requires -SiteUrl.' }
        $Site = [Uri]$SiteUrl
        if ($Site.Scheme -ne 'https' -or -not $Site.Host.EndsWith('.sharepoint.com') -or
            $Site.UserInfo -or $Site.Query -or $Site.Fragment -or -not $Site.IsDefaultPort) {
            throw 'Use the exact HTTPS SharePoint job-site URL, without query or fragment.'
        }
        $Path = $Site.AbsolutePath.TrimEnd('/')
        if (-not $Path) { throw 'Resolve a specific job site, not the tenant root.' }
        $Uri = $Base + '/sites/' + $Site.Host + ':' + $Path + '?$select=id,displayName,webUrl,siteCollection'
        Invoke-MgGraphRequest -Method GET -Uri $Uri -OutputType PSObject
        return
    }
    if (-not $SiteId -or $SiteId -notmatch '^[A-Za-z0-9.-]+,[A-Fa-f0-9-]{36},[A-Fa-f0-9-]{36}$') {
        throw 'Supply the Graph composite -SiteId returned by Resolve.'
    }
    $Endpoint = $Base + '/sites/' + [Uri]::EscapeDataString($SiteId) + '/permissions'
    $All = @()
    $Next = $Endpoint
    while ($Next) {
        # Only continue the same permissions collection, never an arbitrary host.
        $NextUri = [Uri]$Next
        if ($NextUri.Scheme -ne 'https' -or $NextUri.Host -ne 'graph.microsoft.com' -or
            $NextUri.AbsolutePath -ne ([Uri]$Endpoint).AbsolutePath) { throw 'Unexpected pagination URL.' }
        $Page = Invoke-MgGraphRequest -Method GET -Uri $Next -OutputType PSObject
        $All += @($Page.value)
        $Next = $Page.'@odata.nextLink'
    }
    if ($Action -eq 'List') { $All; return }
    if ($ReaderAppId -eq [Guid]::Empty) { throw 'GrantRead and Revoke require -ReaderAppId (API client ID).' }
    $Matching = @($All | Where-Object {
        $Entry = $_
        $Ids = @($Entry.grantedToIdentitiesV2) + @($Entry.grantedToIdentities)
        @($Ids | Where-Object { $_.application.id -eq $ReaderAppId.ToString() }).Count -gt 0
    })
    if ($Action -eq 'GrantRead') {
        if ($Matching.Count -gt 0) {
            foreach ($Grant in $Matching) {
                if (@($Grant.roles).Count -ne 1 -or $Grant.roles[0] -ne 'read') {
                    throw 'A broader or unexpected existing grant must be reviewed and revoked, not ignored.'
                }
            }
            Write-Output 'A read grant already exists for this application.'
            $Matching
        } elseif ($PSCmdlet.ShouldProcess($SiteId, "Grant READ to runtime API $ReaderAppId")) {
            $Body = @{
                roles = @('read')
                grantedToIdentities = @(@{ application = @{
                    id = $ReaderAppId.ToString(); displayName = 'Resolut Approved Job Sites API'
                }})
            } | ConvertTo-Json -Depth 8
            Invoke-MgGraphRequest -Method POST -Uri $Endpoint -Body $Body -ContentType 'application/json'
        }
    } elseif ($Action -eq 'Revoke') {
        $Target = @($Matching | Where-Object { $_.id -eq $PermissionId })
        if (-not $PermissionId -or $Target.Count -ne 1) {
            throw 'Supply an exact -PermissionId that belongs to -ReaderAppId on this site.'
        }
        if ($PSCmdlet.ShouldProcess($SiteId, "Revoke grant $PermissionId for runtime API $ReaderAppId")) {
            Invoke-MgGraphRequest -Method DELETE -Uri ($Endpoint + '/' + [Uri]::EscapeDataString($PermissionId))
            Write-Output 'Microsoft grant revoked. Confirm the local registry is blocked and run live denial tests.'
        }
    }
} finally {
    Disconnect-MgGraph | Out-Null
}
