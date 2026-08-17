[CmdletBinding()]
param(
    [Parameter()]
    [string]$TerraformDirectory = (Join-Path $PSScriptRoot '..\terraform')
)

$ErrorActionPreference = 'Stop'
$adoptionDirectory = Join-Path $TerraformDirectory 'cloudflare-adoption'
$variablesPath = Join-Path $TerraformDirectory 'terraform.tfvars'

$terraformCommand = Get-Command terraform -ErrorAction SilentlyContinue
if ($terraformCommand) {
    $terraform = $terraformCommand.Source
}
else {
    $terraform = Join-Path $env:TEMP 'homelab-terraform-1.13.0\terraform.exe'
    if (-not (Test-Path -LiteralPath $terraform)) {
        throw 'Terraform was not found in PATH or the temporary validation directory.'
    }
}

$secureToken = Read-Host 'Cloudflare read-only inventory token' -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
$previousToken = $env:CLOUDFLARE_API_TOKEN

try {
    $env:CLOUDFLARE_API_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    Push-Location $adoptionDirectory
    try {
        & $terraform plan -detailed-exitcode -var-file $variablesPath
        $planExitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    switch ($planExitCode) {
        0 { Write-Host 'SAFE RESULT: Terraform plan reports no changes.' }
        2 { Write-Warning 'REVIEW REQUIRED: Terraform plan reports changes. Do not apply.' }
        default { throw "Terraform plan failed with exit code $planExitCode." }
    }
}
finally {
    $env:CLOUDFLARE_API_TOKEN = $previousToken
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
    }
}
