"""GeckoEntity class."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from geckolib import GeckoAutomationBase, GeckoReminderType, Observable
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from homeassistant.const import EntityCategory

    from .spa_manager import GeckoSpaManager

_REMINDER_NAMES: dict[GeckoReminderType, str] = {
    GeckoReminderType.RINSE_FILTER: "Rinse filter",
    GeckoReminderType.CLEAN_FILTER: "Clean filter",
    GeckoReminderType.CHANGE_WATER: "Change water",
    GeckoReminderType.CHECK_SPA: "Check Spa",
    GeckoReminderType.CHANGE_OZONATOR: "Change Ozonator",
    GeckoReminderType.CHANGE_VISION_CARTRIDGE: "Change Vision cartridge",
}


def reminder_name(reminder_type: GeckoReminderType) -> str:
    """Get the display name for a reminder type."""
    return _REMINDER_NAMES.get(reminder_type, "Unknown")


class GeckoEntityBase(Entity):
    """Base for all Gecko entities."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        spaman: GeckoSpaManager,
        unique_id: str,
        name: str,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize the entity class."""
        self.spaman = spaman
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_entity_category = entity_category
        self._observables: list[Observable] = []

    def _observe(self, observable: Any) -> None:
        """Register something to watch for the time this entity is in HA."""
        if isinstance(observable, Observable) and observable not in self._observables:
            self._observables.append(observable)

    async def async_added_to_hass(self) -> None:
        """Start watching for changes once HA knows about the entity."""
        await super().async_added_to_hass()
        for observable in self._observables:
            observable.watch(self._on_change)

    async def async_will_remove_from_hass(self) -> None:
        """Stop watching for changes."""
        for observable in self._observables:
            # geckolib drops all observers itself when it tears the facade
            # down, so ours may already have gone
            with contextlib.suppress(ValueError):
                observable.unwatch(self._on_change)
        await super().async_will_remove_from_hass()

    def _on_change(self, _sender: Any, _old_value: Any, _new_value: Any) -> None:
        """Notify HA of the change."""
        if self.hass is not None:
            self.async_schedule_update_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Get device information."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self.spaman.unique_id)},
            name=self.spaman.spa_name,
            manufacturer=MANUFACTURER,
        )
        if (facade := self.spaman.facade) is not None:
            spa = facade.spa
            info["model"] = f"{spa.pack} {spa.version}"
            info["sw_version"] = (
                f"SpaPack:v{spa.revision} "
                f"Config:{spa.config_version} "
                f"Log:{spa.log_version}"
            )
            info["hw_version"] = (
                f"EN:{spa.intouch_version_en} CO:{spa.intouch_version_co}"
            )
        return info


class GeckoEntity(GeckoEntityBase):
    """Entity base of Gecko items."""

    def __init__(
        self,
        spaman: GeckoSpaManager,
        automation_entity: GeckoAutomationBase,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Initialize a gecko entity."""
        super().__init__(
            spaman,
            automation_entity.unique_id,
            automation_entity.name,
            entity_category,
        )
        self._automation_entity: Any = automation_entity
        self._observe(automation_entity)
