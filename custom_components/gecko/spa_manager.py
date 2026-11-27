"""GeckoSpaManager class manages the interactions between geckolib and HA."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Self

from geckolib import GeckoAsyncSpaMan, GeckoSpaEvent
from homeassistant.config_entries import ConfigEntry

from .const import PLATFORMS, SHOW_PING_KEY, STATUS_PLATFORMS

if TYPE_CHECKING:
    from homeassistant.const import Platform
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_QUEUE_TASK_KEY = "HASPAMAN"

type GeckoConfigEntry = ConfigEntry[GeckoSpaManager]


class GeckoSpaManager(GeckoAsyncSpaMan):
    """HA Gecko Spa Manager."""

    def __init__(
        self,
        client_id: str,
        hass: HomeAssistant | None = None,
        entry: GeckoConfigEntry | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the Spa Manager.

        The config flow uses a manager without hass or a config entry, purely
        to locate spas on the network.
        """
        super().__init__(client_id, **kwargs)
        self.hass = hass
        self.entry = entry

        self._can_use_facade = False

        self.platforms: list[Platform] = []
        self._event_queue: asyncio.Queue[GeckoSpaEvent] = asyncio.Queue()

    async def __aenter__(self) -> Self:
        """Perform async enter."""
        await super().__aenter__()
        self.start_event_processing()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Support async with."""
        self.stop_event_processing()
        return await super().__aexit__(*exc_info)

    def start_event_processing(self) -> None:
        """Start handling the spa manager events that (re)build platforms."""
        self.add_task(
            self._queue_loop(), "Home Assistant Gecko Spa Manager", _QUEUE_TASK_KEY
        )

    def stop_event_processing(self) -> None:
        """
        Stop handling spa manager events.

        This must happen before the config entry is unloaded, otherwise a
        queued event can set platforms up again part way through the unload.
        """
        self.cancel_key_tasks(_QUEUE_TASK_KEY)

    @property
    def can_use_facade(self) -> bool:
        """Determine if the facade is ready for use."""
        return self._can_use_facade

    async def _queue_loop(self) -> None:
        while True:
            event = await self._event_queue.get()
            # One unhandled exception must not kill event processing for
            # the lifetime of the integration
            try:
                if event == GeckoSpaEvent.CLIENT_FACADE_IS_READY:
                    # Wait for a single update so we have reminders and watercare
                    if self.facade is not None:
                        await self.facade.wait_for_one_update()
                    self._can_use_facade = True
                    await self.reload()

                elif event in (
                    GeckoSpaEvent.CLIENT_HAS_RECONNECT_BUTTON,
                    GeckoSpaEvent.CLIENT_HAS_STATUS_SENSOR,
                ):
                    await self.reload()

                elif event == GeckoSpaEvent.CLIENT_FACADE_TEARDOWN:
                    self._can_use_facade = False
                    await self.reload()
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("Exception handling queued event %s", event)
            finally:
                self._event_queue.task_done()

    async def handle_event(self, event: GeckoSpaEvent, **_kwargs: Any) -> None:
        """Handle spa manager events."""
        _LOGGER.debug("Event: %s, state %s", event, self.spa_state)
        # The Geckolib spa manager issues events as they happen, and sometimes
        # this is what you want, but for HA, we want to serialise some of them
        # because otherwise we end up trying to build platforms at the same time
        await self._event_queue.put(event)

    async def unload_platforms(self) -> bool:
        """Unload the platforms that were previously loaded."""
        if self.hass is None or self.entry is None or not self.platforms:
            return True

        _LOGGER.debug("Unload platforms %s", self.platforms)
        unloaded = await self.hass.config_entries.async_unload_platforms(
            self.entry, self.platforms
        )
        if unloaded:
            self.platforms = []
        return unloaded

    async def load_platforms(self) -> None:
        """Load the appropriate platforms."""
        if self.hass is None or self.entry is None:
            return
        platforms = list(PLATFORMS if self._can_use_facade else STATUS_PLATFORMS)
        _LOGGER.debug("Load platforms %s", platforms)
        self.platforms = platforms
        await self.hass.config_entries.async_forward_entry_setups(self.entry, platforms)

    async def reload(self) -> None:
        """Reload the platforms."""
        if await self.unload_platforms():
            await self.load_platforms()

    @property
    def show_ping_sensor(self) -> bool:
        """Show the ping sensor property."""
        if self.entry is None:
            return False
        return bool(self.entry.options.get(SHOW_PING_KEY, False))
