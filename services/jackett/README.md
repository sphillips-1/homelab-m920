# Jackett

GitHub Actions deploys Jackett on the M920Q. Jackett stores its API key and
indexer settings in `/srv/homelab/appdata/jackett`. HolyArrs reaches Jackett
at `http://jackett:9117` over the shared Docker network. The admin interface
binds to host loopback and has no public route.

Open an SSH tunnel for dashboard access:

```sh
ssh -N -L 19117:127.0.0.1:9117 sean@192.168.4.27
```

Open `http://127.0.0.1:19117`, set a Jackett admin password, then add and
test AudioBook Bay. Use its **Copy Torznab Feed** button. Keep the feed path
and replace the dashboard origin with `http://jackett:9117` for HolyArrs.
Enter the Jackett API key in the separate field and enable **Allow local
network** for that source.
