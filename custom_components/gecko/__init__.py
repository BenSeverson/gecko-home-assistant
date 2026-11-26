"""
Custom integration to integrate Gecko Alliance spa with Home Assistant.

For more details about this integration, please refer to
https://github.com/gazoodle/gecko-home-assistant
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from geckolib import VERSION as GECKOLIB_VERSION

from .const import (
    CONF_CLIENT_ID,
    CONF_SPA_ADDRESS,
    CONF_SPA_IDENTIFIER,
    CONF_SPA_NAME,
    DOMAIN,
)
from .spa_manager import GeckoConfigEntry, GeckoSpaManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Config entry version history
# 1.1 Initial version
# 2.1 Added a per-entry client id
# 2.2 Added the spa identifier as the config entry unique id
_ENTRY_VERSION = 2
_ENTRY_MINOR_VERSION = 2


async def async_migrate_entry(hass: HomeAssistant, entry: GeckoConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version > _ENTRY_VERSION:
        # Downgraded from a future version that we know nothing about
        return False

    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_CLIENT_ID: f"{uuid.uuid4()}"},
            version=2,
            minor_version=1,
        )

    if entry.version == _ENTRY_VERSION and entry.minor_version < _ENTRY_MINOR_VERSION:
        updates: dict[str, Any] = {}
        spa_identifier = entry.data.get(CONF_SPA_IDENTIFIER)
        if (
            entry.unique_id is None
            and spa_identifier
            and hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, spa_identifier
            )
            is None
        ):
            updates["unique_id"] = spa_identifier
        hass.config_entries.async_update_entry(
            entry, minor_version=_ENTRY_MINOR_VERSION, **updates
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful", entry.version, entry.minor_version
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: GeckoConfigEntry) -> bool:
    """Set up this integration using UI."""
    spa_identifier = entry.data.get(CONF_SPA_IDENTIFIER)
    spa_address = entry.data.get(CONF_SPA_ADDRESS)
    spa_name = entry.data.get(CONF_SPA_NAME)
    client_id = entry.data[CONF_CLIENT_ID]

    _LOGGER.debug(
        "Setup entry for UUID %s, ID %s, address %s (%s) using geckolib %s",
        client_id,
        spa_identifier,
        spa_address,
        spa_name,
        GECKOLIB_VERSION,
    )

    # The spa manager connects in the background and adds the platforms that
    # are appropriate to the connection state as it changes
    spaman = GeckoSpaManager(
        client_id,
        hass,
        entry,
        spa_identifier=spa_identifier,
        spa_address=spa_address,
        spa_name=spa_name,
    )
    await spaman.__aenter__()
    entry.runtime_data = spaman

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(_hass: HomeAssistant, entry: GeckoConfigEntry) -> bool:
    """Handle removal of an entry."""
    spaman = entry.runtime_data
    # Stop reacting to spa events first, so that the teardown below can't
    # queue a platform reload on an entry that is on its way out
    spaman.stop_event_processing()
    if not await spaman.unload_platforms():
        spaman.start_event_processing()
        return False

    _LOGGER.debug("Close SpaMan")
    await spaman.async_reset()
    await spaman.__aexit__(None, None, None)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: GeckoConfigEntry) -> None:
    """Reload the config entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
