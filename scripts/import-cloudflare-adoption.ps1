[CmdletBinding()]
param(
    [Parameter()]
    [string]$TerraformDirectory = (Join-Path $PSScriptRoot '..\terraform')
)

$ErrorActionPreference = 'Stop'
$inventoryPath = Join-Path $TerraformDirectory 'cloudflare-inventory.json'
$variablesPath = Join-Path $TerraformDirectory 'terraform.tfvars'
$adoptionDirectory = Join-Path $TerraformDirectory 'cloudflare-adoption'
$backendPath = Join-Path $TerraformDirectory 'backend.hcl'

if (-not (Test-Path -LiteralPath $inventoryPath)) {
    throw "Cloudflare inventory not found: $inventoryPath"
}
if (-not (Test-Path -LiteralPath $variablesPath)) {
    throw "Terraform variables not found: $variablesPath"
}
if (-not (Test-Path -LiteralPath $backendPath)) {
    throw "Terraform backend configuration not found: $backendPath"
}

$terraformCommand = Get-Command terraform -ErrorAction SilentlyContinue
if ($terraformCommand) {
    $terraform = $terraformCommand.Source
}
else {
    $temporaryTerraform = Join-Path $env:TEMP 'homelab-terraform-1.13.0\terraform.exe'
    if (-not (Test-Path -LiteralPath $temporaryTerraform)) {
        throw 'Terraform was not found in PATH or the temporary validation directory.'
    }
    $terraform = $temporaryTerraform
}

$inventory = Get-Content -Raw -LiteralPath $inventoryPath | ConvertFrom-Json
$tunnels = @($inventory.tunnels)
$dnsRecords = @($inventory.dns_records)

if ($tunnels.Count -ne 1) {
    throw "Expected exactly one discovered tunnel; found $($tunnels.Count)."
}
if ($dnsRecords.Count -ne 3) {
    throw "Expected exactly three discovered application DNS records; found $($dnsRecords.Count)."
}

$secureToken = Read-Host 'Cloudflare read-only inventory token' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
$previousToken = $env:CLOUDFLARE_API_TOKEN

try {
    $env:CLOUDFLARE_API_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)

    $verification = Invoke-RestMethod -Method Get `
        -Uri 'https://api.cloudflare.com/client/v4/user/tokens/verify' `
        -Headers @{ Authorization = "Bearer $env:CLOUDFLARE_API_TOKEN" }
    if (-not $verification.success -or $verification.result.status -ne 'active') {
        throw 'Cloudflare rejected the inventory token. Create or copy the token again.'
    }
    Write-Host 'Cloudflare token verified as active.'

    Push-Location $adoptionDirectory
    try {
        & $terraform init -reconfigure -backend-config $backendPath
        if ($LASTEXITCODE -ne 0) {
            throw 'Terraform backend initialization failed.'
        }

        $imports = @(
            @{
                Address = 'cloudflare_zero_trust_tunnel_cloudflared.homelab'
                Id      = "$($inventory.account_id)/$($tunnels[0].id)"
            }
        )

        foreach ($record in $dnsRecords) {
            $imports += @{
                # Backslashes preserve the literal quotes through Windows native
                # argument parsing so Terraform receives a valid for_each address.
                Address = "cloudflare_dns_record.public_hostnames[\`"$($record.name)\`"]"
                Id      = "$($inventory.zone.id)/$($record.id)"
            }
        }

        $stateAddresses = @(& $terraform state list)
        if ($LASTEXITCODE -ne 0) {
            throw 'Unable to read the current Terraform state.'
        }

        foreach ($item in $imports) {
            $stateAddress = $item.Address.Replace('\"', '"')
            if ($stateAddress -in $stateAddresses) {
                Write-Host "Already imported: $($item.Address)"
                continue
            }
            Write-Host "Importing $($item.Address)"
            & $terraform import -var-file $variablesPath $item.Address $item.Id
            if ($LASTEXITCODE -ne 0) {
                throw "Terraform import failed for $($item.Address)."
            }
        }

        Write-Host 'Cloudflare tunnel and DNS adoption imports completed.'
    }
    finally {
        Pop-Location
    }
}
finally {
    $env:CLOUDFLARE_API_TOKEN = $previousToken
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
}
