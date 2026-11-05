# Local coding AI

Browser access: https://ai.shelfgoblin.dev using your existing Authentik Google
identity. Only the owner is initially granted `ai-users`. The embedded proxy gates
all browser traffic; native OIDC creates or matches your private WebUI account.
Local passwords and signup are disabled. Continue retains the private Ollama SSH
tunnel below; it does not use browser SSO.


## Deployment

This stack follows the repository's `services/<name>/compose.yml` convention.
Commit and review the changes, then merge to `main`. The existing **Deploy**
GitHub Actions workflow pulls the images, runs `scripts/init-local-ai.sh` through
`deploy-services.sh`, and verifies both services. To retry, use **Actions → Deploy
→ Run workflow → main**. Do not deploy over SSH or run Compose manually on the host.
The script uses official prebuilt images, waits for Ollama health, downloads
missing models with a 20-minute timeout per model, and starts Open WebUI.
Existing model tags are preserved on reruns; no model download occurs when present.
Initial downloads need Internet access and several GB of free disk space.
The overall deployment currently has a 45-minute Actions timeout, which includes
all other services; unusually slow initial downloads can require a retry.

Versions: Ollama `0.40.14`, Open WebUI `v0.13.0`. Review image updates explicitly;
these are release tags, not immutable digests. Model library tags can also change:
record `ollama show` output before deliberately repulling a model.

## Resource budget

| Service | RAM hard limit | RAM soft reservation | CPU quota | CPU shares |
| --- | --- | --- | --- | --- |
| Ollama | 6 GiB | 3 GiB | 3 | 256 |
| Open WebUI | 2 GiB | 512 MiB | 1 | 256 |

Equal memory and memory-plus-swap limits prohibit container swap. Reservations are
soft pressure hints, not dedicated physical RAM. CPU quotas are hard aggregate
limits; shares lower scheduling priority under contention. No GPU devices are
passed through. Ollama detects CPU instruction support and inference threads;
the three-CPU quota bounds consumption without assuming an exact Core SKU.
For explicit tuning, Ollama API requests accept `options.num_thread`; start at 3.
There is no assumed `OLLAMA_NUM_THREADS` variable here.

The stack can consume 8 GiB, leaving nominally 8 GiB for Linux and existing
services on a 16 GiB host. This does **not** reserve 8 GiB for the host or guarantee
against host OOM: check existing peak consumption in Beszel before enabling the
stack. Reduce these limits or stop competing workloads through repository changes
if the total budget does not fit. An oversized request can still OOM its own
container. Never disable the OOM killer.

Ollama loads one model and handles one request at a time with a queue of eight.
Default context is 4096 tokens. Clients can override context; keep WebUI chat
parameters at 4096 or less. Chat and autocomplete share the same engine, so
switching models incurs reload latency and autocomplete can wait behind chat.
The requested DeepSeek tag is provided as-is; completion quality depends on its
template and Continue version. Neither small model is configured for Agent tools.

`OLLAMA_KEEP_ALIVE=5m` retains the active model between requests. `-1` would keep
it loaded indefinitely, but does not pin physical pages or prevent model eviction
when another model is requested. Keeping both models resident costs more RAM;
this configuration prioritizes the host budget. Background WebUI title, tag,
and follow-up generation are disabled to avoid extra CPU inference.

## Browser and VS Code access

On your workstation, keep this terminal open:

```bash
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -L 127.0.0.1:11434:127.0.0.1:11434 \
  -L 127.0.0.1:3000:127.0.0.1:3000 sean@192.168.4.27
```

In PowerShell, place the command on one line instead of using backslashes.
The address comes from `docs/network-inventory.md`. SSH here forwards traffic
only. Host ports bind only to loopback. WebUI also has the authenticated Cloudflare
route; Ollama has no public route.
Ollama has no API authentication; the SSH connection supplies access control.

Open <https://ai.shelfgoblin.dev> and sign in through Authentik. Your existing
Google-linked owner account has access. Select `qwen2.5-coder:3b` for chat.
Browser access needs no SSH tunnel. For Continue, forward only port 11434;
port 3000 remains a localhost-only diagnostic endpoint and is no longer a local
password-login route. The OIDC callback always returns to the HTTPS hostname.
WebUI talks to `http://ollama:11434` inside Docker; Continue talks directly to
Ollama, not WebUI. WebUI joins the shared `homelab` network for the proxy, while
Ollama remains exclusively on the dedicated AI network.

