# Container deployment

Every push to `main` runs the single **Deploy** workflow in
`.github/workflows/deploy.yml`. It validates the container configuration and
scripts, validates and applies Terraform, then deploys containers on the existing
M920Q GitHub Actions runner. Pull requests do not run a separate pipeline.

## One-time runner setup

Give the runner the labels `self-hosted`, `linux`, `x64`, and `m920`. From the
canonical checkout, install the root-owned deployment entry point for the Unix
account that runs the GitHub runner:

```bash
cd /opt/homelab
sudo bash ./scripts/install-container-deployment.sh RUNNER_USER
```

The installer gives that account passwordless sudo access only to
`/usr/local/sbin/homelab-deploy`. The command itself accepts only a full commit
SHA that is contained in the fetched `origin/main` history. After a successful
deployment it refreshes the installed entry point from the reviewed version in
the repository, so deployment-script changes become active for the next run.

Protect `main` with pull-request review. Remove required status checks for the
retired **Container PR** and **Terraform PR** workflows from branch protection
or rulesets; validation now runs after merge as part of **Deploy**.
Repository write access is production-equivalent because reviewed repository
code controls Docker workloads and the root deployment process.

## Deployment behavior

The **Deploy** workflow serializes the entire run and invokes the exact pushed
commit. Container validation must pass before Terraform runs; Terraform retains
its adoption gate, remote state, validation, saved plan, and rejection of deletes
or replacements before apply. Containers deploy only after Terraform succeeds.
All production jobs retain the `infrastructure` environment. If container
deployment fails, the already-applied Terraform changes are not rolled back.

The host deployment command:

1. locks against concurrent deployments;
2. refuses to overwrite tracked local changes;
3. verifies the commit belongs to `origin/main`;
4. backs up affected state when a stateful Compose definition changed,
   including Jellyfin configuration but not media or transcode cache;
5. validates every Compose model and pulls its declared images;
6. runs the repository's idempotent service deployment;
7. verifies containers and local HTTP readiness; and
8. records the deployed SHA under `/srv/homelab/appdata/deployment`.

Cloudflared is deployed after the applications by `deploy-services.sh`. If its
runtime configuration has not been created, deployment and verification skip
it as they do during initial bootstrap.

## Failures and rollback

If deployment or verification fails, the command checks out the previous SHA
and reapplies its Compose definitions. It deliberately does not restore
persistent data automatically: an automatic restore could discard writes made
after the backup. When an image has performed an incompatible database
migration, inspect the deployment logs and restore the timestamped backup under
`/srv/homelab/backups` manually.

The current and pending SHAs are available at:

```text
/srv/homelab/appdata/deployment/current-sha
/srv/homelab/appdata/deployment/pending-sha
```

The workflow can also be started manually from GitHub Actions with `main`
selected. A manual run validates, applies, and redeploys the selected main
commit. Runs dispatched against other branches or tags skip all jobs.
