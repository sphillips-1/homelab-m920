#!/usr/bin/env bash
set -euo pipefail

HOSTNAME_VALUE="${1:-homelab}"

if [[ "${EUID}" -ne 0 ]]; then
echo "ERROR: Run this script as root."
exit 1
fi

if [[ -z "${HOSTNAME_VALUE}" ]]; then
echo "ERROR: Hostname cannot be empty."
exit 1
fi

echo "==> Configuring hostname: ${HOSTNAME_VALUE}"

hostnamectl set-hostname "${HOSTNAME_VALUE}"

HOSTS_FILE="/etc/hosts"

if grep -qE '^127.0.1.1[[:space:]]' "${HOSTS_FILE}"; then
sed -i
"s/^127.0.1.1[[:space:]].*/127.0.1.1 ${HOSTNAME_VALUE} ${HOSTNAME_VALUE}/"
"${HOSTS_FILE}"
else
printf '127.0.1.1 %s %s\n'
"${HOSTNAME_VALUE}"
"${HOSTNAME_VALUE}" >> "${HOSTS_FILE}"
fi

echo
echo "Hostname:"
hostname

echo
echo "/etc/hosts:"
grep -E '^(127.0.0.1|127.0.1.1)' "${HOSTS_FILE}"

echo
echo "Hostname configuration complete."