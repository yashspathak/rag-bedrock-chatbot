#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
BUCKET="${S3_BUCKET:-rag-docs}"
DOMAIN="${OPENSEARCH_DOMAIN:-rag-vectors}"
AWS=(aws --endpoint-url "${ENDPOINT}" --region "${AWS_DEFAULT_REGION}")

if ! command -v aws >/dev/null 2>&1; then
  echo "AWS CLI v2 is required for bootstrap. Install it, then re-run this script." >&2
  exit 1
fi

if ! curl -sf "${ENDPOINT}/_localstack/health" >/dev/null; then
  echo "LocalStack is not reachable at ${ENDPOINT}. Start it with: docker compose up -d" >&2
  exit 1
fi

echo "Creating S3 bucket s3://${BUCKET} ..."
if "${AWS[@]}" s3api head-bucket --bucket "${BUCKET}" >/dev/null 2>&1; then
  echo "Bucket already exists."
else
  "${AWS[@]}" s3 mb "s3://${BUCKET}"
fi

echo "Creating OpenSearch domain ${DOMAIN} ..."
if "${AWS[@]}" opensearch describe-domain --domain-name "${DOMAIN}" >/dev/null 2>&1; then
  echo "Domain already exists."
else
  "${AWS[@]}" opensearch create-domain \
    --domain-name "${DOMAIN}" \
    --engine-version "OpenSearch_2.11"
fi

echo "Waiting for OpenSearch domain to become active ..."
for _ in $(seq 1 60); do
  processing="$("${AWS[@]}" opensearch describe-domain --domain-name "${DOMAIN}" \
    --query 'DomainStatus.Processing' --output text 2>/dev/null || echo true)"
  endpoint="$("${AWS[@]}" opensearch describe-domain --domain-name "${DOMAIN}" \
    --query 'DomainStatus.Endpoint' --output text 2>/dev/null || echo None)"
  if [[ "${processing}" == "False" || "${processing}" == "false" ]] && [[ "${endpoint}" != "None" && -n "${endpoint}" ]]; then
    break
  fi
  sleep 2
done

endpoint="$("${AWS[@]}" opensearch describe-domain --domain-name "${DOMAIN}" \
  --query 'DomainStatus.Endpoint' --output text)"

if [[ "${endpoint}" == "None" || -z "${endpoint}" ]]; then
  echo "OpenSearch domain did not become ready. Check LocalStack logs." >&2
  exit 1
fi

if [[ "${endpoint}" != http* ]]; then
  endpoint="http://${endpoint}"
fi

echo "S3 bucket:           s3://${BUCKET}"
echo "OpenSearch endpoint: ${endpoint}"
echo "Bootstrap complete."
