#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
export MIN_POLL_MINUTES="$(bashio::config 'min_poll_interval_minutes')"
export LOG_LEVEL="$(bashio::config 'log_level')"

NEED_RESTART=0
# Встановлення/оновлення інтеграції dtek_dnem у /config/custom_components (без HACS).
if bashio::config.true 'install_integration' && [ -d /homeassistant ]; then
  SRC=/integration/dtek_dnem
  DST=/homeassistant/custom_components/dtek_dnem
  if ! diff -rq -x __pycache__ "$SRC" "$DST" >/dev/null 2>&1; then
    mkdir -p /homeassistant/custom_components
    rm -rf "$DST"
    cp -r "$SRC" "$DST"
    NEED_RESTART=1
    bashio::log.warning "Інтеграцію dtek_dnem встановлено/оновлено, потрібен перезапуск Home Assistant."
  else
    bashio::log.info "Інтеграція dtek_dnem актуальна."
  fi
fi

# Auto-discovery: повідомляємо Supervisor, щоб HA показав картку «Discovered» (як у Signal add-on).
(
  for _ in $(seq 1 60); do
    curl -sf http://127.0.0.1:8099/health >/dev/null && break
    sleep 2
  done
  CONFIG="$(jq -n --arg host "$(bashio::addon.hostname)" '{host: $host, port: 8099}')"
  if bashio::discovery "dtek_dnem" "${CONFIG}" >/dev/null; then
    bashio::log.info "Discovery для HA опубліковано."
  else
    bashio::log.warning "Не вдалося опублікувати discovery (додайте інтеграцію вручну: http://<IP_HA>:8099)."
  fi
  # Запит на перезапуск у UI HA (persistent notification), а не лише рядок у лозі.
  if [ "${NEED_RESTART:-0}" = "1" ]; then
    BODY="$(jq -n '{notification_id: "dtek_dnem_restart", title: "ДТЕК Дніпро: потрібен перезапуск", message: "Add-on встановив/оновив інтеграцію dtek_dnem. [Перезапустити Home Assistant](/config/system)."}')"
    for _ in $(seq 1 30); do
      curl -sf -X POST -H "Authorization: Bearer ${SUPERVISOR_TOKEN}" -H "Content-Type: application/json" \
        -d "${BODY}" http://supervisor/core/api/services/persistent_notification/create >/dev/null && break
      sleep 10
    done
  fi
) &

cd /
exec /opt/venv/bin/python -m app.server
