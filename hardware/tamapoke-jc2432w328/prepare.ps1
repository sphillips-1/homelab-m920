param(
    [Parameter(Mandatory)]
    [string] $Checkout
)

$ErrorActionPreference = 'Stop'
$revision = 'a441be28270b6d48cc922454df11618fe04d1e45'
$patch = Join-Path $PSScriptRoot 'upstream.patch'

if (-not (Test-Path -LiteralPath $Checkout)) {
    git clone --no-checkout https://github.com/socquique/TamaPoke.git $Checkout
    if ($LASTEXITCODE) { throw 'Could not clone TamaPoke.' }
    git -C $Checkout checkout --detach $revision
    if ($LASTEXITCODE) { throw 'Could not check out the pinned TamaPoke revision.' }
}

$head = git -C $Checkout rev-parse HEAD
if ($LASTEXITCODE -or $head -ne $revision) {
    throw "Use a dedicated TamaPoke checkout at $revision."
}

git -C $Checkout apply --check $patch 2>$null
if ($LASTEXITCODE -eq 0) {
    git -C $Checkout apply $patch
    if ($LASTEXITCODE) { throw 'Could not apply the board patch.' }
} else {
    git -C $Checkout apply --reverse --check $patch
    if ($LASTEXITCODE) { throw 'The checkout differs from the expected source or applied patch.' }
}

foreach ($file in 'jc_display.h', 'platformio.ini', 'cyd_ota.h') {
    $source = if ($file -eq 'cyd_ota.h') {
        Join-Path $PSScriptRoot '../cyd-ota/ota.h'
    } else {
        Join-Path $PSScriptRoot $file
    }
    $destination = Join-Path $Checkout $file
    if (Test-Path -LiteralPath $destination) {
        if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
            throw "The checkout already contains a different $file."
        }
    } else {
        Copy-Item -LiteralPath $source -Destination $destination
    }
}
