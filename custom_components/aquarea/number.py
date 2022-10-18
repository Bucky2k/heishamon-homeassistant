"""Support for HeishaMon controlled heatpumps through MQTT."""
from __future__ import annotations
import logging

from homeassistant.components import mqtt
from homeassistant.components.mqtt.client import async_publish
from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .definitions import NUMBERS, HeishaMonNumberEntityDescription
from . import build_device_info

_LOGGER = logging.getLogger(__name__)

# async_setup_platform should be defined if one wants to support config via configuration.yaml


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HeishaMon numbers from config entry."""
    async_add_entities(
        HeishaMonMQTTNumber(hass, description, config_entry) for description in NUMBERS
    )


class HeishaMonMQTTNumber(NumberEntity):
    """Representation of a HeishaMon sensor that is updated via MQTT."""

    entity_description: HeishaMonNumberEntityDescription

    def __init__(
        self,
        hass: HomeAssistant,
        description: HeishaMonNumberEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self.hass = hass

        slug = slugify(description.key.replace("/", "_"))
        self.entity_id = f"number.{slug}"
        self._attr_unique_id = (
            f"{config_entry.entry_id}-{description.heishamon_topic_id}"
        )

    async def async_set_native_value(self, value: float) -> None:
        _LOGGER.debug(
            f"Changing {self.entity_description.name} to {value} (sent to {self.entity_description.command_topic})"
        )
        if self.entity_description.state_to_mqtt is not None:
            payload = self.entity_description.state_to_mqtt(value)
        else:
            payload = value
        await async_publish(
            self.hass,
            self.entity_description.command_topic,
            payload,
            self.entity_description.qos,
            self.entity_description.retain,
            self.entity_description.encoding,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to MQTT events."""

        @callback
        def message_received(message):
            """Handle new MQTT messages."""
            _LOGGER.debug(
                f"Received message for {self.entity_description.name}: {message}"
            )
            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)
            else:
                self._attr_native_value = message.payload

            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self.entity_description.key, message_received, 1
        )

    @property
    def device_info(self):
        return build_device_info(self.entity_description.device)
