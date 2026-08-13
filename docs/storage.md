# Storage

## Storage boundary

The repository and operating-system configuration live under:

```text
/opt/homelab
```

Persistent Homelab data lives under:

```text
/srv/homelab
```

## Directory layout

```text
/srv/homelab/
├── appdata/
│   ├── audiobookshelf/
│   ├── calibre-web/
│   ├── homepage/
│   └── monitoring/
│
├── media/
│   ├── audiobooks/
│   └── ebooks/
│
└── backups/
```

## Rules

- Do not store large media files in Git.
- Do not store application databases in Git.
- Do not store secrets in Git.
- Application containers should mount persistent state from `/srv/homelab`.
- Storage setup should be automated by repository scripts where practical.

The physical disk/partition layout will be documented after the M920Q hardware is inventoried.
