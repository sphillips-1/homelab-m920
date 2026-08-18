[CmdletBinding()]
param(
    [Parameter()]
    [string]$TerraformDirectory = (Join-Path $PSScriptRoot '..\terraform'),

    [Parameter()]
    [string]$BlueprintName = 'homelab-terraform',

    [Parameter()]
    [string]$AuthentikUrl = 'https://auth.shelfgoblin.dev'
)

$ErrorActionPreference = 'Stop'
$inventoryPath = Join-Path $TerraformDirectory 'authentik\inventory.json'
$blueprintPath = Join-Path $TerraformDirectory 'authentik\homelab.yaml'
$backendPath = Join-Path $TerraformDirectory 'backend.hcl'

foreach ($requiredPath in @($inventoryPath, $blueprintPath, $backendPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required adoption file not found: $requiredPath"
    }
}

$terraform = (Get-Command terraform -ErrorAction Stop).Source
$inventory = Get-Content -Raw -LiteralPath $inventoryPath | ConvertFrom-Json
$matches = @($inventory.blueprint_instances | Where-Object { $_.name -eq $BlueprintName })
if ($matches.Count -gt 1) {
    throw "Found more than one Authentik blueprint named $BlueprintName."
}

$secureToken = Read-Host 'Authentik API token' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
$previousUrl = $env:AUTHENTIK_URL
$previousToken = $env:AUTHENTIK_TOKEN

Push-Location $TerraformDirectory
try {
    $env:AUTHENTIK_URL = $AuthentikUrl
    $env:AUTHENTIK_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    & $terraform init -reconfigure -backend-config $backendPath
    if ($LASTEXITCODE -ne 0) { throw 'Terraform backend initialization failed.' }

    $address = 'authentik_blueprint.homelab[0]'
    $state = @(& $terraform state list)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to read Terraform state.' }
    if ($address -in $state) {
        Write-Host "Already in state: $address"
    } elseif ($matches.Count -eq 1) {
        & $terraform import -var enable_authentik_blueprint=true $address $matches[0].pk
        if ($LASTEXITCODE -ne 0) { throw 'Authentik blueprint import failed.' }
    } else {
        Write-Host "No existing '$BlueprintName' instance exists; the reviewed plan may create it."
    }

    & $terraform plan -detailed-exitcode -var enable_authentik_blueprint=true
    if ($LASTEXITCODE -eq 1) { throw 'Terraform plan failed.' }
    if ($LASTEXITCODE -eq 2) { Write-Warning 'Plan has changes. Review it; do not apply blindly.' }
}
finally {
    Pop-Location
    $env:AUTHENTIK_URL = $previousUrl
    $env:AUTHENTIK_TOKEN = $previousToken
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
}
