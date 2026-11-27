"""Fan platform for Gecko."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from geckolib import GeckoBlower, GeckoBubbleGenerator, GeckoPump, GeckoWaterfall
from homeassistant.components.fan import FanEntity, FanEntityFeature

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
    """Set up fan platform."""
    spaman = entry.runtime_data
    if (facade := spaman.facade) is not None:
        async_add_entities(
            GeckoFan(spaman, pump) for pump in [*facade.pumps, *facade.blowers]
        )


class GeckoFan(GeckoEntity, FanEntity):
    """GeckoFan class."""

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **_kwargs: Any,
    ) -> None:
        """Turn on the pump."""
        await self.pump.async_turn_on(percentage, preset_mode)

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the pump."""
        await self.pump.async_turn_off()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the pump."""
        await self.pump.async_turn_on(percentage, None)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the pump preset mode."""
        await self.pump.async_set_mode(preset_mode)

    @property
    def is_on(self) -> bool:
        """Get the pump on/off state."""
        return self.pump.is_on

    @property
    def supported_features(self) -> FanEntityFeature:
        """Get fan supported features."""
        features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if self.pump.pump_type == GeckoPump.PumpType.TWO_SPEED:
            features |= FanEntityFeature.PRESET_MODE
        if self.pump.pump_type == GeckoPump.PumpType.VARIABLE_SPEED:
            features |= FanEntityFeature.SET_SPEED
        return features

    @property
    def icon(self) -> str:
        """Return the icon of this pump."""
        if isinstance(self._automation_entity, GeckoBlower):
            return "mdi:fan"
        if isinstance(self._automation_entity, GeckoWaterfall):
            return "mdi:waterfall"
        if isinstance(self._automation_entity, GeckoBubbleGenerator):
            return "mdi:chart-bubble"
        return "mdi:pump"

    @property
    def preset_modes(self) -> list[str] | None:
        """Get preset modes."""
        return self.pump.modes

    @property
    def preset_mode(self) -> str | None:
        """Get current preset mode."""
        return self.pump.mode

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.pump.pump_type == GeckoPump.PumpType.VARIABLE_SPEED:
            return self.pump.percentage
        return None

    @property
    def pump(self) -> GeckoPump:
        """Get the pump."""
        return self._automation_entity
