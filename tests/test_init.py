"""Tests for setting up, unloading and migrating Gecko config entries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from geckolib import GeckoSpaEvent
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gecko.const import (
    CONF_CLIENT_ID,
    DOMAIN,
    PLATFORMS,
    SHOW_PING_KEY,
    STATUS_PLATFORMS,
)

from .conftest import (
    ENTRY_DATA,
    SPA_IDENTIFIER,
    SPA_NAME,
    SPA_UNIQUE_ID,
    FakeButton,
    FakeStatusSensor,
    make_facade,
    send_event,
    setup_entry,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The entry loads without a spa connection, and unloads cleanly."""
    spaman = await setup_entry(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert spaman.platforms == []

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_status_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The status sensor and reconnect button appear before the spa connects."""
    spaman = await setup_entry(hass, config_entry)
    status = FakeStatusSensor()
    spaman._status_sensor = status
    spaman._reconnect_button = FakeButton()
    await send_event(hass, spaman, GeckoSpaEvent.CLIENT_HAS_STATUS_SENSOR)

    assert spaman.platforms == STATUS_PLATFORMS

    # Entity names are composed from the device and entity name
    state = hass.states.get("sensor.my_spa_status")
    assert state is not None
    assert state.state == "Connecting"
    assert state.name == f"{SPA_NAME} Status"

    entry = entity_registry.async_get("sensor.my_spa_status")
    assert entry is not None
    assert entry.unique_id == f"{SPA_UNIQUE_ID}-STATUS"
    assert entry.has_entity_name

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.identifiers == {(DOMAIN, SPA_UNIQUE_ID)}
    assert device.name == SPA_NAME
    assert device.manufacturer == "Gecko Alliance"

    # Changes in geckolib are pushed to Home Assistant
    status.set_state("Connected")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.my_spa_status").state == "Connected"

    # ... and pressing the button gets through to geckolib
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.my_spa_reconnect"}, blocking=True
    )
    spaman.reconnect_button.async_press.assert_awaited_once()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    # The entity stopped watching when it was removed
    assert status._observers == []


async def test_facade_lifecycle(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """All platforms load when the facade is ready and go when it is torn down."""
    spaman = await setup_entry(hass, config_entry)
    spaman._status_sensor = FakeStatusSensor()
    facade = make_facade()
    spaman._facade = facade
    await send_event(hass, spaman, GeckoSpaEvent.CLIENT_FACADE_IS_READY)

    assert spaman.can_use_facade
    assert spaman.platforms == PLATFORMS
    assert hass.states.get("fan.my_spa_pump_1").state == "off"
    assert hass.states.get("binary_sensor.my_spa_spa_in_use").state == "on"
    assert hass.states.get("button.my_spa_snapshot") is not None
    assert hass.states.get("sensor.my_spa_error_s").state == "None"
    assert hass.states.get("fan.my_spa_pump_1").attributes["preset_modes"] == [
        "OFF",
        "LO",
        "HI",
    ]

    await hass.services.async_call(
        "fan", "turn_on", {"entity_id": "fan.my_spa_pump_1"}, blocking=True
    )
    facade.pumps[0].async_turn_on.assert_awaited_once_with(None, None)

    # The snapshot button raises a persistent notification
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.my_spa_snapshot"}, blocking=True
    )
    await hass.async_block_till_done()
    facade.spa.get_snapshot_data.assert_called_once()

    spaman._facade = None
    await send_event(hass, spaman, GeckoSpaEvent.CLIENT_FACADE_TEARDOWN)
    assert not spaman.can_use_facade
    assert spaman.platforms == STATUS_PLATFORMS
    assert hass.states.get("fan.my_spa_pump_1").state == "unavailable"
    assert hass.states.get("sensor.my_spa_status") is not None


async def test_no_reload_after_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Events that arrive during an unload don't set platforms up again."""
    spaman = await setup_entry(hass, config_entry)
    spaman._status_sensor = FakeStatusSensor()
    await send_event(hass, spaman, GeckoSpaEvent.CLIENT_HAS_STATUS_SENSOR)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await spaman.handle_event(GeckoSpaEvent.CLIENT_FACADE_TEARDOWN)
    await hass.async_block_till_done()

    assert spaman.platforms == []
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_options_update_reloads(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Changing the options reloads the entry with a new spa manager."""
    spaman = await setup_entry(hass, config_entry)
    assert not spaman.show_ping_sensor

    hass.config_entries.async_update_entry(config_entry, options={SHOW_PING_KEY: True})
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not spaman
    assert config_entry.runtime_data.show_ping_sensor


async def test_migrate_from_version_1(hass: HomeAssistant) -> None:
    """A version 1 entry gains a client id and a unique id."""
    data = {k: v for k, v in ENTRY_DATA.items() if k != CONF_CLIENT_ID}
    entry = MockConfigEntry(domain=DOMAIN, title=SPA_NAME, data=data, version=1)
    entry.add_to_hass(hass)

    await setup_entry(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert (entry.version, entry.minor_version) == (2, 2)
    assert entry.data[CONF_CLIENT_ID]
    assert entry.unique_id == SPA_IDENTIFIER


async def test_migrate_duplicate_keeps_loading(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A second entry for the same spa migrates without stealing the unique id."""
    duplicate = MockConfigEntry(
        domain=DOMAIN, title=SPA_NAME, data=ENTRY_DATA, version=2, minor_version=1
    )
    duplicate.add_to_hass(hass)

    await setup_entry(hass, duplicate)

    assert duplicate.state is ConfigEntryState.LOADED
    assert duplicate.minor_version == 2
    assert duplicate.unique_id is None


async def test_migrate_from_future_version(hass: HomeAssistant) -> None:
    """An entry from a newer major version is not loaded."""
    entry = MockConfigEntry(domain=DOMAIN, title=SPA_NAME, data=ENTRY_DATA, version=3)
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
