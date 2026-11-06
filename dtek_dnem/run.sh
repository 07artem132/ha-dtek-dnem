#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
export MIN_POLL_MINUTES="$(bashio::config 'min_poll_interval_minutes')"
export LOG_LEVEL="$(bashio::config 'log_level')"
cd /
exec /opt/venv/bin/python -m app.server
