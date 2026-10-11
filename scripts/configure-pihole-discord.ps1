# Enter the Discord webhook privately and store it on the M920Q outside Git.
[CmdletBinding()]
param([string]$SshTarget = 'sean@192.168.4.27')
$ErrorActionPreference = 'Stop'

# Create a private directory as the SSH user; sudo may prompt for the server password.
& ssh -t -o StrictHostKeyChecking=yes -o ConnectTimeout=10 $SshTarget 'sudo install -d -m 0700 -o $(id -un) -g $(id -gn) /srv/homelab/appdata/monitoring/pihole'
if ($LASTEXITCODE -ne 0) { throw 'SSH or private directory setup failed. No webhook was collected or stored.' }

$remotePython = @"
import os, sys, tempfile
from pathlib import Path
from urllib.parse import urlparse
url = sys.stdin.read().strip()
u = urlparse(url)
if u.scheme != 'https' or u.hostname not in ('discord.com', 'discordapp.com') or not u.path.startswith('/api/webhooks/') or len(u.path.split('/')) != 5 or not all(u.path.split('/')[3:]):
    sys.exit('Invalid Discord webhook URL; nothing saved.')
directory = Path('/srv/homelab/appdata/monitoring/pihole')
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
fd, temporary = tempfile.mkstemp(prefix='.discord-webhook-', dir=directory)
try:
    with os.fdopen(fd, 'w') as output:
        output.write(url + '\n')
        output.flush()
        os.fsync(output.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, directory / 'discord-webhook.url')
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
print('Webhook saved privately on M920Q (mode 0600). No message sent.')
"@
# Single shell quotes survive Windows PowerShell's native argument handling.
# A bytes literal constructed from integers avoids nested quotes entirely.
$pythonBytes = [Text.Encoding]::UTF8.GetBytes($remotePython) -join ','
$remoteCommand = "python3 -c 'exec(bytes([$pythonBytes]))'"
# Exercise the same transport before requesting the webhook.
$probeBytes = [Text.Encoding]::UTF8.GetBytes("import sys; assert sys.stdin.read().strip() == 'transport-probe'; print('SSH input check passed.')") -join ','
$probeCommand = "python3 -c 'exec(bytes([$probeBytes]))'"
$probeOutput = 'transport-probe' | & ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 $SshTarget $probeCommand
if ($LASTEXITCODE -ne 0) { throw 'SSH input check failed. No webhook was collected.' }
Write-Host $probeOutput
$secret = Read-Host 'Paste the webhook for Phillips Collab Area / #pihole (input hidden)' -AsSecureString
$pointer = [IntPtr]::Zero
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim()
    if ($plain -notmatch '^https://(discord\.com|discordapp\.com)/api/webhooks/[0-9]+/[^\s/?#]+$') {
        throw 'Invalid Discord webhook URL. Nothing saved.'
    }
    $plain | & ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 $SshTarget $remoteCommand
    if ($LASTEXITCODE -ne 0) { throw 'Remote storage failed. Rerun this helper after resolving SSH/sudo access.' }
} finally {
    $plain = $null
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($secret) { $secret.Dispose() }
}
