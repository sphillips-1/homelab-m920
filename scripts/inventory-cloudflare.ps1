[CmdletBinding()]
param(
    [Parameter()]
    [ValidatePattern('^[A-Za-z0-9.-]+$')]
    [string]$ZoneName = 'shelfgoblin.dev',

    [Parameter()]
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\terraform\cloudflare-inventory.json')
)

$ErrorActionPreference = 'Stop'
$apiBase = 'https://api.cloudflare.com/client/v4'
$tokenPointer = [IntPtr]::Zero

try {
    if ($env:CLOUDFLARE_API_TOKEN) {
        $token = $env:CLOUDFLARE_API_TOKEN
    }
    else {
        $secureToken = Read-Host 'Cloudflare read-only inventory token' -AsSecureString
        $tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
        $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    }
    $headers = @{ Authorization = "Bearer $token" }

    function Invoke-CloudflareGet {
        param([Parameter(Mandatory)][string]$Path)

        $response = Invoke-RestMethod -Method Get -Uri "$apiBase$Path" -Headers $headers
        if (-not $response.success) {
            $messages = $response.errors | ForEach-Object { $_.message }
            throw "Cloudflare API request failed: $($messages -join '; ')"
        }
        return $response.result
    }

    $escapedZoneName = [Uri]::EscapeDataString($ZoneName)
    $zones = @(Invoke-CloudflareGet "/zones?name=$escapedZoneName")
    if ($zones.Count -ne 1) {
        throw "Expected exactly one accessible zone named $ZoneName; found $($zones.Count)."
    }

    $zone = $zones[0]
    $zoneId = $zone.id
    $accountId = $zone.account.id
    $targetNames = @("audiobooks.$ZoneName", "books.$ZoneName", "status.$ZoneName", "auth.$ZoneName")

    $dnsRecords = @(Invoke-CloudflareGet "/zones/$zoneId/dns_records?per_page=100") |
        Where-Object { $_.name -in $targetNames } |
        ForEach-Object {
            [ordered]@{
                id      = $_.id
                name    = $_.name
                type    = $_.type
                content = $_.content
                proxied = $_.proxied
                ttl     = $_.ttl
            }
        }

    $tunnels = @(Invoke-CloudflareGet "/accounts/$accountId/cfd_tunnel?is_deleted=false") |
        ForEach-Object {
            [ordered]@{
                id         = $_.id
                name       = $_.name
                config_src = $_.config_src
                status     = $_.status
                created_at = $_.created_at
            }
        }

    $applications = @(Invoke-CloudflareGet "/accounts/$accountId/access/apps?per_page=100") |
        Where-Object { $null -ne $_ } |
        Where-Object {
            $applicationHostname = ([string]$_.domain -split '/', 2)[0]
            $applicationHostname -in $targetNames
        } |
        ForEach-Object {
            [ordered]@{
                id                        = $_.id
                name                      = $_.name
                domain                    = $_.domain
                type                      = $_.type
                session_duration          = $_.session_duration
                allowed_idps              = @($_.allowed_idps)
                auto_redirect_to_identity = $_.auto_redirect_to_identity
                aud                       = $_.aud
                policies                  = @($_.policies | ForEach-Object {
                        [ordered]@{
                            id         = $_.id
                            name       = $_.name
                            decision   = $_.decision
                            precedence = $_.precedence
                            include    = $_.include
                            exclude    = $_.exclude
                            require    = $_.require
                        }
                    })
            }
        }

    # Deliberately omit IdP config because it can contain OAuth client material.
    $identityProviders = @(Invoke-CloudflareGet "/accounts/$accountId/access/identity_providers") |
        Where-Object { $null -ne $_ } |
        ForEach-Object {
            [ordered]@{
                id        = $_.id
                name      = $_.name
                type      = $_.type
                read_only = $_.read_only
            }
        }

    $organization = Invoke-CloudflareGet "/accounts/$accountId/access/organizations"

    $inventory = [ordered]@{
        generated_at       = (Get-Date).ToUniversalTime().ToString('o')
        account_id         = $accountId
        zone               = [ordered]@{ id = $zoneId; name = $zone.name; status = $zone.status }
        tunnels            = @($tunnels)
        dns_records        = @($dnsRecords)
        access_applications = @($applications)
        identity_providers = @($identityProviders)
        zero_trust_organization = [ordered]@{
            name                    = $organization.name
            auth_domain             = $organization.auth_domain
            deny_unmatched_requests = $organization.deny_unmatched_requests
            is_ui_read_only         = $organization.is_ui_read_only
            session_duration        = $organization.session_duration
        }
    }

    $resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
    $inventory | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $resolvedOutput -Encoding utf8
    Write-Host "Wrote redacted Cloudflare inventory to $resolvedOutput"
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
    Remove-Variable token -ErrorAction SilentlyContinue
    Remove-Variable secureToken -ErrorAction SilentlyContinue
}
