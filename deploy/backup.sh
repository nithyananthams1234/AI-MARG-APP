#!/usr/bin/env bash
# Nightly backup of both MARG databases to S3-compatible storage.
# Install on the server:  crontab -e  ->  15 2 * * * /opt/marg/deploy/backup.sh >> /var/log/marg-backup.log 2>&1
# Requires: docker compose, aws CLI (works with R2/B2/MinIO via --endpoint-url).
set -euo pipefail
cd "$(dirname "$0")"
set -a; . ./.env; set +a

stamp=$(date -u +%Y%m%dT%H%M%SZ)
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

for db in marg_db marg_mentor_intelligence; do
  docker compose exec -T postgres pg_dump -U postgres -Fc "$db" > "$dir/$db-$stamp.dump"
  # Verify the archive is readable before uploading.
  docker compose exec -T postgres pg_restore --list < "$dir/$db-$stamp.dump" > /dev/null
  AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
    aws s3 cp "$dir/$db-$stamp.dump" "s3://$S3_BACKUP_BUCKET/postgres/$db/$db-$stamp.dump" \
    --endpoint-url "$S3_ENDPOINT_URL" --only-show-errors
done
echo "$(date -u) backup ok ($stamp)"
# Retention: configure a lifecycle rule on the bucket (e.g. delete after 30 days).
