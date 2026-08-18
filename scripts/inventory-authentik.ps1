[CmdletBinding()]
param(
    [Parameter()]
    [string]$AuthentikUrl = 'https://auth.shelfgoblin.dev',

    [Parameter()]
    [string]$OutputPath = (Join-Path $PSScriptRoot '..\terraform\authentik\inventory.json')
)

$ErrorActionPreference = 'Stop'
$secureToken = Read-Host 'Authentik API token' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)

try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    $headers = @{ Authorization = "Bearer $token" }
    $base = $AuthentikUrl.TrimEnd('/')

    function Get-AuthentikCollection {
        param([Parameter(Mandatory)][string]$Path)

        $items = @()
        $uri = "$base/api/v3/$Path"
        while ($uri) {
            $response = Invoke-RestMethod -Method Get -Uri $uri -Headers $headers
            $items += @($response.results)
            if ($response.pagination.next) {
                $uri = if ($response.pagination.next -match '^https?://') {
                    $response.pagination.next
                } else {
                    "$base$($response.pagination.next)"
                }
            } else {
                $uri = $null
            }
        }
        return $items
    }

    # Configuration only: deliberately exclude users, tokens, events, sessions,
    # invitations, credentials, and OAuth secret-bearing response fields.
    $collections = [ordered]@{
        applications        = 'core/applications/?page_size=100'
        groups              = 'core/groups/?page_size=100'
        flows               = 'flows/instances/?page_size=100'
        flow_bindings       = 'flows/bindings/?page_size=100'
        oauth2_providers    = 'providers/oauth2/?page_size=100'
        proxy_providers     = 'providers/proxy/?page_size=100'
        oauth_sources       = 'sources/oauth/?page_size=100'
        outposts            = 'outposts/instances/?page_size=100'
        blueprint_instances = 'managed/blueprints/?page_size=100'
    }

    $inventory = [ordered]@{ generated_at = (Get-Date).ToUniversalTime().ToString('o') }
    foreach ($entry in $collections.GetEnumerator()) {
        $inventory[$entry.Key] = @(Get-AuthentikCollection $entry.Value) | ForEach-Object {
            # Keep only adoption identifiers. Full API objects can contain
            # personal attributes or secret-shaped provider fields.
            [ordered]@{
                pk      = $_.pk
                name    = $_.name
                slug    = $_.slug
                type    = $_.type
                managed = $_.managed
                path    = $_.path
                enabled = $_.enabled
            }
        }
    }

    $resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
    $inventory | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $resolvedOutput -Encoding utf8
    Write-Host "Wrote private Authentik configuration inventory to $resolvedOutput"
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
    Remove-Variable token -ErrorAction SilentlyContinue
}
