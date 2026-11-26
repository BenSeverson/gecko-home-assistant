"""Switch platform for Gecko."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory

from .entity import GeckoEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .spa_manager import GeckoConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GeckoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch platform."""
    spaman = entry.runtime_data
    if (facade := spaman.facade) is None:
        return
    switches: list[GeckoBinarySwitch] = [
        GeckoBinarySwitch(spaman, switch, EntityCategory.CONFIG)
        for switch in (facade.eco_mode, facade.standby)
        if switch is not None
    ]
    if facade.mrsteam.is_available:
        switches.extend(
            GeckoBinarySwitch(spaman, switch) for switch in facade.mrsteam.switches
        )
    if facade.bainultra.is_available:
        switches.extend(
            GeckoBinarySwitch(spaman, switch) for switch in facade.bainultra.switches
        )
    async_add_entities(switches)


class GeckoBinarySwitch(GeckoEntity, SwitchEntity):
    """Gecko switch class."""

    _attr_icon = "mdi:toggle-switch"

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the switch."""
        await self._automation_entity.async_turn_on()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the switch."""
        await self._automation_entity.async_turn_off()

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self._automation_entity.is_on
