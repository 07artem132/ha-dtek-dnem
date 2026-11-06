"""Читання порталу ДТЕК справжнім Chromium (як людина у браузері).

Без stealth-плагінів, без підміни fingerprint і без розв'язування капч:
відкриваємо сторінку, чекаємо, поки портал сам видасть ajaxUrl, і робимо
той самий AJAX-запит, що й фронтенд сторінки. Якщо WAF не пускає, кидаємо
BlockedError, а викликач відступає (backoff), а не намагається обійти.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.parse
from typing import Any
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://www.dtek-dnem.com.ua"
PAGE_PATH = "/ua/shutdowns"
FALLBACK_AJAX = "/ua/ajax"
WAF_MARKERS = ("_Incapsula_Resource", "visid_incap", "incap_ses")

_FETCH_JS = """
const [url, body, csrf, done] = arguments;
const headers = {
  'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
  'X-Requested-With': 'XMLHttpRequest',
  'Accept': 'application/json, text/javascript, */*; q=0.01',
};
if (csrf) headers['X-CSRF-Token'] = csrf;
fetch(url, {method: 'POST', credentials: 'same-origin', headers, body})
  .then(r => r.text().then(t => done({status: r.status, text: t})))
  .catch(e => done({status: 0, text: String(e)}));
"""

_META_JS = """
const m = n => { const e = document.querySelector('meta[name="' + n + '"]');
                 return e ? e.getAttribute('content') : null; };
return {ajax: m('ajaxUrl'), csrf: m('csrf-token')};
"""


class FetchError(Exception):
    """Загальна помилка читання порталу."""


class BlockedError(FetchError):
    """WAF / challenge не пропустив сторінку."""


_PAGE_SCHEDULE_JS = """
// Графік (fact/preset) сторінка отримує у глобальній змінній; читаємо її як це робить сам фронтенд.
const keys = Object.keys(window).filter(k => /discon/i.test(k));
let src = null;
for (const k of keys) {
  const v = window[k];
  if (v && typeof v === 'object' && (v.fact || v.preset)) { src = v; break; }
}
if (!src) return {keys: keys, fact: null, preset: null};
const pick = o => { try { return JSON.parse(JSON.stringify(o)); } catch (e) { return null; } };
return {keys: keys, fact: pick(src.fact), preset: pick(src.preset)};
"""


def build_form(
    method: str,
    fields: list[tuple[str, str]] | None = None,
    extra: dict[str, str] | None = None,
) -> str:
    form: dict[str, str] = {"method": method, **(extra or {})}
    for i, (name, value) in enumerate(fields or []):
        form[f"data[{i}][name]"] = name
        form[f"data[{i}][value]"] = value
    return urllib.parse.urlencode(form)


def _make_driver() -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    opts.binary_location = os.environ.get("CHROMIUM_BIN", "/usr/bin/chromium")
    for arg in (
        "--headless=new",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--lang=uk-UA",
    ):
        opts.add_argument(arg)
    service = Service(os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver"))
    return webdriver.Chrome(service=service, options=opts)


def run_calls(
    calls: list[tuple],
    with_schedule: bool = False,
) -> tuple[list[Any], dict | None]:
    """Відкриває браузер ОДИН раз: AJAX-виклики (method, fields[, extra]) + опційно графік зі сторінки."""
    driver = _make_driver()
    try:
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(30)
        driver.get(BASE_URL + PAGE_PATH)

        meta: dict[str, Any] = {}
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            meta = driver.execute_script(_META_JS) or {}
            if meta.get("ajax"):
                break
            time.sleep(1)

        if not meta.get("ajax"):
            html = driver.page_source or ""
            if any(m in html for m in WAF_MARKERS):
                raise BlockedError("WAF challenge не пройдено у браузері")
            _LOGGER.warning("meta ajaxUrl не знайдено, використовую %s", FALLBACK_AJAX)
        ajax_url = urljoin(BASE_URL, (meta.get("ajax") or FALLBACK_AJAX).replace("\\/", "/"))

        page_schedule = driver.execute_script(_PAGE_SCHEDULE_JS) if with_schedule else None

        results: list[Any] = []
        for call in calls:
            method, fields = call[0], call[1]
            extra = call[2] if len(call) > 2 else None
            res = driver.execute_async_script(
                _FETCH_JS, ajax_url, build_form(method, fields, extra), meta.get("csrf")
            )
            status = res.get("status")
            if status in (401, 403, 429) or (
                status == 200 and any(m in res["text"] for m in WAF_MARKERS)
            ):
                raise BlockedError(f"HTTP {status} від порталу")
            if status != 200:
                raise FetchError(f"{method}: HTTP {status}")
            try:
                results.append(json.loads(res["text"]))
            except json.JSONDecodeError as exc:
                raise FetchError(f"{method}: не JSON") from exc
        return results, page_schedule
    finally:
        driver.quit()
