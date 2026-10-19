#!/usr/bin/env bash
set -Eeuo pipefail

: "${SITE_NAME:?Set SITE_NAME}"
: "${DB_PASSWORD:?Set DB_PASSWORD}"
: "${ADMIN_PASSWORD:?Set ADMIN_PASSWORD}"

wait-for-it -t 180 db:3306
wait-for-it -t 180 redis-cache:6379
wait-for-it -t 180 redis-queue:6379

for _ in $(seq 1 60); do
  if [[ -s sites/common_site_config.json ]] && \
     jq -e '.db_host and .redis_cache and .redis_queue' \
       sites/common_site_config.json >/dev/null; then
    break
  fi
  sleep 2
done
jq -e '.db_host and .redis_cache and .redis_queue' \
  sites/common_site_config.json >/dev/null

if [[ ! -f "sites/$SITE_NAME/site_config.json" ]]; then
  bench new-site "$SITE_NAME" \
    --db-type mariadb \
    --db-host db \
    --db-root-username root \
    --db-root-password "$DB_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --mariadb-user-host-login-scope='%'
fi

installed="$(bench --site "$SITE_NAME" list-apps)"
for app in payments lms nightjar_learning; do
  if ! grep -qx "$app" <<<"$installed"; then
    bench --site "$SITE_NAME" install-app "$app"
    installed="$(bench --site "$SITE_NAME" list-apps)"
  fi
done

bench --site "$SITE_NAME" set-config developer_mode 0
bench --site "$SITE_NAME" set-config host_name "https://$SITE_NAME"
bench --site "$SITE_NAME" execute frappe.client.set_value \
  --kwargs '{"doctype":"Website Settings","name":"Website Settings","fieldname":"disable_signup","value":"0"}' \
  >/dev/null
bench --site "$SITE_NAME" migrate
bench --site "$SITE_NAME" enable-scheduler
bench --site "$SITE_NAME" clear-cache
bench --site "$SITE_NAME" execute nightjar_learning.deployment.check
bench use "$SITE_NAME"

