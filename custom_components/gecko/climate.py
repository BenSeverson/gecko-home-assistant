"""Climate platform for Gecko."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE

from .entity import GeckoEntity

if TYPE_CHECKING:
    from geckolib import GeckoWaterCare, GeckoWaterHeater
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .spa_manager import GeckoConfigEntry, GeckoSpaManager

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GeckoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up climate platform."""
    spaman = entry.runtime_data
    if (facade := spaman.facade) is not None and facade.water_heater.is_available:
        async_add_entities(
            [GeckoClimate(spaman, facade.water_heater, facade.water_care)]
        )


class GeckoClimate(GeckoEntity, ClimateEntity):
    """Gecko Climate class."""

    _attr_icon = "mdi:hot-tub"
    _attr_hvac_modes = [HVACMode.AUTO]  # noqa: RUF012
    _attr_hvac_mode = HVACMode.AUTO
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        spaman: GeckoSpaManager,
        automation_entity: GeckoWaterHeater,
        water_care: GeckoWaterCare,
    ) -> None:
        """Initialize Gecko climate entity."""
        super().__init__(spaman, automation_entity)
        self._water_care = water_care
        if self._water_care.is_available:
            self._observe(self._water_care)

    @property
    def available(self) -> bool:
        """Return whether the heater is available."""
        return self._automation_entity.is_available

    @property
    def hvac_action(self) -> HVACAction | None:
        """The current HVAC action."""
        # The geckolib operation names match HA's actions, but they are
        # proper cased, so we just move to lower ...
        try:
            return HVACAction(self._automation_entity.current_operation.lower())
        except ValueError:
            return None

    @property
    def preset_modes(self) -> list[str] | None:
        """List the water care modes."""
        return self._water_care.modes

    @property
    def preset_mode(self) -> str | None:
        """Get the current preset mode."""
        if self._water_care.mode is None:
            return None
        return self._water_care.modes[self._water_care.mode]

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode asynchronously."""
        await self._water_care.async_set_mode(preset_mode)

    @property
    def temperature_unit(self) -> str:
        """Get the current temperature unit."""
        return self._automation_entity.temperature_unit

    @property
    def current_temperature(self) -> float | None:
        """Get the current temperature."""
        return self._automation_entity.current_temperature

    @property
    def target_temperature(self) -> float | None:
        """Get the current target temperature."""
        return self._automation_entity.target_temperature

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

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Do nothing, the spa only has the one mode."""
