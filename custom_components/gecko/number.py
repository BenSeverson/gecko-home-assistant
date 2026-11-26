"""Number platform for Gecko."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up number platform."""
    spaman = entry.runtime_data
    if not spaman.can_use_facade or (facade := spaman.facade) is None:
        return
    numbers: list[GeckoNumber] = []
    if facade.mrsteam.is_available:
        numbers.append(GeckoNumber(spaman, facade.mrsteam.user_runtime))
    if facade.bainultra.is_available:
        bain = facade.bainultra
        numbers.append(GeckoNumber(spaman, bain.bath_runtime))
        numbers.append(GeckoNumber(spaman, bain.bath_intensity))
        numbers.extend(
            GeckoNumber(spaman, number, EntityCategory.CONFIG)
            for number in (
                bain.drying_cycle_delay,
                bain.drying_cycle_hour,
                bain.drying_cycle_minute,
            )
        )
    async_add_entities(numbers)


class GeckoNumber(GeckoEntity, NumberEntity):
    """Gecko Number class."""

    @property
    def native_value(self) -> float | None:
        """Return the native value of the number."""
        return self._automation_entity.native_value

    @property
    def native_min_value(self) -> float:
        """Get the min value."""
        return self._automation_entity.native_min_value

    @property
    def native_max_value(self) -> float:
        """Get the max value."""
        return self._automation_entity.native_max_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the number entity."""
        await self._automation_entity.async_set_native_value(value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._automation_entity.native_unit_of_measurement

    @property
    def native_step(self) -> float | None:
        """Return the step size."""
        return self._automation_entity.native_step

    @property
    def mode(self) -> NumberMode:
        """Return the preferred entry mode."""
        try:
            return NumberMode(self._automation_entity.mode)
        except ValueError:
            return NumberMode.AUTO
