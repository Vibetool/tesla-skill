"""Real Tesla Fleet API client.

Read methods (get_status / get_location / get_charge_info) hit
/api/1/vehicles/{id}/vehicle_data and need only OAuth.

Control methods (set_climate / lock / unlock / charging / lights / horn)
shell out to tesla-control via TeslaControl wrapper, which signs the
command with the user's Virtual Key.

Rate limits to mind:
    - /vehicle_data: ~200 calls/car/day. We cache 30s so a burst of read
      tools share one API call.
    - /wake_up: counts separately + drains battery. Read tools don't wake;
      they return is_online=false if asleep.
"""
from __future__ import annotations

import logging
import time

import httpx

from tesla_skill.auth import oauth
from tesla_skill.config import settings
from tesla_skill.fleet.signer import SignerResult, TeslaControl

log = logging.getLogger(__name__)

# Tesla API returns ranges in miles regardless of user locale.
MI_TO_KM = 1.609344

# Endpoints joined with literal ";" — Tesla's API requires literal semicolons,
# not URL-encoded %3B (httpx's params=dict would encode them, hence why we
# build the query string manually).
_VD_ENDPOINTS = "charge_state;climate_state;drive_state;vehicle_state;location_data"


class RealFleetClient:
    def __init__(self) -> None:
        self._vehicle_id: str | None = None
        self._vin: str | None = None
        self._cached_vd: dict | None = None
        self._cached_at: float = 0.0
        self._cache_ttl_sec: int = 30

    # ---------- internals ----------
    def _client(self) -> httpx.Client:
        token = oauth.get_valid_access_token()
        return httpx.Client(
            base_url=settings.tesla_fleet_api_base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )

    def _ensure_vehicle(self) -> tuple[str, str]:
        if self._vehicle_id and self._vin:
            return self._vehicle_id, self._vin
        with self._client() as c:
            r = c.get("/api/1/vehicles")
            r.raise_for_status()
            vehicles = r.json().get("response") or []
        if not vehicles:
            raise RuntimeError("No vehicles found on this Tesla account")
        v = vehicles[0]  # single-car personal use; pick first
        self._vehicle_id = str(v["id"])
        self._vin = v.get("vin", "")
        log.info(
            "Using vehicle id=%s vin=%s (display_name=%s)",
            self._vehicle_id, self._vin, v.get("display_name"),
        )
        return self._vehicle_id, self._vin

    def _vehicle_data(self) -> dict:
        """Fetch combined vehicle_data, with 30s cache and offline handling."""
        if self._cached_vd is not None and (time.time() - self._cached_at) < self._cache_ttl_sec:
            return self._cached_vd
        vid, _ = self._ensure_vehicle()
        with self._client() as c:
            # Build URL manually so ";" stays literal.
            r = c.get(f"/api/1/vehicles/{vid}/vehicle_data?endpoints={_VD_ENDPOINTS}")
        if r.status_code in (408, 503):
            log.info("vehicle_data: car is offline/asleep (%s)", r.status_code)
            data = {"_offline": True}
            self._cached_vd = data
            self._cached_at = time.time()
            return data
        if r.status_code == 403:
            log.warning("vehicle_data: 403 Forbidden — Virtual Key not paired with vehicle")
            return {"_unpaired": True}
        r.raise_for_status()
        data = r.json().get("response") or {}
        self._cached_vd = data
        self._cached_at = time.time()
        return data

    # ---------- Read tools ----------
    def get_status(self) -> dict:
        d = self._vehicle_data()
        if d.get("_unpaired"):
            return {
                "is_online": False,
                "reason": "Virtual Key not paired with vehicle. Open https://tesla.com/_ak/<your-domain> on your phone to pair.",
            }
        if d.get("_offline"):
            return {"is_online": False, "reason": "Vehicle is asleep; control commands will auto-wake it"}
        cs = d.get("charge_state") or {}
        cl = d.get("climate_state") or {}
        vs = d.get("vehicle_state") or {}
        return {
            "battery_percent": cs.get("battery_level"),
            "range_km": round((cs.get("battery_range") or 0) * MI_TO_KM),
            "climate_on": bool(cl.get("is_climate_on")),
            "inside_temp_c": cl.get("inside_temp"),
            "target_temp_c": cl.get("driver_temp_setting"),
            "locked": bool(vs.get("locked", True)),
            "sentry_on": bool(vs.get("sentry_mode")),
            "is_online": True,
            "model": (vs.get("car_version") or "Tesla").split(" ")[0][:20],
        }

    def get_location(self) -> dict:
        d = self._vehicle_data()
        if d.get("_unpaired"):
            return {"is_online": False, "reason": "Virtual Key not paired"}
        if d.get("_offline"):
            return {"is_online": False, "reason": "Vehicle asleep"}
        ds = d.get("drive_state") or {}
        speed_mph = ds.get("speed")
        return {
            "lat": ds.get("latitude"),
            "lng": ds.get("longitude"),
            "heading": ds.get("heading"),
            "speed_kmh": round(speed_mph * MI_TO_KM) if speed_mph is not None else 0,
            "shift_state": ds.get("shift_state") or "P",
        }

    def get_charge_info(self) -> dict:
        d = self._vehicle_data()
        if d.get("_unpaired"):
            return {"is_online": False, "reason": "Virtual Key not paired"}
        if d.get("_offline"):
            return {"is_online": False, "reason": "Vehicle asleep"}
        cs = d.get("charge_state") or {}
        return {
            "charging": cs.get("charging_state") == "Charging",
            "soc_percent": cs.get("battery_level"),
            "limit_percent": cs.get("charge_limit_soc"),
            "charging_power_kw": cs.get("charger_power"),
            "time_to_full_min": int((cs.get("time_to_full_charge") or 0) * 60) or None,
        }

    # ---------- Control tools (TVCP signed via tesla-control) ----------
    def _tc(self) -> TeslaControl:
        _, vin = self._ensure_vehicle()
        return TeslaControl(vin)

    @staticmethod
    def _result(ok: bool, signer: SignerResult, **extra) -> dict:
        if ok:
            return {"ok": True, **extra}
        return {"ok": False, "reason": signer.friendly_reason, **extra}

    def set_climate(self, on: bool, temp_c: float | None = None) -> dict:
        tc = self._tc()
        cmd = "climate-on" if on else "climate-off"
        r = tc.wake_and_retry(cmd)
        if not r.ok:
            return self._result(False, r)

        if on and temp_c is not None:
            r2 = tc.run("climate-set-temp", f"{float(temp_c):.1f}", f"{float(temp_c):.1f}")
            if not r2.ok:
                return {"ok": True, "climate_on": True, "warning": f"target temp not set: {r2.friendly_reason}"}
            self._cached_vd = None
            return {"ok": True, "climate_on": True, "target_temp_c": temp_c}

        self._cached_vd = None
        return {"ok": True, "climate_on": on}

    def lock(self) -> dict:
        r = self._tc().wake_and_retry("lock")
        self._cached_vd = None
        return self._result(r.ok, r, locked=True) if r.ok else self._result(False, r)

    def unlock(self) -> dict:
        r = self._tc().wake_and_retry("unlock")
        self._cached_vd = None
        return self._result(r.ok, r, locked=False) if r.ok else self._result(False, r)

    def start_charging(self) -> dict:
        r = self._tc().wake_and_retry("charging-start")
        self._cached_vd = None
        return self._result(r.ok, r, charging=True) if r.ok else self._result(False, r)

    def stop_charging(self) -> dict:
        r = self._tc().wake_and_retry("charging-stop")
        self._cached_vd = None
        return self._result(r.ok, r, charging=False) if r.ok else self._result(False, r)

    def flash_lights(self) -> dict:
        r = self._tc().wake_and_retry("flash-lights")
        return self._result(r.ok, r) if r.ok else self._result(False, r)

    def honk_horn(self) -> dict:
        r = self._tc().wake_and_retry("honk")
        return self._result(r.ok, r) if r.ok else self._result(False, r)
