"""Tests for the Gecko config and options flows."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.gecko.const import (
    CONF_CLIENT_ID,
    CONF_SPA_ADDRESS,
    CONF_SPA_IDENTIFIER,
    CONF_SPA_NAME,
    DOMAIN,
    SHOW_PING_KEY,
)

from .conftest import SPA_IDENTIFIER, SPA_NAME

if TYPE_CHECKING:
    from collections.abc import Generator

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
def discovery() -> Generator[MagicMock]:
    """Replace the spa manager that the config flow uses to find spas."""
    spaman = MagicMock()
    spaman.__aenter__ = AsyncMock(return_value=spaman)
    spaman.__aexit__ = AsyncMock(return_value=None)
    spaman.async_set_spa_info = AsyncMock()
    spaman.wait_for_descriptors = AsyncMock()
    spaman.spa_descriptors = [
        SimpleNamespace(name=SPA_NAME, identifier_as_string=SPA_IDENTIFIER)
    ]
    with patch(
        "custom_components.gecko.config_flow.GeckoSpaManager", return_value=spaman
    ):
        yield spaman


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Don't set the integration up when the flow creates an entry."""
    with patch("custom_components.gecko.async_setup_entry", return_value=True) as setup:
        yield setup


async def test_scan_flow(
    hass: HomeAssistant, discovery: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Leaving the address blank scans the network for spas."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick"
    discovery.async_set_spa_info.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPA_NAME: SPA_NAME}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SPA_NAME
    assert result["data"][CONF_SPA_NAME] == SPA_NAME
    assert result["data"][CONF_SPA_IDENTIFIER] == SPA_IDENTIFIER
    assert result["data"][CONF_SPA_ADDRESS] is None
    assert result["data"][CONF_CLIENT_ID]
    assert result["result"].unique_id == SPA_IDENTIFIER
    assert mock_setup_entry.call_count == 1

    # The discovery spa manager is closed once the flow is done
    discovery.__aenter__.assert_awaited_once()
    discovery.__aexit__.assert_awaited_once()


async def test_address_flow(
    hass: HomeAssistant, discovery: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """A spa can be found from its IP address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPA_ADDRESS: "10.1.2.3"}
    )
    assert result["step_id"] == "pick"
    discovery.async_set_spa_info.assert_awaited_once_with("10.1.2.3", None, None)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPA_NAME: SPA_NAME}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SPA_ADDRESS] == "10.1.2.3"


async def test_address_errors(
    hass: HomeAssistant, discovery: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Bad addresses are reported, and the user can try again."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPA_ADDRESS: "not an address"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_ip"}

    discovery.spa_descriptors = []
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPA_ADDRESS: "10.1.2.3"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_spa"}

    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    discovery.__aexit__.assert_awaited_once()


async def test_scan_finds_nothing(hass: HomeAssistant, discovery: MagicMock) -> None:
    """The flow aborts when no spas are found."""
    discovery.spa_descriptors = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_spas"


async def test_already_configured(
    hass: HomeAssistant, discovery: MagicMock, config_entry: MockConfigEntry
) -> None:
    """The same spa can't be added twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SPA_NAME: SPA_NAME}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_setup_entry: AsyncMock
) -> None:
    """The ping sensor can be turned on from the options."""
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {SHOW_PING_KEY: True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {SHOW_PING_KEY: True}
