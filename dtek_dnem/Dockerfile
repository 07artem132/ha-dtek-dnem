ARG BUILD_FROM
FROM $BUILD_FROM

# Усе з apk (musl-збірки), щоб не компілювати нічого на місці.
# selenium ставимо у venv лише з готових wheel (--only-binary), aiohttp береться з системи.
RUN apk add --no-cache python3 py3-pip py3-aiohttp chromium chromium-chromedriver \
    font-noto ttf-freefont \
 && python3 -m venv --system-site-packages /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: "selenium>=4.25,<5"

COPY app /app
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
