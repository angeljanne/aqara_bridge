import logging
from homeassistant.components.sensor import SensorEntity

from . import GLOBAL_DATA_MANAGER
from .aiot_manager import AiotEntityBase

TYPE = "sensor"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    await GLOBAL_DATA_MANAGER.aiot_manager.async_add_entities(
        TYPE, AiotSensorEntity, async_add_entities
    )


class AiotSensorEntity(AiotEntityBase, SensorEntity):
    def __init__(self, hass, device, res_params, channel=None, **kwargs):
        AiotEntityBase.__init__(self, hass, device, res_params, TYPE, channel, **kwargs)
        self._attr_state_class = kwargs.get("state_class")
        self._attr_name = f"{self._attr_name} {self._attr_device_class}"

    def convert_res_to_attr(self, res_name, res_value):
        if res_name == "battry":
            return int(res_value)
        return super().convert_res_to_attr(res_name, res_value)
