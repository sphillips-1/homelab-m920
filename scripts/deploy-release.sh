#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="/opt/homelab"
DEPLOY_STATE_DIR="/srv/homelab/appdata/deployment"
LOCK_FILE="/run/lock/homelab-deploy.lock"
TARGET_SHA="${1:-}"
PREVIOUS_SHA=""
CHECKED_OUT_TARGET=false

log() {
    echo
    echo "==> $1"
}

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

git_repo() {
    git -c safe.directory="${REPO_DIR}" -C "${REPO_DIR}" "$@"
}

rollback() {
    local exit_code=$?
    trap - ERR

    if [[ "${CHECKED_OUT_TARGET}" == true && -n "${PREVIOUS_SHA}" ]]; then
        echo "Deployment failed; restoring repository and Compose definitions from ${PREVIOUS_SHA}." >&2
        git_repo checkout --detach --force "${PREVIOUS_SHA}" || true
        "${REPO_DIR}/scripts/deploy-services.sh" || true
        printf '%s\n' "${PREVIOUS_SHA}" > "${DEPLOY_STATE_DIR}/current-sha" || true
    fi

    echo "Persistent data was not automatically restored. Use the pre-deployment backup if an image performed an incompatible database migration." >&2
    exit "${exit_code}"
}

[[ "${EUID}" -eq 0 ]] || fail "Run this script as root."
[[ "${TARGET_SHA}" =~ ^[0-9a-f]{40}$ ]] || fail "Pass one full 40-character lowercase Git commit SHA."
[[ -d "${REPO_DIR}/.git" ]] || fail "Repository not found at ${REPO_DIR}."

exec 9>"${LOCK_FILE}"
flock --nonblock 9 || fail "Another container deployment is already running."

if ! git_repo diff --quiet || ! git_repo diff --cached --quiet; then
    fail "Tracked files in ${REPO_DIR} have local changes; refusing to overwrite them."
fi

log "Fetching origin/main"
git_repo fetch --prune origin main
git_repo cat-file -e "${TARGET_SHA}^{commit}" 2>/dev/null || fail "Commit ${TARGET_SHA} was not fetched."
git_repo merge-base --is-ancestor "${TARGET_SHA}" origin/main || fail "Commit ${TARGET_SHA} is not contained in origin/main."

PREVIOUS_SHA="$(git_repo rev-parse HEAD)"
install -d -m 0700 "${DEPLOY_STATE_DIR}"
printf '%s\n' "${TARGET_SHA}" > "${DEPLOY_STATE_DIR}/pending-sha"

changed_files="$(git_repo diff --name-only "${PREVIOUS_SHA}" "${TARGET_SHA}")"

if grep -qx 'services/authentik/compose.yml' <<<"${changed_files}" &&
   docker inspect authentik-postgresql >/dev/null 2>&1; then
    log "Backing up Authentik before its image or Compose configuration changes"
    bash "${REPO_DIR}/scripts/backup-authentik.sh"
fi

if grep -Eq '^services/(audiobookshelf|calibre-web)/compose\.yml$' <<<"${changed_files}" &&
   docker inspect audiobookshelf calibre-web >/dev/null 2>&1; then
    log "Backing up application state before an application image or Compose configuration changes"
    bash "${REPO_DIR}/scripts/backup-applications.sh"
fi

trap rollback ERR

log "Checking out ${TARGET_SHA}"
git_repo checkout --detach --force "${TARGET_SHA}"
CHECKED_OUT_TARGET=true

if [[ "${PREVIOUS_SHA}" == "${TARGET_SHA}" ]]; then
    log "Commit ${TARGET_SHA} is already checked out; verifying the deployment"
    bash "${REPO_DIR}/scripts/verify-services.sh"
    printf '%s\n' "${TARGET_SHA}" > "${DEPLOY_STATE_DIR}/current-sha"
    rm -f "${DEPLOY_STATE_DIR}/pending-sha"
    exit 0
fi

log "Validating Compose configuration"
while IFS= read -r compose_file; do
    docker compose -f "${compose_file}" config --quiet
done < <(find "${REPO_DIR}/services" -name compose.yml -type f -print | sort)

log "Pulling declared container images"
while IFS= read -r compose_file; do
    docker compose -f "${compose_file}" pull
done < <(find "${REPO_DIR}/services" -name compose.yml -type f -print | sort)

log "Deploying services"
"${REPO_DIR}/scripts/deploy-services.sh"

log "Verifying service health"
bash "${REPO_DIR}/scripts/verify-services.sh"

printf '%s\n' "${TARGET_SHA}" > "${DEPLOY_STATE_DIR}/current-sha"
rm -f "${DEPLOY_STATE_DIR}/pending-sha"
install -o root -g root -m 0755 "${REPO_DIR}/scripts/deploy-release.sh" /usr/local/sbin/homelab-deploy
trap - ERR

log "Deployment complete: ${TARGET_SHA}"
