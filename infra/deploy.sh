#!/usr/bin/env bash
# =============================================================================
# Despliegue de Nexo EP3 en la instancia EC2.
# Uso:
#   EC2_HOST=54.1.2.3 SSH_KEY=~/.ssh/nexo.pem ./infra/deploy.sh
# Variables obligatorias: EC2_HOST, SSH_KEY, DB_PASSWORD, RABBITMQ_PASSWORD,
#                         NVIDIA_API_KEY, ANONYMIZATION_SALT
# =============================================================================
set -euo pipefail

EC2_HOST="${EC2_HOST:-}"
SSH_KEY="${SSH_KEY:-}"
SSH_USER="${SSH_USER:-ec2-user}"
REMOTE_DIR="${REMOTE_DIR:-/opt/nexo}"
IMAGE_TAG="${IMAGE_TAG:-ep3}"
DOMAIN="${DOMAIN:-nexo.local}"

DB_PASSWORD="${DB_PASSWORD:-}"
RABBITMQ_PASSWORD="${RABBITMQ_PASSWORD:-}"
NVIDIA_API_KEY="${NVIDIA_API_KEY:-}"
ANONYMIZATION_SALT="${ANONYMIZATION_SALT:-}"
SAGEMAKER_ENDPOINT_NAME="${SAGEMAKER_ENDPOINT_NAME:-}"
S3_BUCKET="${S3_BUCKET:-}"
GHCR_USER="${GHCR_USER:-}"
GHCR_PAT="${GHCR_PAT:-}"

if [[ -z "$EC2_HOST" || -z "$SSH_KEY" ]]; then
  echo "ERROR: define EC2_HOST y SSH_KEY" >&2
  exit 1
fi
for requerido in DB_PASSWORD RABBITMQ_PASSWORD NVIDIA_API_KEY ANONYMIZATION_SALT; do
  if [[ -z "${!requerido}" ]]; then
    echo "ERROR: falta la variable $requerido" >&2
    exit 1
  fi
done
if [[ ! -f "$SSH_KEY" ]]; then
  echo "ERROR: no existe la llave SSH: $SSH_KEY" >&2
  exit 1
fi

SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15)
TMP_ENV="$(mktemp)"
trap 'rm -f "$TMP_ENV"' EXIT

cp .env.example "$TMP_ENV"

set_env() {
  local clave="$1" valor="$2"
  awk -v k="$clave" -v v="$valor" '
    BEGIN { FS = OFS = "=" }
    $1 == k { print k "=" v; next }
    { print }
  ' "$TMP_ENV" > "$TMP_ENV.new"
  mv "$TMP_ENV.new" "$TMP_ENV"
}

set_env IMAGE_TAG "$IMAGE_TAG"
set_env DOMAIN "$DOMAIN"
set_env DB_PASSWORD "$DB_PASSWORD"
set_env RABBITMQ_PASSWORD "$RABBITMQ_PASSWORD"
set_env NVIDIA_API_KEY "$NVIDIA_API_KEY"
set_env ANONYMIZATION_SALT "$ANONYMIZATION_SALT"
set_env SAGEMAKER_ENDPOINT_NAME "$SAGEMAKER_ENDPOINT_NAME"
set_env S3_BUCKET "$S3_BUCKET"

echo "==> Preparando $REMOTE_DIR en $EC2_HOST"
ssh "${SSH_OPTS[@]}" "$SSH_USER@$EC2_HOST" "mkdir -p '$REMOTE_DIR'"

echo "==> Copiando compose y .env"
scp "${SSH_OPTS[@]}" docker-compose.yml "$SSH_USER@$EC2_HOST:$REMOTE_DIR/docker-compose.yml"
scp "${SSH_OPTS[@]}" "$TMP_ENV" "$SSH_USER@$EC2_HOST:$REMOTE_DIR/.env"
ssh "${SSH_OPTS[@]}" "$SSH_USER@$EC2_HOST" "chmod 600 '$REMOTE_DIR/.env'"

if [[ -d datos/datos_tratados ]]; then
  echo "==> Copiando CSV tratados"
  ssh "${SSH_OPTS[@]}" "$SSH_USER@$EC2_HOST" "mkdir -p '$REMOTE_DIR/datos'"
  scp -r "${SSH_OPTS[@]}" datos/datos_tratados "$SSH_USER@$EC2_HOST:$REMOTE_DIR/datos/"
fi

if [[ -n "$GHCR_PAT" ]]; then
  echo "==> Login en GHCR"
  printf '%s' "$GHCR_PAT" | ssh "${SSH_OPTS[@]}" "$SSH_USER@$EC2_HOST" \
    "docker login ghcr.io -u '$GHCR_USER' --password-stdin"
fi

echo "==> Descargando imágenes :$IMAGE_TAG y levantando servicios"
ssh "${SSH_OPTS[@]}" "$SSH_USER@$EC2_HOST" "cd '$REMOTE_DIR' && \
  docker compose pull && docker compose up -d --remove-orphans && \
  docker compose ps"

echo "==> Despliegue completado"
echo "    Health: https://$EC2_HOST/api/health"
echo "    Campañas: POST https://$EC2_HOST/api/campanas/{usuario}"
