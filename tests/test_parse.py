import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "dtek_dnem"))
from app.parse import KYIV, build_schedule, parse_houses, slots_to_intervals  # noqa: E402

DAY = datetime(2026, 11, 6, tzinfo=KYIV)


def test_hourly_slots_merge_and_halves():
    slots = {str(i): "yes" for i in range(1, 25)}
    slots.update({"3": "no", "4": "no", "5": "second", "10": "first", "12": "maybe"})
    out = slots_to_intervals(slots, DAY)
    assert [(o["start"][11:16], o["end"][11:16], o["type"]) for o in out] == [
        ("02:00", "04:00", "definite"),
        ("04:30", "05:00", "definite"),  # ключ 5 -> година 04, друга половина
        ("09:00", "09:30", "definite"),
        ("11:00", "12:00", "possible"),
    ]


def test_half_hour_slots():
    slots = {str(i): "yes" for i in range(1, 49)}
    slots["1"] = "no"
    slots["2"] = "no"
    out = slots_to_intervals(slots, DAY)
    assert out[0]["start"][11:16] == "00:00" and out[0]["end"][11:16] == "01:00"


def test_houses_both_formats():
    d = {"data": {"1": {"sub_type_reason": ["GPV3.1"]}, "2": {"sub_type_reason": []}}}
    assert parse_houses(d) == {"1": ["GPV3.1"], "2": []}
    l = {"data": [{"num": "5", "sub_type_reason": ["GPV1.2"]}]}
    assert parse_houses(l) == {"5": ["GPV1.2"]}


def test_build_schedule():
    ts = int(DAY.timestamp())
    payload = {
        "data": {"1": {"sub_type_reason": ["GPV3.1"]}},
        "preset": {"sch_names": {"GPV3.1": "Черга 3.1"}},
        "fact": {"today": ts, "update": "06.11.2026 10:00",
                 "data": {str(ts): {"GPV3.1": {"1": "no", "2": "yes"}}}},
    }
    r = build_schedule(payload, "1", now=DAY)
    assert r["status"] == "ok" and r["group_name"] == "Черга 3.1"
    assert list(r["days"]) == ["2026-11-06"]
    assert build_schedule(payload, "9")["status"] == "house_not_found"


def test_emergency_parsed():
    ts = int(DAY.timestamp())
    payload = {
        "data": {"1": {"sub_type_reason": ["GPV3.1"], "sub_type": "Аварійні ремонтні роботи",
                       "start_date": "06.11.2026 10:15", "end_date": "06.11.2026 14:00", "type": "2"},
                 "2": {"sub_type_reason": ["GPV3.1"]}},
        "fact": {"today": ts, "data": {}},
    }
    e = build_schedule(payload, "1", now=DAY)["emergency"]
    assert e["active"] and e["reason"] == "Аварійні ремонтні роботи"
    assert e["start"].startswith("2026-11-06T10:15") and e["end"].startswith("2026-11-06T14:00")
    assert build_schedule(payload, "2", now=DAY)["emergency"]["active"] is False
