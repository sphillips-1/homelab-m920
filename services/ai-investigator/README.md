# AI investigator pilot

The pilot accepts synthetic alerts through Alertmanager, summarizes them with
the existing Ollama instance, writes delivery state to SQLite, and publishes to
**Phillips Collab Area → #something-is-borked**. It needs no Docker socket or remediation
credentials. The Deploy workflow starts the pilot only when its GitHub
environment secret is configured.

Alertmanager forwards alerts grouped by all labels, so each webhook represents
one alert. The investigator treats a repeat with the same labels, start time
and status as a duplicate. A resolution can publish separately. Inference
uses one worker, with a 12-second HTTP timeout, and falls back to the original
alert when Ollama fails. Discord delivery disables automatic mentions. A webhook
failure returns a retriable error and preserves the message in SQLite. An
interruption after Discord accepts a message and before
SQLite records delivery can cause a duplicate on retry.

## Host measurements

On November 19, 2026, the M920Q ran three short Qwen3 summaries in 3.72 s,
1.33 s and 1.08 s. The model was cold for the first request. Available RAM
went from 12,265 to 10,660 MiB. Swap remained at 3,476 MiB, with no swap-out
during the sampled requests. Ollama had no model loaded at the start. A
concurrent coding workload and peak-load behavior remain unmeasured.

Beszel was active. No local Prometheus, Grafana, Node Exporter or Alertmanager
was visible in the container, process, service or listener inventory. Any
off-host monitoring endpoints still need confirmation. The pilot can run from
synthetic input while that is resolved.

## Smoke test

With Python, install `requirements.txt` in a virtual environment and
run `python -B smoke.py /path/to/alertmanager`. The test starts
real Alertmanager and a mock Discord receiver on temporary loopback ports and simulates Ollama
success and timeout. It checks the notification content, deduplication and
SQLite delivery state. It cleans up the local processes and test database.
Set `PILOT_SMOKE_OLLAMA_URL=http://127.0.0.1:11434` to use the host's Ollama
for the successful alert while keeping the timeout case simulated.

For a host rollout after approval, store the dedicated webhook URL for
`#something-is-borked` in the GitHub `infrastructure` environment secret
`AI_INVESTIGATOR_DISCORD_WEBHOOK`. The runner provisions the private URL file
with mode `0600` and sets up the persistent directory under
`/srv/homelab/appdata/ai-investigator` for UID/GID 10001.
Compose joins the existing `local-ai_local-ai` network for inference and
needs outbound HTTPS to Discord. Alertmanager publishes a loopback port for
synthetic alerts and reaches the investigator on a private Docker network.
Use SSH forwarding for the test port. Review channel membership and set an
incident retention policy before sending alerts that contain real evidence.

## Beszel disk alerts

In Beszel **Settings → Notifications**, add a generic notification URL for the
private investigator. Keep any existing destinations in the list.

```text
generic://ai-investigator-webhook:8080/beszel?template=json&disabletls=yes
```

Enable a Disk alert on the `m920` system. Start at 85% for 10 minutes. Beszel
sends all configured notification types to the URL. The receiver accepts only
the M920Q disk threshold and recovery titles, verifies that requests originate
from the Beszel hub on the Docker network, and suppresses repeated events in
the same state. Apply through the normal Deploy workflow before saving the new
notification destination in Beszel.
