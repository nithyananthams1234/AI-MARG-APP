#!/usr/bin/env bash
# Restore one database from a backup file. DESTRUCTIVE for that database.
# Usage: ./restore.sh marg_db /path/marg_db-20261101T021500Z.dump
set -euo pipefail
cd "$(dirname "$0")"
db="$1"; file="$2"
read -r -p "This REPLACES all data in '$db'. Type the database name to continue: " confirm
[ "$confirm" = "$db" ] || { echo "Aborted."; exit 1; }
docker compose stop backend worker mentor-intelligence
docker compose exec -T postgres pg_restore -U postgres --clean --if-exists -d "$db" < "$file"
docker compose start backend worker mentor-intelligence
echo "Restored $db from $file"
