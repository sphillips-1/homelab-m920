# Post-reboot diagnostics without SSH

Run **M920 Diagnostics** from GitHub Actions using **Run workflow**. It uses
the existing runner with `self-hosted`, `linux`, `x64`, and `m920` labels and
the `infrastructure` environment. The workflow must first be present on the
default branch for GitHub to expose its manual dispatch button.

The workflow shares Deploy's `production-deployment` concurrency group. It
does not check out or update `/opt/homelab`, deploy containers, restart services,
change networking, or repair storage. It publishes a selected diagnostic snapshot
in the run summary and logs, without raw journals, container environments,
credentials, or application response bodies.

Checks include boot identity and uptime, interface addresses and routes, SSH
service/socket state and local TCP connections, failed systemd units, expected
media mountpoints and capacity, the deployed torrent-storage guard, container
states, local HTTP responses, and counts of known current-boot error markers.
Private network addresses and filesystem UUIDs are visible to people who can
read the run. There are no uploaded artifacts or persistent diagnostic files.

Unavailable checks indicate insufficient permissions, missing commands, or
missing resources; they are not evidence of successful recovery. Journal counts
only cover entries visible to the runner, limited to the latest 500 errors.
Docker access uses the runner account or existing noninteractive Docker sudo;
the workflow grants no new privileges. The summary is a diagnostic snapshot,
not an automatic all-healthy verdict or a filesystem integrity check.

If the job stays queued, check whether the M920 runner is online in repository
Settings → Actions → Runners and whether environment approval or a deployment
is holding the job. This path cannot collect data while the runner is offline.
