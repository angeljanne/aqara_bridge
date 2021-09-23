import logging
from homeassistant.components.switch import SwitchEntity

from . import GLOBAL_DATA_MANAGER
from .aiot_manager import AiotToggleableEntityBase

TYPE = "switch"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    await GLOBAL_DATA_MANAGER.aiot_manager.async_add_entities(
        TYPE, AiotSwitchEntity, async_add_entities
    )


class AiotSwitchEntity(AiotToggleableEntityBase, SwitchEntity):
    def __init__(self, hass, device, res_params, channel=None, **kwargs):
        AiotToggleableEntityBase.__init__(
            self, hass, device, res_params, TYPE, channel, **kwargs
        )
