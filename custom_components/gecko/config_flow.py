"""Adds config flow for Gecko."""

from __future__ import annotations

import ipaddress
import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CONF_CLIENT_ID,
    CONF_SPA_ADDRESS,
    CONF_SPA_IDENTIFIER,
    CONF_SPA_NAME,
    DOMAIN,
    SHOW_PING_KEY,
)
from .spa_manager import GeckoConfigEntry, GeckoSpaManager

_LOGGER = logging.getLogger(__name__)


class GeckoFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Gecko."""

    VERSION = 2
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize the flow handler class."""
        self._static_ip: str | None = None
        self._client_id = f"{uuid.uuid4()}"
        # A spa manager with no config is only used to locate spas
        self._spaman: GeckoSpaManager | None = None

    async def _async_get_spaman(self) -> GeckoSpaManager:
        """Get the spa manager used for discovery, starting it if needed."""
        if self._spaman is None:
            self._spaman = GeckoSpaManager(self._client_id)
            await self._spaman.__aenter__()
        return self._spaman

    @callback
    def async_remove(self) -> None:
        """Clean up the discovery spa manager when the flow finishes or aborts."""
        if self._spaman is not None:
            spaman, self._spaman = self._spaman, None
            self.hass.async_create_task(
                spaman.__aexit__(None, None, None), "Gecko discovery cleanup"
            )

    def _show_user_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Let the user provide an IP address, or indicate they want to search."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional(CONF_SPA_ADDRESS): str}),
            errors=errors,
        )

    def _show_pick_form(self, spaman: GeckoSpaManager) -> ConfigFlowResult:
        """Let the user choose which spa to connect to."""
        _LOGGER.debug("Found %s on the network", spaman.spa_descriptors)
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SPA_NAME): vol.In(
                        [spa.name for spa in spaman.spa_descriptors or []]
                    )
                }
            ),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for an address, or scan the network for spas."""
        # Start locating spas as soon as the flow opens, so that a scan has
        # usually finished by the time the user submits the form
        spaman = await self._async_get_spaman()
        if user_input is None:
            return self._show_user_form()

        if user_addr := user_input.get(CONF_SPA_ADDRESS, "").strip():
            _LOGGER.debug("User provided address '%s'", user_addr)
            try:
                ipaddress.IPv4Address(user_addr)
            except ValueError:
                return self._show_user_form({"base": "not_ip"})

            # Check that there is a spa there to connect to ...
            await spaman.async_set_spa_info(user_addr, None, None)
            await spaman.wait_for_descriptors()
            if not spaman.spa_descriptors:
                return self._show_user_form({"base": "no_spa"})

            self._static_ip = user_addr
            return self._show_pick_form(spaman)

        _LOGGER.debug("No address provided, so wait for scan to complete...")
        await spaman.wait_for_descriptors()
        if not spaman.spa_descriptors:
            _LOGGER.warning("No spas found on the local network")
            return self.async_abort(reason="no_spas")

        return self._show_pick_form(spaman)

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry for the spa that the user picked."""
        spaman = await self._async_get_spaman()
        if user_input is None:
            return self._show_pick_form(spaman)

        spa_name = user_input[CONF_SPA_NAME]
        spa = next(
            (spa for spa in spaman.spa_descriptors or [] if spa.name == spa_name),
            None,
        )
        if spa is None:
            return self.async_abort(reason="no_spas")

        await self.async_set_unique_id(spa.identifier_as_string)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=spa_name,
            data={
                CONF_SPA_NAME: spa_name,
                CONF_SPA_IDENTIFIER: spa.identifier_as_string,
                CONF_SPA_ADDRESS: self._static_ip,
                CONF_CLIENT_ID: self._client_id,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: GeckoConfigEntry) -> OptionsFlow:
        """Get options flow implementation class."""
        return GeckoOptionsFlowHandler()


class GeckoOptionsFlowHandler(OptionsFlow):
    """Gecko config flow options handler."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        SHOW_PING_KEY,
                        default=self.config_entry.options.get(SHOW_PING_KEY, False),
                    ): bool
                }
            ),
        )