## Continue config.json (legacy)

Install Continue in VS Code, open its local configuration, and merge these entries
with existing settings. Back up the original first. On Windows the usual file is
`%USERPROFILE%\.continue\config.json`; on Linux/macOS it is
`~/.continue/config.json`. JSON configuration is deprecated by Continue; use the
YAML alternative below if the installed version opens `config.yaml`.

```json
{
  "models": [
    {
      "title": "M920 Qwen Coder Chat",
      "provider": "ollama",
      "model": "qwen2.5-coder:3b",
      "apiBase": "http://127.0.0.1:11434",
      "contextLength": 4096,
      "completionOptions": { "maxTokens": 768, "temperature": 0.2 }
    }
  ],
  "tabAutocompleteModel": {
    "title": "M920 DeepSeek Autocomplete",
    "provider": "ollama",
    "model": "deepseek-coder:1.3b",
    "apiBase": "http://127.0.0.1:11434",
    "contextLength": 2048,
    "completionOptions": { "maxTokens": 128, "temperature": 0.1 }
  },
  "tabAutocompleteOptions": {
    "debounceDelay": 750,
    "maxPromptTokens": 1024
  }
}
```

## Continue config.yaml (current)

Use this **instead of** the JSON example for current Continue installations:

```yaml
name: M920 Local Coding
version: 1.0.0
schema: v1
models:
  - name: M920 Qwen Coder Chat
    provider: ollama
    model: qwen2.5-coder:3b
    apiBase: http://127.0.0.1:11434
    roles: [chat, edit]
    defaultCompletionOptions:
      contextLength: 4096
      maxTokens: 768
      temperature: 0.2
  - name: M920 DeepSeek Autocomplete
    provider: ollama
    model: deepseek-coder:1.3b
    apiBase: http://127.0.0.1:11434
    roles: [autocomplete]
    defaultCompletionOptions:
      contextLength: 2048
      maxTokens: 128
      temperature: 0.1
```

Select this local configuration and the Qwen model in Continue, use Chat mode,
enable tab autocomplete, and reload VS Code if needed. Type a small function
and pause to test inline suggestions. Keep prompts and file selections short.
Remote SSH/Dev Container extension hosts resolve `127.0.0.1` in their own
environment: run the tunnel where Continue executes or forward it into that
environment. A workstation tunnel alone does not reach a remote extension host.

## Verification and recovery

From the workstation while the tunnel is running:

```bash
curl http://127.0.0.1:11434/api/tags
curl http://127.0.0.1:3000/health
curl http://127.0.0.1:11434/api/generate -H 'Content-Type: application/json' -d '{"model":"qwen2.5-coder:3b","prompt":"Write a Python add function.","stream":false,"options":{"num_ctx":4096,"num_thread":3,"num_predict":64}}'
```

PowerShell users can use `curl.exe` for the first two checks and
`Invoke-RestMethod` with a JSON body for generation. CPU inference can take time.
If connection fails, check SSH forwarding and port conflicts before changing
network bindings. A queue-full response means inference is busy; pause autocomplete
while chatting. Review Actions logs for model pull and health timeout failures.
Read-only host diagnostics include `docker stats --no-stream local-ai-ollama
local-ai-webui` and `docker inspect local-ai-ollama` (`State.OOMKilled`).

Persistent state is `/srv/homelab/appdata/local-ai/ollama` and
`/srv/homelab/appdata/local-ai/open-webui`. Back up WebUI state, including its
generated signing secret, consistently while stopped; model blobs are
redownloadable. Existing application backup scripts do not yet include this
stack. Before WebUI upgrades, take a consistent backup: database migrations may
require restoring that backup to roll back, not merely reverting an image tag.
Schedule stop/backup/start operations through GitHub Actions, never direct SSH.

## References

- [Ollama FAQ: residency, concurrency, memory](https://docs.ollama.com/faq)
- [Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.14)
- [Open WebUI release](https://github.com/open-webui/open-webui/releases/tag/v0.13.0)
- [Pinned first-admin behavior](https://github.com/open-webui/open-webui/blob/v0.13.0/backend/open_webui/routers/auths.py)
- [Continue legacy JSON reference](https://github.com/continuedev/continue/blob/main/docs/reference/json-reference.mdx)
- [Continue YAML reference](https://docs.continue.dev/reference)
