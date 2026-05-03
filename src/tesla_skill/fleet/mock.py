"""In-memory mock Tesla client — used when USE_MOCK=true.

Simulates a generic Model Y. Keeps minimal state so control tools actually
*change* something and read tools reflect it. Useful for:
    - Developing without a real Tesla / before completing OAuth setup
    - Demoing the agent integration end-to-end
    - Smoke-testing tool wiring after code changes
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class MockFleetClient:
    def __init__(self) -> None:
        # Plausible Model Y standard-range values
        self._battery_pct: int = 78
        self._full_range_km: int = 525
        self._charge_limit: int = 90
        self._charging: bool = False
        self._climate_on: bool = False
        self._target_temp_c: float = 22.0
        self._inside_temp_c: float = 19.0
        self._locked: bool = True
        self._sentry: bool = False
        # Generic mock location (downtown San Francisco)
        self._lat: float = 37.7749
        self._lng: float = -122.4194
        self._address: str = "Mock location (San Francisco)"

    @property
    def _range_km(self) -> int:
        return int(self._full_range_km * self._battery_pct / 100)

    # ---------- Read ----------
    def get_status(self) -> dict:
        return {
            "battery_percent": self._battery_pct,
            "range_km": self._range_km,
            "climate_on": self._climate_on,
            "inside_temp_c": round(self._inside_temp_c, 1),
            "target_temp_c": self._target_temp_c,
            "locked": self._locked,
            "sentry_on": self._sentry,
            "is_online": True,
            "model": "Model Y (mock)",
        }

    def get_location(self) -> dict:
        return {
            "lat": self._lat,
            "lng": self._lng,
            "address": self._address,
            "speed_kmh": 0,
            "heading": 0,
        }

    def get_charge_info(self) -> dict:
        kwh_total = 60
        kw_charging = 7 if self._charging else 0
        remaining_kwh = kwh_total * (self._charge_limit - self._battery_pct) / 100
        time_to_full_min = (
            int(remaining_kwh / kw_charging * 60) if self._charging and remaining_kwh > 0 else None
        )
        return {
            "charging": self._charging,
            "soc_percent": self._battery_pct,
            "limit_percent": self._charge_limit,
            "charging_power_kw": kw_charging,
            "time_to_full_min": time_to_full_min,
        }

    # ---------- Climate ----------
    def set_climate(self, on: bool, temp_c: float | None = None) -> dict:
        self._climate_on = on
        if temp_c is not None:
            self._target_temp_c = float(temp_c)
        if on:
            # simulate inside temp drifting toward target
            self._inside_temp_c += (self._target_temp_c - self._inside_temp_c) * 0.3
        return {"climate_on": self._climate_on, "target_temp_c": self._target_temp_c}

    # ---------- Lock ----------
    def lock(self) -> dict:
        self._locked = True
        return {"locked": True}

    def unlock(self) -> dict:
        self._locked = False
        return {"locked": False}

    # ---------- Charging ----------
    def start_charging(self) -> dict:
        if self._battery_pct >= self._charge_limit:
            return {"charging": False, "reason": "already at charge limit"}
        self._charging = True
        return {"charging": True}

    def stop_charging(self) -> dict:
        self._charging = False
        return {"charging": False}

    # ---------- Signals ----------
    def flash_lights(self) -> dict:
        log.info("mock: flash lights")
        return {"ok": True}

    def honk_horn(self) -> dict:
        log.info("mock: honk horn")
        return {"ok": True}
