"""Розбір відповідей AJAX порталу ДТЕК у нормалізований вигляд (без мережі)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")

# Статуси слоту на порталі: yes / no / maybe / first / second / mfirst / msecond
_DEFINITE = {"no", "first", "second"}
_POSSIBLE = {"maybe", "mfirst", "msecond"}


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def house_entries(payload: dict) -> dict[str, dict]:
    """house_number -> сирий запис будинку з getHomeNum (обидва формати data)."""
    data = payload.get("data", {})
    out: dict[str, dict] = {}
    if isinstance(data, dict):
        for num, entry in data.items():
            out[str(num)] = _as_dict(entry)
    elif isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            num = next(
                (entry[k] for k in ("num", "house_num", "house_number", "name", "id") if entry.get(k)),
                None,
            )
            if num is None:
                continue
            out[str(num)] = entry
    return out


def _groups(entry: dict) -> list[str]:
    groups = entry.get("sub_type_reason") or []
    return [str(g) for g in groups] if isinstance(groups, list) else []


def parse_houses(payload: dict) -> dict[str, list[str]]:
    """house_number -> [group_id,...]."""
    return {n: _groups(e) for n, e in house_entries(payload).items()}


_DATE_FORMATS = ("%d.%m.%Y %H:%M", "%H:%M %d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M")


def _parse_dt(raw: Any) -> str | None:
    """Дата порталу -> ISO у Києві; None, якщо формат невідомий (сирий рядок лишається окремо)."""
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=KYIV).isoformat()
        except ValueError:
            continue
    return None


def parse_emergency(entry: dict) -> dict[str, Any]:
    """Поточне (не за графіком) відключення: причина, початок, очікуваний кінець."""
    reason = str(entry.get("sub_type") or "").strip()
    start_raw = str(entry.get("start_date") or "").strip()
    end_raw = str(entry.get("end_date") or "").strip()
    active = bool(reason or start_raw)
    return {
        "active": active,
        "reason": reason or None,
        "start": _parse_dt(start_raw),
        "end": _parse_dt(end_raw),
        "start_raw": start_raw or None,
        "end_raw": end_raw or None,
        "type": str(entry.get("type") or "") or None,
    }


def slots_to_intervals(
    slots: dict[str, str], day: datetime
) -> list[dict[str, str]]:
    """Слоти доби -> об'єднані інтервали [{start,end,type}].

    Ключі слотів 1..N (N=24 -> година, N=48 -> пів години). Статуси first/second
    означають відключення у першій/другій половині слоту.
    """
    n = len(slots)
    if n == 0:
        return []
    minutes = 1440 // n
    half = minutes // 2
    midnight = day.astimezone(KYIV).replace(hour=0, minute=0, second=0, microsecond=0)

    pieces: list[tuple[datetime, datetime, str]] = []
    for key, status in slots.items():
        try:
            idx = int(key) - 1
        except ValueError:
            continue
        start = midnight + timedelta(minutes=idx * minutes)
        mid = start + timedelta(minutes=half)
        end = start + timedelta(minutes=minutes)
        if status == "no":
            pieces.append((start, end, "definite"))
        elif status == "first":
            pieces.append((start, mid, "definite"))
        elif status == "second":
            pieces.append((mid, end, "definite"))
        elif status == "maybe":
            pieces.append((start, end, "possible"))
        elif status == "mfirst":
            pieces.append((start, mid, "possible"))
        elif status == "msecond":
            pieces.append((mid, end, "possible"))

    pieces.sort(key=lambda p: p[0])
    merged: list[list[Any]] = []
    for s, e, t in pieces:
        if merged and merged[-1][2] == t and merged[-1][1] >= s:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e, t])
    return [
        {"start": s.isoformat(), "end": e.isoformat(), "type": t} for s, e, t in merged
    ]


def build_schedule(
    payload: dict, house: str, now: datetime | None = None
) -> dict[str, Any]:
    """Нормалізований графік для однієї адреси з відповіді getHomeNum (+ fact/preset)."""
    now = (now or datetime.now(KYIV)).astimezone(KYIV)
    entries = house_entries(payload)
    entry = entries.get(house)
    if entry is None:
        return {"status": "house_not_found", "houses": sorted(entries)}
    groups = _groups(entry)
    emergency = parse_emergency(entry)
    if not groups:
        return {"status": "not_in_schedule", "group": None, "emergency": emergency}
    group = groups[0]

    fact = _as_dict(payload.get("fact"))
    preset = _as_dict(payload.get("preset"))
    names = _as_dict(preset.get("sch_names"))
    fact_days = _as_dict(fact.get("data"))

    days: dict[str, list] = {}
    for ts, per_group in fact_days.items():
        slots = _as_dict(_as_dict(per_group).get(group))
        if not slots:
            continue
        try:
            day = datetime.fromtimestamp(int(ts), tz=KYIV)
        except (ValueError, OSError):
            continue
        days[day.date().isoformat()] = slots_to_intervals(
            {k: str(v) for k, v in slots.items()}, day
        )

    return {
        "status": "ok",
        "group": group,
        "group_name": names.get(group, group),
        "multi_group": len(groups) > 1,
        "updated": fact.get("update") or payload.get("updateTimestamp"),
        "days": days,  # {"2026-11-06": [{start,end,type}, ...]}
        "today": now.date().isoformat(),
        "emergency": emergency,
    }
