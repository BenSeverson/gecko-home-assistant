"""Constants for Gecko."""

from homeassistant.const import Platform

DOMAIN = "gecko"

# Platforms available once the spa facade is ready
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.DATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

# Platforms available while the spa is still connecting, or is disconnected
STATUS_PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SENSOR,
]

# Option keys
SHOW_PING_KEY = "show_ping"

# Configuration and options
CONF_SPA_NAME = "spaname"
CONF_SPA_IDENTIFIER = "spaidentifier"
CONF_SPA_ADDRESS = "spaipaddress"
CONF_CLIENT_ID = "clientid"

MANUFACTURER = "Gecko Alliance"
