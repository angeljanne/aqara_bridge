from asyncio.unix_events import FastChildWatcher
import datetime
import re
import logging

from homeassistant.helpers import aiohttp_client

from .aiot_manager import (
    AiotManager,
    AiotDevice,
)
from .aiot_cloud import AiotCloud
from .const import *


_LOGGER = logging.getLogger(__name__)


def data_masking(s: str, n: int) -> str:
    return re.sub(f"(?<=.{{{n}}}).(?=.{{{n}}})", "*", str(s))


def gen_auth_entry(
    account: str, account_type: int, country_code: str, token_result: dict
):
    auth_entry = {}
    auth_entry[CONF_ENTRY_AUTH_ACCOUNT] = account
    auth_entry[CONF_ENTRY_AUTH_ACCOUNT_TYPE] = account_type
    auth_entry[CONF_ENTRY_AUTH_COUNTRY_CODE] = country_code
    auth_entry[CONF_ENTRY_AUTH_OPENID] = token_result["openId"]
    auth_entry[CONF_ENTRY_AUTH_ACCESS_TOKEN] = token_result["accessToken"]
    auth_entry[CONF_ENTRY_AUTH_EXPIRES_IN] = token_result["expiresIn"]
    auth_entry[CONF_ENTRY_AUTH_EXPIRES_TIME] = (
        datetime.datetime.now()
        + datetime.timedelta(seconds=int(token_result["expiresIn"]))
    ).strftime("%Y-%m-%d %H:%M:%S")
    auth_entry[CONF_ENTRY_AUTH_REFRESH_TOKEN] = token_result["refreshToken"]
    return auth_entry


def init_hass_data(hass):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(HASS_DATA_AUTH_ENTRY_ID, None)
    session = AiotCloud(aiohttp_client.async_create_clientsession(hass))
    if not hass.data[DOMAIN].get(HASS_DATA_AIOTCLOUD):
        hass.data[DOMAIN].setdefault(HASS_DATA_AIOTCLOUD, session)
    if not hass.data[DOMAIN].get(HASS_DATA_AIOT_MANAGER):
        hass.data[DOMAIN].setdefault(HASS_DATA_AIOT_MANAGER, AiotManager(hass, session))


async def async_setup(hass, config):
    """Setup component."""
    init_hass_data(hass)
    return True


async def async_setup_entry(hass, entry):
    def token_updated(access_token, refresh_token):
        auth_entry = hass.data[DOMAIN][HASS_DATA_AUTH_ENTRY_ID]
        if auth_entry:
            data = auth_entry.data.copy()
            data[CONF_ENTRY_AUTH_ACCESS_TOKEN] = access_token
            data[CONF_ENTRY_AUTH_REFRESH_TOKEN] = refresh_token
            hass.config_entries.async_update_entry(entry, data=data)

    """Set up the Aqara components from a config entry."""
    data = entry.data.copy()
    manager: AiotManager = hass.data[DOMAIN][HASS_DATA_AIOT_MANAGER]
    if CONF_ENTRY_AUTH_ACCOUNT in entry.data:
        aiotcloud: AiotCloud = hass.data[DOMAIN][HASS_DATA_AIOTCLOUD]
        aiotcloud.update_token_event_callback = token_updated
        if (
            datetime.datetime.strptime(
                data.get(CONF_ENTRY_AUTH_EXPIRES_TIME), "%Y-%m-%d %H:%M:%S"
            )
            <= datetime.datetime.now()
        ):
            resp = aiotcloud.async_refresh_token(
                data.get(CONF_ENTRY_AUTH_REFRESH_TOKEN)
            )
            if resp["code"] == 0:
                auth_entry = gen_auth_entry(
                    data.get(CONF_ENTRY_AUTH_ACCOUNT),
                    data.get(CONF_ENTRY_AUTH_ACCOUNT_TYPE),
                    data.get(CONF_ENTRY_AUTH_COUNTRY_CODE),
                    resp["result"],
                )
                hass.config_entries.async_update_entry(entry, data=auth_entry)
            else:
                # TODO 这里需要处理刷新令牌失败的情况
                return False
        else:
            aiotcloud.set_country(data.get(CONF_ENTRY_AUTH_COUNTRY_CODE))
            aiotcloud.access_token = data.get(CONF_ENTRY_AUTH_ACCESS_TOKEN)
            aiotcloud.refresh_token = data.get(CONF_ENTRY_AUTH_REFRESH_TOKEN)

        hass.data[DOMAIN][HASS_DATA_AUTH_ENTRY_ID] = entry.entry_id
        await manager.async_refresh_all_devices()
    else:
        await manager.async_add_devices(entry, [AiotDevice(**entry.data)], True)
        await manager.async_forward_entry_setup(entry)

    return True


async def async_unload_entry(hass, entry):
    # if CONF_ENTRY_AUTH_ACCOUNT in entry.data:
    #     hass.data[DOMAIN][HASS_DATA_AUTH_ENTRY_ID] = None
    # else:
    #     manager: AiotManager = hass.data[DOMAIN][HASS_DATA_AIOT_MANAGER]
    #     await manager.async_unload_entry(entry)
    return True


async def async_remove_entry(hass, entry):
    if CONF_ENTRY_AUTH_ACCOUNT in entry.data:
        hass.data[DOMAIN][HASS_DATA_AUTH_ENTRY_ID] = None
    else:
        manager: AiotManager = hass.data[DOMAIN][HASS_DATA_AIOT_MANAGER]
        await manager.async_remove_entry(entry)
    return True
