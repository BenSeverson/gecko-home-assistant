"""Water heater platform for Gecko."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE

from .entity import GeckoEntity

if TYPE_CHECKING:
    from geckolib import GeckoWaterHeaterAbstract
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .spa_manager import GeckoConfigEntry, GeckoSpaManager

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GeckoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up water heater platform."""
    spaman = entry.runtime_data
    if (facade := spaman.facade) is None:
        return
    # A facade with a Mr.Steam is a steam generator rather than a hot tub
    icon = "mdi:steam" if facade.mrsteam.is_available else "mdi:hot-tub"
    water_heaters: list[GeckoHAWaterHeater] = []
    if facade.water_heater.is_available:
        water_heaters.append(GeckoHAWaterHeater(spaman, facade.water_heater, icon))
    if facade.mrsteam.is_available:
        water_heaters.append(GeckoHAWaterHeater(spaman, facade.mrsteam, icon))
    async_add_entities(water_heaters)


class GeckoHAWaterHeater(GeckoEntity, WaterHeaterEntity):
    """Gecko Water Heater class."""

    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self,
        spaman: GeckoSpaManager,
        automation_entity: GeckoWaterHeaterAbstract,
        icon: str,
    ) -> None:
        """Initialize Gecko water heater entity."""
        super().__init__(spaman, automation_entity)
        self._attr_icon = icon

    @property
    def available(self) -> bool:
        """Return whether the heater is available."""
        return self._automation_entity.is_available

    @property
    def current_operation(self) -> str | None:
        """The current operation."""
        return self._automation_entity.current_operation

    @property
    def native_temperature_unit(self) -> str:
        """Get the current temperature unit."""
        return self._automation_entity.temperature_unit

    @property
    def native_current_temperature(self) -> float | None:
        """Get the current temperature."""
        return self._automation_entity.current_temperature

    @property
    def native_target_temperature(self) -> float | None:
        """Get the current target temperature."""
        return self._automation_entity.target_temperature

    # Home Assistant 2026.11 renamed these to the native_ names above and drops
    # the old ones in 2027.11. Older releases only read the old names.
    temperature_unit = native_temperature_unit
    current_temperature = native_current_temperature
    target_temperature = native_target_temperature

    @property
    def min_temp(self) -> float:
        """Get the minimum temperature."""
        return self._automation_entity.min_temp

    @property
    def max_temp(self) -> float:
        """Get the maximum temperature."""
        return self._automation_entity.max_temp

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature asynchronously."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self._automation_entity.async_set_target_temperature(temperature)
