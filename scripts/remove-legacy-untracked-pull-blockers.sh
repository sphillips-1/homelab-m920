#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/homelab"

TARGETS=(
    "config/cloudflared/config.sso.yml.template"
    "docs/application-sso.md"
    "docs/user-onboarding.md"
    "scripts/backup-applications.sh"
)

[[ -d "${REPO_DIR}/.git" ]] || {
    echo "ERROR: Git repository not found at ${REPO_DIR}." >&2
    exit 1
}

cd "${REPO_DIR}"

for path in "${TARGETS[@]}"; do
    if [[ ! -e "${path}" ]]; then
        echo "Already absent: ${path}"
        continue
    fi

    if git ls-files --error-unmatch -- "${path}" >/dev/null 2>&1; then
        echo "ERROR: Refusing to remove tracked file: ${path}" >&2
        exit 1
    fi

    status="$(git status --porcelain=v1 --untracked-files=all -- "${path}")"
    if [[ "${status}" != "?? ${path}" ]]; then
        echo "ERROR: Refusing to remove path with unexpected Git status: ${status:-unknown} (${path})" >&2
        exit 1
    fi

    rm -- "${path}"
    echo "Removed untracked pull blocker: ${path}"
done

echo "Legacy untracked pull blockers removed. Run: git pull --ff-only"
