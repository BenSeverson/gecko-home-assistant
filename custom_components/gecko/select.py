"""Select platform for Gecko."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from .entity import GeckoEntity

if TYPE_CHECKING:
    from geckolib import GeckoAutomationBase
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .spa_manager import GeckoConfigEntry, GeckoSpaManager

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GeckoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select platform."""
    spaman = entry.runtime_data
    # facade can be None while can_use_facade is still True: async_reset nulls
    # it immediately but the teardown event is processed asynchronously
    if not spaman.can_use_facade or (facade := spaman.facade) is None:
        return
    config = EntityCategory.CONFIG
    selects: list[GeckoSelect] = []
    if facade.heatpump.is_available:
        selects.append(
            GeckoSelect(spaman, facade.heatpump, config, "mdi:heat-pump-outline")
        )
    if facade.ingrid.is_available:
        selects.append(GeckoSelect(spaman, facade.ingrid, config, "mdi:heat-wave"))
    if facade.lockmode.is_available:
        selects.append(GeckoLockMode(spaman, facade.lockmode, config))
    if facade.keypad.backlight.is_available:
        selects.append(
            GeckoSelect(
                spaman, facade.keypad.backlight, config, "mdi:alarm-panel-outline"
            )
        )
    if facade.inmix.is_available and facade.inmix.syncro.is_available:
        selects.append(
            GeckoSelect(spaman, facade.inmix.syncro, None, "mdi:alarm-panel-outline")
        )
    if facade.water_care.is_available:
        selects.append(
            GeckoSelect(spaman, facade.water_care, config, "mdi:water-check")
        )
    if facade.bainultra.is_available:
        bain = facade.bainultra
        selects.extend(
            GeckoSelect(spaman, select, None, "mdi:heat-wave")
            for select in bain.selects
        )
        if bain.chroma.is_available:
            selects.append(GeckoSelect(spaman, bain.chroma, None, "mdi:looks"))
        selects.append(GeckoSelect(spaman, bain.drying_cycle, config))

    async_add_entities(selects)


class GeckoSelect(GeckoEntity, SelectEntity):
    """Gecko select class."""

    def __init__(
        self,
        spaman: GeckoSpaManager,
        select: GeckoAutomationBase,
        entity_category: EntityCategory | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize the select."""
        super().__init__(spaman, select, entity_category)
        self._attr_icon = icon
        _LOGGER.debug("%r loaded. Options are %s", select, self.options)

    @property
    def current_option(self) -> str | None:
        """Get the current option."""
        return self._automation_entity.state

    @property
    def options(self) -> list[str]:
        """Get the option list."""
        return self._automation_entity.states

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self._automation_entity.async_set_state(option)


class GeckoLockMode(GeckoSelect):
    """Lockmode class."""

    @property
    def icon(self) -> str:
        """Get the icon for the lock."""
        option = self.current_option or ""
        if option == "Unlocked":
            return "mdi:lock-open-variant-outline"
        if option.startswith("Partial"):
            return "mdi:lock-minus-outline"
        return "mdi:lock-outline"
