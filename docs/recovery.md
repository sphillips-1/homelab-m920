# Recovery

The intended recovery model is:

```text
Fresh Debian installation
        ↓
Clone repository
        ↓
Run bootstrap
        ↓
Restore /srv/homelab
        ↓
Deploy services
        ↓
Verify
```

The repository should contain everything necessary to recreate the host configuration.

Backups must contain the persistent state that cannot be reconstructed from Git, especially application databases and configuration.
