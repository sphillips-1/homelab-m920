FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap ca-certificates git openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global happy@1.2.7 @openai/codex@0.172.0 \
    && happy --version \
    && codex --version

USER node
WORKDIR /workspace
CMD ["sh", "-ec", "until [ -f /home/node/.paired ]; do sleep 5; done; exec happy daemon start-sync"]
