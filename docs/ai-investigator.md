# Homelab AI investigator

## Existing AI and monitoring

The M920Q runs Ollama for local inference, Open WebUI for browser chat via
Authentik, and supports Continue as an editor-side client over SSH forwarding.
No Aider service or separate coding agent was found in the repository or the
host inventory. Both AI containers were healthy during the audit. Installed
models were `qwen2.5-coder:3b`, `deepseek-coder:1.3b`, and the shared-weight
`shelfgoblin-coder:3b` chat wrapper. Ollama had no model loaded at the time.

Keep the coding stack and share its inference backend with the investigator.
Ollama stays on its dedicated Docker network with a loopback-only host binding.
The existing CPU and RAM limits are three CPUs and 6 GiB for Ollama and one CPU
and 2 GiB for WebUI. Ollama uses one request slot, one loaded model, a 4,096-token
context, and an eight-request queue. The two workloads can see queue delays
and model reloads when used together.

## Host audit

Snapshot from 2026-11-19 at 1:35 p.m. Eastern on the M920Q:

| Measurement | Observed |
| --- | --- |
| CPU and load average | i5-8500T, six logical CPUs, 0.63 / 0.73 / 0.84 |
| RAM | 15,833 MiB total, 3,432 MiB used, 12,400 MiB available |
| Swap | 3,675 of 12,595 MiB used |
| Disk | 130 GiB available on the shared root/appdata filesystem |
| Containers | Ollama 21 MiB idle, WebUI 210 MiB, qBittorrent about 6 GiB in Docker stats |
| Monitoring | Active Beszel hub and agent and Pi-hole monitor. No Prometheus, Grafana, or Node Exporter seen in local Docker, process, or running service inventory. |

This snapshot supports provisioning Qwen3 and trialing occasional serialized
inference. Existing swap usage and an idle Ollama make peak-load capacity
uncertain. Before enabling alert-driven inference, measure generation latency,
swap activity, and memory pressure with normal services active and while
coding inference is in use. Check Beszel history for peak demand and confirm
whether the stated Prometheus stack runs elsewhere.

The audit script writes a timestamped report to stdout. Run it on the host or
stream it from this checkout using the address in the network inventory:

```bash
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes sean@192.168.4.27 'bash -s' \
  < scripts/audit-ai-host.sh > "/tmp/ai-host-audit-$(date -u +%Y%m%dT%H%M%SZ).txt"
```

Run the command from the checkout. The Docker account needs permission to
query inventory and stats. The script reads process names and selected Docker
fields and avoids process arguments, environment values, and application logs.

## Phase 1

The existing deployment installs and verifies `qwen3:1.7b` in the same Ollama
instance. The model is about 1.4 GB. Provisioning checks for 5 GiB free on the
model filesystem before downloading it and reuses the existing persistent
model store at `/srv/homelab/appdata/local-ai/ollama`.
[Ollama model registry](https://ollama.com/library/qwen3:1.7b)

After approval, submit the scoped changes to `main` through the existing review
and merge process. The Deploy workflow runs on a main update and
supports manual dispatch on main when needed. Review its validation and
service verification results. Rerun the audit to verify the new model appears.
The full deployment can reconcile and recreate containers depending on
the configuration deployed. Obtain approval for the push or merge and for
the production deployment window before triggering it.

## Later phases

Confirm Prometheus, Grafana and Node Exporter endpoints and ownership before
deciding whether any monitoring services need deployment. Reuse existing
ones where available. Use cAdvisor for container metrics, Alloy to collect
logs, Loki for bounded log storage, and Alertmanager for alert delivery to an
internal FastAPI endpoint. Keep Grafana for human investigation.

Have FastAPI deduplicate alerts in SQLite under
`/srv/homelab/appdata/ai-investigator` and process a bounded queue with one
inference worker. Query designated Prometheus and Loki endpoints for bounded
evidence and ask the existing Ollama instance for a short, evidence-linked
summary. Treat log text as untrusted input. Keep the investigator off the
Docker socket and limit its write access to incident history and a dedicated
ntfy publishing topic. Deliver a basic alert when inference times out or fails.
Keep the authenticated ntfy receiver private. Review the Phase 2 rollout,
retention budgets, and notification access before enabling those services.
