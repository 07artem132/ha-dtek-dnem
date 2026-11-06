# Світло / EcoFlow / ДТЕК → Signal

Автоматизації Home Assistant для дому з EcoFlow Delta 2 Max і інтеграцією `dtek_dnem` з цього репо.
Усі повідомлення йдуть у Signal через `notify.send_message` на entity `notify.rozumnii_dim`
(інтеграція [ha-signal-wsrpc](https://github.com/07artem132/ha-signal-wsrpc)).

| id | Коли | Що пише |
|---|---|---|
| `ecoflow_outage_start` | напруга AC-входу EcoFlow < 100 V протягом 1 хв | світло зникло, заряд, на скільки вистачить, чи вистачить до кінця відключення за ДТЕК |
| `ecoflow_outage_low_soc` | під час відключення заряд < 30% / < 15% | оновлений прогноз |
| `ecoflow_outage_monitor` | кожні 2 хв під час відключення | «вже НЕ вистачить» / «знову вистачає» (один раз на зміну, гістерезис 15 хв) |
| `ecoflow_power_restored` | напруга > 180 V протягом 3 хв (лише після зафіксованого «зникло») | скільки не було, швидкість заряду, чи встигне до 100% до наступного відключення і яку потужність заряду поставити; план на 48 год, якщо є проблема |
| `dtek_schedule_updated_signal` | подія `dtek_dnem_schedule_updated` | графік по днях + план EcoFlow на 48 год |
| `dtek_emergency_signal` | подія `dtek_dnem_emergency` | аварійне відключення: причина, час, чи вистачить EcoFlow |
| `ecoflow_profile_update` | щогодини | оновлює погодинний профіль навантаження (EMA 10%, обрізання ±50%) |

## Модель

- **Світло є/нема**: `sensor.delta_2_max_ac_in_volts` (мережа 200–230 V, без неї 0–35 V). Вхідна потужність не годиться: при повній батареї вона ≈ 0.
- **Енергія**: `(main_remain_capacity − full_capacity × min_discharge%) × battery_volts`. Вбудований `discharge_remaining_time` EcoFlow не використовується: на історії помилявся до +60%.
- **Витрата** = навантаження × 1.10 (втрати інвертора; відкалібровано на трьох відключеннях 3–6.11.2026: реальна витрата 1.06–1.12 × `total_out_power`).
  - поточне відключення: на кожну годину `max(середнє за 10 хв, профіль години)`;
  - план на майбутні відключення: профіль години.
- **Профіль годин** (`input_text.ecoflow_profil_navantazhennia`, 24 значення W через кому, Київ 0..23): засіяно медіаною годинних середніх `total_out_power` з recorder за 30 днів. Медіана влучала в реальне споживання під час відключень у межах ~5%, середнє завищувало вечір на 20–25%.
- **Заряд**: `number.delta_2_max_ac_charging_power` (200–2400 W, крок 100); реальний заряд ≈ 0.98 × налаштування.
- **Захист від збоїв EcoFlow Cloud**: при перепідключенні ~3 хв віддає `unknown`/0 (напр. `battery_volts` 0.003 V). Старт/відновлення вимагають `sensor.delta_2_max_status == online` і 40 < `battery_volts` < 60; нереальні ємність/напруга замінюються номіналом.
- **ДТЕК** знаходиться без хардкоду entity_id: `integration_entities('dtek_dnem')` → календар, аварійний `binary_sensor` (device_class `problem`), сенсор з атрибутом `outage_now`, timestamp-сенсори. Без інтеграції все працює, просто без графіка.

## Хелпери (створюються один раз, UI або `ws.ps1`)

| entity | тип | налаштування |
|---|---|---|
| `sensor.ecoflow_navantazhennia_10_khv` | statistics | `total_out_power`, average_step, 10 хв |
| `sensor.ecoflow_navantazhennia_24_god` | statistics | `total_out_power`, average_step, 24 год |
| `sensor.komora_delta_2_max_ecoflow_navantazhennia_1_god` | statistics | `total_out_power`, average_step, 1 год |
| `sensor.ecoflow_navantazhennia_bez_svitla` | template | `total_out_power`, коли напруга AC < 100 V, інакше `this.state` |
| `sensor.ecoflow_serednie_navantazhennia_bez_svitla` | statistics | попередній, average_timeless, 72 год |
| `input_boolean.ecoflow_ne_vistachit_do_kintsia_vidkliuchennia` | input_boolean | стан «вже попередили» для моніторингу |
| `input_text.ecoflow_profil_navantazhennia` | input_text, max 255 | профіль годин |

## Деплой (Windows PowerShell, з LAN)

```powershell
# ha-token.txt поруч зі скриптами: long-lived token HA (у git не потрапляє)
$env:HA_URL = 'http://192.168.0.231:8123'
python build.py                 # automations.yaml → automations.json
powershell -ExecutionPolicy Bypass -File deploy.ps1
```

`deploy.ps1` пише кожну автоматизацію через `POST /api/config/automation/config/<id>` (HA сам перезавантажує).

## Перевірка без побічних ефектів

```powershell
python test/gen.py              # сценарії → test/cases.json
powershell -ExecutionPolicy Bypass -File test/run.ps1   # рендерить усі тексти через /api/template
```
