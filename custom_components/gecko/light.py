"""Light platform for Gecko."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ColorMode, LightEntity

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
    """Set up light platform."""
    spaman = entry.runtime_data
    if (facade := spaman.facade) is None:
        return
    lights: list[LightEntity] = [GeckoLight(spaman, light) for light in facade.lights]
    if facade.inmix.is_available:
        lights.extend(GeckoZone(spaman, zone) for zone in facade.inmix.zones)
    async_add_entities(lights)


class GeckoLight(GeckoEntity, LightEntity):
    """Gecko light class."""

    _attr_icon = "mdi:lightbulb"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}  # noqa: RUF012

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn on the light."""
        await self._automation_entity.async_turn_on()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the light."""
        await self._automation_entity.async_turn_off()

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._automation_entity.is_on


class GeckoZone(GeckoEntity, LightEntity):
    """Gecko inMix zone class."""

    _attr_icon = "mdi:lightbulb"
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}  # noqa: RUF012

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the zone."""
        await self._automation_entity.async_turn_on(**kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the zone."""
        await self._automation_entity.async_turn_off(**kwargs)

    @property
    def is_on(self) -> bool:
        """Return true if the zone is on."""
        return self._automation_entity.is_on

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Get the rgb colour."""
        return self._automation_entity.rgb_color

    @property
    def brightness(self) -> int | None:
        """Get the brightness."""
        return self._automation_entity.brightness
