# Migration

Use the [deployment runbook](deployment-runbook.md) to prepare the M920Q and
register the Actions runner. Use [recovery](recovery.md) to inventory and restore
service data, secrets, and media. Stop source writers before the final copy and
verify destination mounts before restoring. Preserve the source until accounts,
libraries, playback, ingress, and backups pass verification on the M920Q. Apply
service configuration through the GitHub Actions pipeline. See the
[decommission plan](decommission-plan.md) for retiring legacy infrastructure.
