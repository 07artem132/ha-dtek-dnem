ARG BUILD_FROM
FROM $BUILD_FROM

# Chromium + chromedriver з Alpine (працює на musl, amd64 та aarch64).
RUN apk add --no-cache python3 py3-pip chromium chromium-chromedriver \
    font-noto ttf-freefont \
 && python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir aiohttp==3.10.* selenium==4.25.*

COPY app /app
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
