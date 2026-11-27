"""Date platform for Gecko."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from geckolib import GeckoReminderType
from homeassistant.components.date import DateEntity
from homeassistant.const import EntityCategory
from homeassistant.util import dt as dt_util

from .entity import GeckoEntityBase, reminder_name

if TYPE_CHECKING:
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
    """Set up date platform."""
    spaman = entry.runtime_data
    if (
        spaman.can_use_facade
        and (facade := spaman.facade) is not None
        and facade.reminders_manager.is_available
    ):
        async_add_entities(
            GeckoReminderDate(spaman, reminder.reminder_type)
            for reminder in facade.reminders_manager.reminders
        )


class GeckoReminderDate(GeckoEntityBase, DateEntity):
    """Gecko reminder date class."""

    _attr_icon = "mdi:reminder"

    def __init__(
        self, spaman: GeckoSpaManager, reminder_type: GeckoReminderType
    ) -> None:
        """Initialize the reminder date."""
        super().__init__(
            spaman,
            f"{spaman.unique_id}-{GeckoReminderType.to_string(reminder_type)}",
            f"{reminder_name(reminder_type)} due",
            EntityCategory.CONFIG,
        )
        self._reminder_type = reminder_type
        if spaman.facade is not None:
            self._observe(spaman.facade.reminders_manager)

    @property
    def native_value(self) -> date | None:
        """Get the date that the reminder is due."""
        if (facade := self.spaman.facade) is None:
            return None
        reminder = facade.reminders_manager.get_reminder(self._reminder_type)
        if reminder is None:
            return None
        return dt_util.now().date() + timedelta(days=reminder.days)

    async def async_set_value(self, value: date) -> None:
        """Update the current value."""
        if (facade := self.spaman.facade) is None:
            return
        days = (value - dt_util.now().date()).days
        _LOGGER.debug("Set reminder delta to %d", days)
        await facade.reminders_manager.set_reminder(self._reminder_type, days)
