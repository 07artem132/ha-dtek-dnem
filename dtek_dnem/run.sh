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

cd /
exec /opt/venv/bin/python -m app.server
