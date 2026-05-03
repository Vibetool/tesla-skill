"""tesla-skill MCP Server — entry point.

Transport: stdio. This is the canonical MCP transport for local agents
(Claude Desktop, Cursor, Continue, Codex, Claude Code, etc.). The agent
spawns this process as a subprocess and exchanges JSON-RPC over stdin/stdout.

Tool design notes:
    - All docstrings are in English so any-locale LLM can route correctly.
    - Tool outputs are language-neutral structured JSON.
    - Stay under 1KB return values (some agents have payload limits).
    - stdout is reserved for JSON-RPC; logs go to stderr (logger).
"""
from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from tesla_skill.fleet import get_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("tesla_skill")

mcp = FastMCP("tesla-skill")
fleet = get_client()


# ============================================================================
# Read tools
# ============================================================================

@mcp.tool()
def get_car_status() -> dict:
    """Get a snapshot of the Tesla's current state.

    Returns battery percent, remaining range (km), climate on/off, inside
    temperature, lock status, sentry mode, and online status.

    Use when the user asks about overall vehicle state, battery level,
    whether the car is locked, range remaining, or if it's online.
    """
    log.info("tool: get_car_status")
    return fleet.get_status()


@mcp.tool()
def get_car_location() -> dict:
    """Get the Tesla's current geographic location.

    Returns lat/lng (WGS84), heading (degrees), speed (km/h), and shift state.

    Use when the user asks where their car is, whether it's moving, or
    its current speed/direction.
    """
    log.info("tool: get_car_location")
    return fleet.get_location()


@mcp.tool()
def get_charge_info() -> dict:
    """Get charging state and progress.

    Returns whether the car is currently charging, current state-of-charge
    percent, the configured charge limit percent, current charging power
    in kW, and minutes remaining to reach the limit.

    Use when the user asks about charging status, time to full, or
    current charge level relative to the limit.
    """
    log.info("tool: get_charge_info")
    return fleet.get_charge_info()


# ============================================================================
# Climate
# ============================================================================

@mcp.tool()
def set_climate(on: bool, temp_c: float | None = None) -> dict:
    """Turn climate control on or off and optionally set target temperature.

    Args:
        on: True to start climate (HVAC), False to stop.
        temp_c: Optional target temperature in Celsius (16-28). Applies to
            both driver and passenger. Only meaningful when on=True.

    Use when the user says things like "turn on AC", "set climate to 22",
    "preheat the car", "stop climate", "cool down the car".
    """
    log.info("tool: set_climate on=%s temp_c=%s", on, temp_c)
    return fleet.set_climate(on=on, temp_c=temp_c)


# ============================================================================
# Lock / Unlock
# ============================================================================

@mcp.tool()
def lock_car() -> dict:
    """Lock all doors. Use when the user says "lock the car"."""
    log.info("tool: lock_car")
    return fleet.lock()


@mcp.tool()
def unlock_car() -> dict:
    """Unlock all doors.

    SAFETY: This makes the car physically openable by anyone nearby.
    Confirm with the user before calling unless they explicitly asked.

    Use when the user says "unlock", "open the car", "let me in".
    """
    log.info("tool: unlock_car")
    return fleet.unlock()


# ============================================================================
# Charging
# ============================================================================

@mcp.tool()
def start_charging() -> dict:
    """Start charging. Requires the charge cable to be plugged in.

    Use when the user says "start charging" or "charge now".
    """
    log.info("tool: start_charging")
    return fleet.start_charging()


@mcp.tool()
def stop_charging() -> dict:
    """Stop the current charging session.

    Use when the user says "stop charging" or "pause charging".
    """
    log.info("tool: stop_charging")
    return fleet.stop_charging()


# ============================================================================
# Find-my-car signals
# ============================================================================

@mcp.tool()
def flash_lights() -> dict:
    """Flash the headlights once. Useful for finding the car in a parking lot.

    Use when the user says "flash the lights" or "find my car".
    """
    log.info("tool: flash_lights")
    return fleet.flash_lights()


@mcp.tool()
def honk_horn() -> dict:
    """Honk the horn briefly. Useful for finding the car or alerting someone.

    Note: This is loud — avoid in residential areas at night. Use when
    the user says "honk", "beep the horn", "press the horn".
    """
    log.info("tool: honk_horn")
    return fleet.honk_horn()


def main() -> None:
    log.info("tesla-skill MCP starting (transport=stdio, mock=%s)", fleet.__class__.__name__ == "MockFleetClient")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
