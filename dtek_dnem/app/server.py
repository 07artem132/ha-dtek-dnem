"""HTTP API add-on'а: /api/cities, /api/streets, /api/houses, /api/schedule."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from aiohttp import web

from . import fetcher
from .parse import build_schedule, parse_houses

_LOGGER = logging.getLogger("dtek_dnem")

MIN_POLL = int(os.environ.get("MIN_POLL_MINUTES", "30")) * 60
CATALOG_TTL = 24 * 3600
BACKOFF_START, BACKOFF_MAX = 15 * 60, 6 * 3600

_lock = asyncio.Lock()  # один браузер за раз (Pi має мало RAM)
_cache: dict[str, tuple[float, Any]] = {}
_blocked_until = 0.0
_backoff = BACKOFF_START


async def _call(calls, with_schedule=False):
    global _blocked_until, _backoff
    if time.time() < _blocked_until:
        raise web.HTTPServiceUnavailable(
            text=f"blocked, retry after {int(_blocked_until - time.time())}s"
        )
    async with _lock:
        try:
            res = await asyncio.get_running_loop().run_in_executor(
                None, fetcher.run_calls, calls, with_schedule
            )
            _backoff = BACKOFF_START
            return res
        except fetcher.BlockedError as exc:
            _blocked_until = time.time() + _backoff
            _LOGGER.warning("%s; пауза %d хв", exc, _backoff // 60)
            _backoff = min(_backoff * 2, BACKOFF_MAX)
            raise web.HTTPServiceUnavailable(text=f"blocked: {exc}")
        except fetcher.FetchError as exc:
            raise web.HTTPBadGateway(text=str(exc))


async def _cached(key: str, ttl: int, factory):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    value = await factory()
    _cache[key] = (time.time(), value)
    return value


async def cities(_: web.Request) -> web.Response:
    async def f():
        (raw,), _ = await _call([("getStreets", None)])
        return raw.get("streets") or raw.get("data") or {}

    streets = await _cached("streets", CATALOG_TTL, f)
    return web.json_response(sorted(streets) if isinstance(streets, dict) else [])


async def streets(req: web.Request) -> web.Response:
    city = req.query.get("city", "")
    await cities(req)  # прогріває кеш
    data = _cache["streets"][1]
    return web.json_response(sorted(data.get(city, [])) if isinstance(data, dict) else [])


async def _home(city: str, street: str) -> dict:
    async def f():
        calls = [("getHomeNum", [("city", city), ("street", street)])]
        (raw,), page = await _call(calls, with_schedule=True)
        raw = dict(raw)
        if page:
            for k in ("fact", "preset"):
                if page.get(k) and k not in raw:
                    raw[k] = page[k]
        if "fact" not in raw and "preset" not in raw:
            # Запасний шлях: той самий виклик, що робить фронтенд для оновлення графіка.
            (extra,), _ = await _call(
                [("checkDisconUpdate", None, {"update": "01.01.2000 00:00"})]
            )
            if isinstance(extra, dict):
                raw.update({k: extra[k] for k in ("fact", "preset") if k in extra})
        raw["_page_keys"] = (page or {}).get("keys")
        return raw

    return await _cached(f"home:{city}|{street}", MIN_POLL, f)


async def houses(req: web.Request) -> web.Response:
    raw = await _home(req.query.get("city", ""), req.query.get("street", ""))
    return web.json_response(sorted(parse_houses(raw)))


async def schedule(req: web.Request) -> web.Response:
    q = req.query
    raw = await _home(q.get("city", ""), q.get("street", ""))
    return web.json_response(build_schedule(raw, q.get("house", "")))


def _shape(v, depth=0):
    """Структура відповіді без персональних значень (для діагностики формату порталу)."""
    if isinstance(v, dict):
        if depth >= 4:
            return f"dict[{len(v)}]"
        return {str(k): _shape(x, depth + 1) for k, x in list(v.items())[:6]}
    if isinstance(v, list):
        return [f"list[{len(v)}]"] + ([_shape(v[0], depth + 1)] if v else [])
    return v if isinstance(v, (int, float, bool)) or v is None else str(v)[:40]


async def debug(req: web.Request) -> web.Response:
    q = req.query
    raw = await _home(q.get("city", ""), q.get("street", ""))
    data = raw.get("data")
    house = data.get(q.get("house", "")) if isinstance(data, dict) else None
    return web.json_response({"top_keys": list(raw), "house_entry": house, "shape": _shape(raw)})


async def health(_: web.Request) -> web.Response:
    return web.json_response(
        {"ok": True, "blocked_for_s": max(0, int(_blocked_until - time.time()))}
    )


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "info").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    app = web.Application()
    app.add_routes(
        [
            web.get("/health", health),
            web.get("/api/cities", cities),
            web.get("/api/streets", streets),
            web.get("/api/houses", houses),
            web.get("/api/schedule", schedule),
            web.get("/api/debug", debug),
        ]
    )
    web.run_app(app, host="0.0.0.0", port=8099)


if __name__ == "__main__":
    main()
