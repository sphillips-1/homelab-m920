#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-}"
[[ "${DOMAIN}" =~ ^[A-Za-z0-9.-]+$ ]] || {
    echo "Usage: $0 <domain>" >&2
    exit 2
}

TEST_URL="https://audiobooks-access-test.${DOMAIN}/"
PRODUCTION_URL="https://audiobooks.${DOMAIN}/"

test_headers="$(curl --silent --show-error --head --max-time 20 "${TEST_URL}")"
grep -Eq '^HTTP/[^ ]+ 30[12378]' <<<"${test_headers}" || {
    echo "ERROR: Test hostname did not return an Access redirect." >&2
    exit 1
}
grep -Eiq '^location: .*cloudflareaccess\.com' <<<"${test_headers}" || {
    echo "ERROR: Test hostname did not redirect to Cloudflare Access." >&2
    exit 1
}

production_headers="$(curl --silent --show-error --head --max-time 20 "${PRODUCTION_URL}")"
if grep -Eiq '^location: .*cloudflareaccess\.com' <<<"${production_headers}"; then
    echo "ERROR: Production Audiobookshelf unexpectedly redirects to Cloudflare Access." >&2
    exit 1
fi

echo "PASS: Test hostname is Access-protected and production remains unchanged."
