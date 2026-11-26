"""Diagnostics support for Gecko."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from geckolib import VERSION as GECKOLIB_VERSION
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.loader import async_get_loaded_integration

from .const import CONF_CLIENT_ID, CONF_SPA_ADDRESS, CONF_SPA_IDENTIFIER, DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .spa_manager import GeckoConfigEntry

TO_REDACT = {CONF_CLIENT_ID, CONF_SPA_ADDRESS, CONF_SPA_IDENTIFIER}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GeckoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    spaman = entry.runtime_data
    facade = spaman.facade
    return {
        "integration_version": str(async_get_loaded_integration(hass, DOMAIN).version),
        "geckolib_version": GECKOLIB_VERSION,
        "entry": {
            "version": f"{entry.version}.{entry.minor_version}",
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "spa_state": str(spaman.spa_state),
        "can_use_facade": spaman.can_use_facade,
        "platforms": [str(platform) for platform in spaman.platforms],
        # This is the same data that the Snapshot button reports
        "snapshot": facade.spa.get_snapshot_data() if facade is not None else None,
    }
