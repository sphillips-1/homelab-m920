# Migration

The M920Q will eventually become the primary host for services currently running on Raspberry Pi hardware.

Migration should be performed in stages:

1. Install and configure Debian.
2. Clone this repository.
3. Run the base/bootstrap configuration.
4. Configure Docker and Tailscale.
5. Create `/srv/homelab`.
6. Deploy services.
7. Migrate application state.
8. Migrate media.
9. Verify services.
10. Retire or repurpose the old host only after verification.

Use `deployment-runbook.md` as the executable version of this sequence. It
identifies which scripts are manual, which are invoked by other automation,
and where each service's one-time application setup belongs.

Audiobookshelf data should be migrated with particular care because its database and metadata are persistent application state.
