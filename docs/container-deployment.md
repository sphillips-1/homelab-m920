# Container deployment

Pushes to `main` that change service definitions, scripts, or the container
workflows deploy automatically on the existing M920Q GitHub Actions runner.
Terraform continues to use its separate workflows.

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

Protect `main` with pull-request review and require the **Container PR** check.
Repository write access is production-equivalent because reviewed repository
code controls Docker workloads and the root deployment process.

## Deployment behavior

The **Container Deploy** workflow is serialized and invokes the exact pushed
commit. The host deployment command:

1. locks against concurrent deployments;
2. refuses to overwrite tracked local changes;
3. verifies the commit belongs to `origin/main`;
4. backs up affected state when a stateful Compose definition changed;
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

The workflow can also be started manually from GitHub Actions. A manual run
redeploys and verifies the commit selected by GitHub for that run.
