"""Button platform for Gecko."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components import persistent_notification
from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import GeckoEntity, GeckoEntityBase

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
    """Set up button platform."""
    spaman = entry.runtime_data
    buttons: list[ButtonEntity] = []
    # facade can be None while can_use_facade is still True: async_reset nulls
    # it immediately but the teardown event is processed asynchronously
    if spaman.can_use_facade and (facade := spaman.facade) is not None:
        buttons.append(GeckoSnapshotButton(spaman))
        buttons.extend(GeckoButton(spaman, button) for button in facade.keypad.buttons)
    if spaman.reconnect_button is not None:
        buttons.append(
            GeckoButton(
                spaman,
                spaman.reconnect_button,
                EntityCategory.DIAGNOSTIC,
                "mdi:connection",
            )
        )
    if spaman.resync_button is not None:
        # Re-reads the spa state without reconnecting
        buttons.append(
            GeckoButton(
                spaman, spaman.resync_button, EntityCategory.DIAGNOSTIC, "mdi:refresh"
            )
        )
    async_add_entities(buttons)


class GeckoButton(GeckoEntity, ButtonEntity):
    """Gecko button class."""

    def __init__(
        self,
        spaman: GeckoSpaManager,
        button: GeckoAutomationBase,
        entity_category: EntityCategory | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize the button."""
        super().__init__(spaman, button, entity_category)
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Press the button asynchronously."""
        await self._automation_entity.async_press()


class GeckoSnapshotButton(GeckoEntityBase, ButtonEntity):
    """Gecko Snapshot button class."""

    _attr_icon = "mdi:magnify-scan"

    def __init__(self, spaman: GeckoSpaManager) -> None:
        """Initialize the button class."""
        super().__init__(
            spaman,
            f"{spaman.unique_id}-SNAPSHOT",
            "Snapshot",
            EntityCategory.DIAGNOSTIC,
        )

    async def async_press(self) -> None:
        """Press the button asynchronously."""
        facade = self.spaman.facade
        if facade is None:
            return
        data = facade.spa.get_snapshot_data()
        data["Integration Version"] = str(
            async_get_loaded_integration(self.hass, DOMAIN).version
        )
        _LOGGER.info("SNAPSHOT ========%s========", data)

        # Make a persistent notification so it's easy to access
        persistent_notification.async_create(
            self.hass,
            (
                "A snapshot of your Gecko system was taken at "
                f"{dt_util.now().isoformat()}\n"
                "<details>"
                "<summary>Click to expand</summary>\n\n"
                f"```{data}```"
                "</details>"
            ),
            title="Gecko Snapshot",
        )
