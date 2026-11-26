"""Sensor platform for Gecko."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from geckolib import GeckoReminderType
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.util import dt as dt_util

from .entity import GeckoEntity, GeckoEntityBase, reminder_name

if TYPE_CHECKING:
    from geckolib import GeckoAutomationBase, GeckoErrorSensor
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .spa_manager import GeckoConfigEntry, GeckoSpaManager

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: GeckoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    spaman = entry.runtime_data
    sensors: list[SensorEntity] = []

    # Diagnostic sensors that belong to the spa manager, these are available
    # whether or not the spa is connected
    diagnostics = [
        spaman.status_sensor,
        spaman.ping_sensor if spaman.show_ping_sensor else None,
        spaman.last_data_sensor,
        spaman.radio_sensor,
        spaman.channel_sensor,
    ]
    sensors.extend(
        GeckoSensor(spaman, sensor, EntityCategory.DIAGNOSTIC)
        for sensor in diagnostics
        if sensor is not None
    )

    if spaman.can_use_facade and (facade := spaman.facade) is not None:
        heater = facade.water_heater
        if heater.is_available:
            sensors.append(
                GeckoCurrentTemperatureSensor(
                    spaman, heater.current_temperature_sensor, heater
                )
            )
            sensors.append(GeckoSensor(spaman, heater.target_temperature_sensor))
            sensors.append(GeckoSensor(spaman, heater.real_target_temperature_sensor))
        sensors.extend(GeckoSensor(spaman, sensor) for sensor in facade.sensors)
        if facade.reminders_manager.is_available:
            sensors.extend(
                GeckoReminderSensor(spaman, reminder.reminder_type)
                for reminder in facade.reminders_manager.reminders
            )
        sensors.append(GeckoErrorTextSensor(spaman, facade.error_sensor))
        if facade.mrsteam.is_available:
            sensors.append(GeckoSensor(spaman, facade.mrsteam.remaining_runtime))
    async_add_entities(sensors)


class GeckoSensor(GeckoEntity, SensorEntity):
    """Gecko Sensor class."""

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        return self._automation_entity.state

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._automation_entity.unit_of_measurement

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor."""
        try:
            return SensorDeviceClass(self._automation_entity.device_class)
        except ValueError:
            return None

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class, so temperatures get long-term statistics."""
        if self.device_class is SensorDeviceClass.TEMPERATURE:
            return SensorStateClass.MEASUREMENT
        return None


class GeckoReminderSensor(GeckoEntityBase, SensorEntity):
    """Gecko reminder sensor class."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:reminder"

    def __init__(
        self, spaman: GeckoSpaManager, reminder_type: GeckoReminderType
    ) -> None:
        """Initialize the reminder sensor."""
        super().__init__(
            spaman,
            f"{spaman.unique_id}-{GeckoReminderType.to_string(reminder_type)}",
            f"{reminder_name(reminder_type)} due",
        )
        self._reminder_type = reminder_type
        if spaman.facade is not None:
            self._observe(spaman.facade.reminders_manager)

    @property
    def native_value(self) -> datetime | None:
        """Get the sensor native value."""
        if (facade := self.spaman.facade) is None:
            return None
        reminder = facade.reminders_manager.get_reminder(self._reminder_type)
        if reminder is None:
            return None
        return dt_util.start_of_local_day() + timedelta(days=reminder.days)


class GeckoErrorTextSensor(GeckoEntityBase, SensorEntity):
    """Gecko text error sensor class."""

    _attr_icon = "mdi:alert"

    def __init__(self, spaman: GeckoSpaManager, error_sensor: GeckoErrorSensor) -> None:
        """Initialize the error text sensor."""
        super().__init__(
            spaman,
            f"{spaman.unique_id}-ERR",
            "Error(s)",
            EntityCategory.DIAGNOSTIC,
        )
        self._error_sensor = error_sensor
        self._observe(error_sensor)

    @property
    def native_value(self) -> str | None:
        """Get native value."""
        if self.spaman.facade is None:
            return None
        return self._error_sensor.state


class GeckoCurrentTemperatureSensor(GeckoSensor):
    """Current temperature sensor, only available when the heater is."""

    def __init__(
        self,
        spaman: GeckoSpaManager,
        automation_entity: GeckoAutomationBase,
        valid_entity: GeckoAutomationBase,
    ) -> None:
        """Initialize the current temp sensor."""
        super().__init__(spaman, automation_entity)
        self._valid_entity = valid_entity
        self._observe(valid_entity)

    @property
    def available(self) -> bool:
        """Return whether the heater has a temperature to report."""
        return self._valid_entity.is_available
