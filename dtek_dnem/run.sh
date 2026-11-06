#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
export MIN_POLL_MINUTES="$(bashio::config 'min_poll_interval_minutes')"
export LOG_LEVEL="$(bashio::config 'log_level')"

# Встановлення/оновлення інтеграції dtek_dnem у /config/custom_components (без HACS).
if bashio::config.true 'install_integration' && [ -d /homeassistant ]; then
  SRC=/integration/dtek_dnem
  DST=/homeassistant/custom_components/dtek_dnem
  if ! diff -rq -x __pycache__ "$SRC" "$DST" >/dev/null 2>&1; then
    mkdir -p /homeassistant/custom_components
    rm -rf "$DST"
    cp -r "$SRC" "$DST"
    bashio::log.warning "Інтеграцію dtek_dnem встановлено/оновлено. Перезапустіть Home Assistant, щоб вона з'явилась."
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
) &

cd /
exec /opt/venv/bin/python -m app.server
