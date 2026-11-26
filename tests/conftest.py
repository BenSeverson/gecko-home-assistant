"""Fixtures for the Gecko integration tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from geckolib import (
    GeckoAutomationBase,
    GeckoPump,
    GeckoReminderType,
    GeckoSpaEvent,
)
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gecko.const import (
    CONF_CLIENT_ID,
    CONF_SPA_ADDRESS,
    CONF_SPA_IDENTIFIER,
    CONF_SPA_NAME,
    DOMAIN,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from homeassistant.core import HomeAssistant

    from custom_components.gecko.spa_manager import GeckoSpaManager

SPA_NAME = "My Spa"
SPA_IDENTIFIER = "SPA01:02:03:04:05:06"
SPA_UNIQUE_ID = "SPA010203040506"
CLIENT_ID = "11111111-2222-3333-4444-555555555555"

ENTRY_DATA = {
    CONF_SPA_NAME: SPA_NAME,
    CONF_SPA_IDENTIFIER: SPA_IDENTIFIER,
    CONF_SPA_ADDRESS: None,
    CONF_CLIENT_ID: CLIENT_ID,
}


class FakeStatusSensor(GeckoAutomationBase):
    """Stands in for the spa manager's status sensor."""

    def __init__(self) -> None:
        """Initialize the sensor."""
        super().__init__(SPA_UNIQUE_ID, "Status", SPA_NAME, "STATUS")
        self.state = "Connecting"
        self.unit_of_measurement = None
        self.device_class = None

    def set_state(self, state: str) -> None:
        """Change the state and tell the observers."""
        old_state, self.state = self.state, state
        self._on_change(self, old_state, state)


class FakeButton(GeckoAutomationBase):
    """Stands in for the spa manager's reconnect button."""

    def __init__(self) -> None:
        """Initialize the button."""
        super().__init__(SPA_UNIQUE_ID, "Reconnect", SPA_NAME, "RECONNECT")
        self.async_press = AsyncMock()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture(autouse=True)
def mock_geckolib() -> Generator[None]:
    """Stop the geckolib spa manager from touching the network."""
    with (
        patch(
            "geckolib.GeckoAsyncSpaMan._handle_event", new=AsyncMock(return_value=None)
        ),
        patch(
            "geckolib.GeckoAsyncSpaMan._sequence_pump",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "geckolib.GeckoAsyncSpaMan._error_watchdog",
            new=AsyncMock(return_value=None),
        ),
    ):
        yield


