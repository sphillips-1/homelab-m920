# Happy Coder on the M920

The Deploy Happy Coder GitHub Actions workflow builds and starts an isolated
container with the Happy CLI and Codex. It publishes no ports and uses Happy's
hosted relay. Its home directory and workspace live under
`/srv/homelab/appdata/happy-coder`. The container can work in `/workspace`.
It has no mount for the production checkout, Docker socket, or media.

## First-time pairing

Open an interactive SSH terminal to the M920 and run these commands there.
Keep the pairing QR code and the OpenAI device code in your terminal.

```sh
docker exec -it happy-coder happy auth login
docker exec -it happy-coder codex login --device-auth
docker exec happy-coder codex login status
docker exec happy-coder touch /home/node/.paired
```

Scan the QR code in Happy Coder and approve the connection. Complete the Codex
device sign-in in your browser. After both sign-ins succeed, the final command
allows the daemon to start automatically and persist across container restarts.

In Happy Coder, select `m920-happy`, choose Codex and `/workspace`, and run a
test prompt such as “What directory are you running in?” Put any repositories
you want Happy to work on under `/workspace`. Deploy homelab changes through
GitHub Actions.
