"""Tests for the Gecko diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geckolib import GeckoSpaEvent
from homeassistant.components.diagnostics import REDACTED

from custom_components.gecko.const import (
    CONF_CLIENT_ID,
    CONF_SPA_IDENTIFIER,
    CONF_SPA_NAME,
)
from custom_components.gecko.diagnostics import async_get_config_entry_diagnostics

from .conftest import SPA_NAME, make_facade, send_event, setup_entry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_diagnostics(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Diagnostics hold the snapshot, and no identifying data."""
    spaman = await setup_entry(hass, config_entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["snapshot"] is None
    assert diagnostics["entry"]["data"][CONF_SPA_NAME] == SPA_NAME
    assert diagnostics["entry"]["data"][CONF_SPA_IDENTIFIER] == REDACTED
    assert diagnostics["entry"]["data"][CONF_CLIENT_ID] == REDACTED

    spaman._facade = make_facade()
    await send_event(hass, spaman, GeckoSpaEvent.CLIENT_FACADE_IS_READY)

    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["can_use_facade"]
    assert diagnostics["snapshot"] == {"Spa pack": "inYT 1 v2.0"}