@pytest.fixture(autouse=True)
async def unload_entries(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Unload anything a test left loaded, so that no geckolib tasks linger."""
    yield
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a current config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=SPA_NAME,
        data=ENTRY_DATA,
        unique_id=SPA_IDENTIFIER,
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    return entry


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> GeckoSpaManager:
    """Set up the config entry and return its spa manager."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data


async def send_event(
    hass: HomeAssistant, spaman: GeckoSpaManager, event: GeckoSpaEvent
) -> None:
    """Send the spa manager an event and wait until it has been handled."""
    await spaman.handle_event(event)
    await spaman._event_queue.join()
    await hass.async_block_till_done()


def fake(name: str, key: str, *, available: bool = True, **attrs: Any) -> Any:
    """Build a geckolib automation object with the given attributes."""
    item = GeckoAutomationBase(SPA_UNIQUE_ID, name, SPA_NAME, key)
    item.set_availability(is_available=available)
    for attr, value in attrs.items():
        setattr(item, attr, value)
    return item


def make_facade() -> MagicMock:
    """Build a minimal connected spa facade with a single pump."""
    facade = MagicMock()
    facade.wait_for_one_update = AsyncMock()
    facade.disconnect = AsyncMock()
    facade.spa.get_snapshot_data.return_value = {"Spa pack": "inYT 1 v2.0"}

    facade.pumps = [
        fake(
            "Pump 1",
            "P1",
            is_on=False,
            modes=["OFF", "LO", "HI"],
            mode="OFF",
            pump_type=GeckoPump.PumpType.TWO_SPEED,
            async_turn_on=AsyncMock(),
            async_turn_off=AsyncMock(),
            async_set_mode=AsyncMock(),
        )
    ]
    facade.blowers = []
    facade.binary_sensors = []
    facade.spa_in_use_sensor = fake("Spa In Use", "INUSE", is_on=True)
    facade.error_sensor = fake("Errors", "ERRS", state="None")
    facade.sensors = []
    facade.lights = []
    facade.keypad.buttons = []
    facade.eco_mode = None
    facade.standby = None
    for optional in (
        facade.water_heater,
        facade.water_care,
        facade.reminders_manager,
        facade.mrsteam,
        facade.bainultra,
        facade.inmix,
        facade.heatpump,
        facade.ingrid,
        facade.lockmode,
        facade.keypad.backlight,
    ):
        optional.is_available = False
    return facade


def make_full_facade() -> MagicMock:
    """Build a connected spa facade with something for every platform."""
    facade = make_facade()

    def temperature(name: str, key: str, value: float) -> Any:
        return fake(
            name, key, state=value, unit_of_measurement="°C", device_class="temperature"
        )

    facade.water_heater = fake(
        "Heater",
        "HEAT",
        current_operation="Heating",
        temperature_unit="°C",
        current_temperature=36.5,
        target_temperature=38.0,
        min_temp=15.0,
        max_temp=40.0,
        async_set_target_temperature=AsyncMock(),
        current_temperature_sensor=temperature("Current Temperature", "CT", 36.5),
        target_temperature_sensor=temperature("Target Temperature", "TT", 38.0),
        real_target_temperature_sensor=temperature("Real Target", "RT", 38.0),
    )
    water_care_modes = ["Away From Home", "Standard", "Energy Saving"]
    facade.water_care = fake(
        "Water Care",
        "WC",
        modes=water_care_modes,
        mode=1,
        states=water_care_modes,
        state="Standard",
        async_set_mode=AsyncMock(),
        async_set_state=AsyncMock(),
    )
    reminder = SimpleNamespace(reminder_type=GeckoReminderType.RINSE_FILTER, days=5)
    facade.reminders_manager = fake(
        "Reminders",
        "REM",
        reminders=[reminder],
        get_reminder=MagicMock(return_value=reminder),
        set_reminder=AsyncMock(),
    )
    facade.lockmode = fake(
        "Lock Mode",
        "LOCK",
        states=["Unlocked", "Partial Lock", "Full Lock"],
        state="Partial Lock",
        async_set_state=AsyncMock(),
    )
    facade.lights = [
        fake(
            "Light",
            "LI",
            is_on=True,
            async_turn_on=AsyncMock(),
            async_turn_off=AsyncMock(),
        )
    ]
    facade.eco_mode = fake(
        "Eco Mode",
        "ECO",
        is_on=False,
        async_turn_on=AsyncMock(),
        async_turn_off=AsyncMock(),
    )
    facade.sensors = [fake("Smart Winter Mode", "SWM", state="Off", device_class=None)]
    facade.sensors[0].unit_of_measurement = None
    facade.keypad.buttons = [fake("Pump 1 Key", "KP1", async_press=AsyncMock())]

    def number(name: str, key: str) -> Any:
        return fake(
            name,
            key,
            native_value=20,
            native_min_value=1,
            native_max_value=30,
            native_step=1,
            native_unit_of_measurement="min",
            mode="slider",
            async_set_native_value=AsyncMock(),
        )

    facade.bainultra = fake(
        "BainUltra",
        "BAIN",
        bath_runtime=number("Bath Runtime", "BR"),
        bath_intensity=number("Bath Intensity", "BI"),
        drying_cycle_delay=number("Drying Cycle Delay", "DCD"),
        drying_cycle_hour=number("Drying Cycle Hour", "DCH"),
        drying_cycle_minute=number("Drying Cycle Minute", "DCM"),
        selects=[],
        switches=[],
        chroma=fake("Chroma", "CHR", available=False),
        drying_cycle=fake(
            "Drying Cycle",
            "DC",
            states=["Off", "On"],
            state="Off",
            async_set_state=AsyncMock(),
        ),
    )
    return facade
