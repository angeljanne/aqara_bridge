import re
import logging

from .aiot_manager import GLOBAL_DATA_MANAGER
from .const import *


_LOGGER = logging.getLogger(__name__)


def data_masking(s: str, n: int) -> str:
    return re.sub(f"(?<=.{{{n}}}).(?=.{{{n}}})", "*", str(s))


async def async_setup(hass, config):
    """Setup component."""
    GLOBAL_DATA_MANAGER.init_data(hass)
    return True


async def async_setup_entry(hass, entry):
    """Set up the Aqara components from a config entry."""
    GLOBAL_DATA_MANAGER.set_entry(entry)
    if not await GLOBAL_DATA_MANAGER.async_refresh_token():
        GLOBAL_DATA_MANAGER.session_update_token(
            entry.data.get(CONF_ENTRY_AUTH_ACCESS_TOKEN),
            entry.data.get(CONF_ENTRY_AUTH_COUNTRY_CODE),
            entry.data.get(CONF_ENTRY_AUTH_COUNTRY_CODE),
        )
    await GLOBAL_DATA_MANAGER.aiot_manager.async_refresh_all_devices()
    await GLOBAL_DATA_MANAGER.aiot_manager.async_add_devices(entry)
    await GLOBAL_DATA_MANAGER.aiot_manager.async_forward_entry_setup(entry)
    return True


async def async_unload_entry(hass, entry):
    return True


async def async_remove_entry(hass, entry):
    await GLOBAL_DATA_MANAGER.aiot_manager.async_remove_entry()
    return True
