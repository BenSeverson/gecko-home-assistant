"""Tests for the entities on each Gecko platform."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from geckolib import GeckoReminderType, GeckoSpaEvent
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import make_full_facade, send_event, setup_entry

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
async def facade(hass: HomeAssistant, config_entry: MockConfigEntry) -> MagicMock:
    """Set the integration up with a connected spa."""
    spaman = await setup_entry(hass, config_entry)
    facade = make_full_facade()
    spaman._facade = facade
    await send_event(hass, spaman, GeckoSpaEvent.CLIENT_FACADE_IS_READY)
    return facade


async def call(
    hass: HomeAssistant, domain: str, service: str, entity_id: str, **data: object
) -> None:
    """Call an entity service."""
    await hass.services.async_call(
        domain, service, {"entity_id": entity_id, **data}, blocking=True
    )


async def test_climate(hass: HomeAssistant, facade: MagicMock) -> None:
    """The climate entity reports and controls the heater and water care."""
    state = hass.states.get("climate.my_spa_heater")
    assert state.state == "auto"
    assert state.attributes["hvac_action"] == "heating"
    assert state.attributes["current_temperature"] == 36.5
    assert state.attributes["temperature"] == 38.0
    assert state.attributes["min_temp"] == 15.0
    assert state.attributes["max_temp"] == 40.0
    assert state.attributes["preset_mode"] == "Standard"

    await call(hass, "climate", "set_temperature", state.entity_id, temperature=37)
    facade.water_heater.async_set_target_temperature.assert_awaited_once_with(37)

    await call(
        hass, "climate", "set_preset_mode", state.entity_id, preset_mode="Standard"
    )
    facade.water_care.async_set_mode.assert_awaited_once_with("Standard")

    # A change in the water care is pushed to the climate entity too
    facade.water_care.mode = None
    facade.water_care._on_change(facade.water_care, 1, None)
    await hass.async_block_till_done()
    assert hass.states.get(state.entity_id).attributes["preset_mode"] is None

    facade.water_heater.set_availability(is_available=False)
    facade.water_heater._on_change(facade.water_heater, None, None)
    await hass.async_block_till_done()
    assert hass.states.get(state.entity_id).state == STATE_UNAVAILABLE
    assert (
        hass.states.get("sensor.my_spa_current_temperature").state == STATE_UNAVAILABLE
    )


async def test_water_heater(hass: HomeAssistant, facade: MagicMock) -> None:
    """The water heater entity reports and controls the heater."""
    state = hass.states.get("water_heater.my_spa_heater")
    assert state.state == "Heating"
    assert state.attributes["current_temperature"] == 36.5
    assert state.attributes["temperature"] == 38.0
    assert state.attributes["icon"] == "mdi:hot-tub"

    await call(hass, "water_heater", "set_temperature", state.entity_id, temperature=39)
    facade.water_heater.async_set_target_temperature.assert_awaited_once_with(39)


async def test_sensors(hass: HomeAssistant, facade: MagicMock) -> None:
    """Sensors take their metadata from geckolib."""
    state = hass.states.get("sensor.my_spa_current_temperature")
    assert state.state == "36.5"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["unit_of_measurement"] == "°C"

    state = hass.states.get("sensor.my_spa_smart_winter_mode")
    assert state.state == "Off"
    assert "device_class" not in state.attributes
    assert "state_class" not in state.attributes

    state = hass.states.get("sensor.my_spa_rinse_filter_due")
    assert state.attributes["device_class"] == "timestamp"
    due = dt_util.start_of_local_day() + timedelta(days=5)
    assert dt_util.parse_datetime(state.state) == due


async def test_reminder_date(
    hass: HomeAssistant, facade: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Reminders can be read and set as dates."""
    today = dt_util.now().date()
    state = hass.states.get("date.my_spa_rinse_filter_due")
    assert state.state == (today + timedelta(days=5)).isoformat()
    assert "device_class" not in state.attributes
    entry = entity_registry.async_get(state.entity_id)
    assert entry.entity_category is er.EntityCategory.CONFIG

    new_date = today + timedelta(days=30)
    await call(hass, "date", "set_value", state.entity_id, date=new_date.isoformat())
    facade.reminders_manager.set_reminder.assert_awaited_once_with(
        GeckoReminderType.RINSE_FILTER, 30
    )


async def test_selects(hass: HomeAssistant, facade: MagicMock) -> None:
    """Selects report and change their options."""
    state = hass.states.get("select.my_spa_lock_mode")
    assert state.state == "Partial Lock"
    assert state.attributes["options"] == ["Unlocked", "Partial Lock", "Full Lock"]
    assert state.attributes["icon"] == "mdi:lock-minus-outline"

    await call(hass, "select", "select_option", state.entity_id, option="Unlocked")
    facade.lockmode.async_set_state.assert_awaited_once_with("Unlocked")

    assert hass.states.get("select.my_spa_water_care").state == "Standard"
    assert hass.states.get("select.my_spa_drying_cycle").state == "Off"
    # Unavailable accessories don't get entities
    assert hass.states.get("select.my_spa_chroma") is None


async def test_numbers(hass: HomeAssistant, facade: MagicMock) -> None:
    """Numbers report and change their values."""
    state = hass.states.get("number.my_spa_bath_runtime")
    assert state.state == "20"
    assert state.attributes["min"] == 1
    assert state.attributes["max"] == 30
    assert state.attributes["step"] == 1
    assert state.attributes["mode"] == "slider"
    assert state.attributes["unit_of_measurement"] == "min"
    assert "device_class" not in state.attributes

    await call(hass, "number", "set_value", state.entity_id, value=25)
    facade.bainultra.bath_runtime.async_set_native_value.assert_awaited_once_with(25)


async def test_light_switch_fan_button(hass: HomeAssistant, facade: MagicMock) -> None:
    """The simple on/off style entities work."""
    assert hass.states.get("light.my_spa_light").state == "on"
    await call(hass, "light", "turn_off", "light.my_spa_light")
    facade.lights[0].async_turn_off.assert_awaited_once_with()

    assert hass.states.get("switch.my_spa_eco_mode").state == "off"
    await call(hass, "switch", "turn_on", "switch.my_spa_eco_mode")
    facade.eco_mode.async_turn_on.assert_awaited_once_with()

    await call(hass, "fan", "set_preset_mode", "fan.my_spa_pump_1", preset_mode="HI")
    facade.pumps[0].async_set_mode.assert_awaited_once_with("HI")
    await call(hass, "fan", "turn_off", "fan.my_spa_pump_1")
    facade.pumps[0].async_turn_off.assert_awaited_once_with()

    await call(hass, "button", "press", "button.my_spa_pump_1_key")
    facade.keypad.buttons[0].async_press.assert_awaited_once_with()
