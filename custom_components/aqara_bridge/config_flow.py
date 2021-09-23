import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries

from . import data_masking, GLOBAL_DATA_MANAGER
from .const import (
    CONF_FIELD_EXCLUDE_DEVICES,
    DOMAIN,
    CONF_FIELD_ACCOUNT,
    CONF_FIELD_COUNTRY_CODE,
    CONF_FIELD_AUTH_CODE,
    CONF_FIELD_REFRESH_TOKEN,
    CONF_ENTRY_AUTH_ACCOUNT,
    SERVER_COUNTRY_CODES,
    SERVER_COUNTRY_CODES_DEFAULT,
    CONF_ENTRY_AUTH_ACCOUNT,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_GET_AUTH_CODE_CONFIG = vol.Schema(
    {
        vol.Required(CONF_FIELD_ACCOUNT): str,
        vol.Required(
            CONF_FIELD_COUNTRY_CODE, default=SERVER_COUNTRY_CODES_DEFAULT
        ): vol.In(SERVER_COUNTRY_CODES),
        vol.Optional(CONF_FIELD_REFRESH_TOKEN): str,
    }
)

DEVICE_GET_TOKEN_CONFIG = vol.Schema({vol.Required(CONF_FIELD_AUTH_CODE): str})


class AqaraBridgeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Aqara Bridge config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.account = None
        self.country_code = None
        self.account_type = None
        self._auth = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        GLOBAL_DATA_MANAGER.init_data(self.hass)
        if GLOBAL_DATA_MANAGER.entry:
            return await self.async_step_exclude_devices()
        else:
            return await self.async_step_get_auth_code()

    async def async_step_get_auth_code(self, user_input=None):
        """Configure an aqara device through the Aqara Cloud."""
        errors = {}
        if user_input:
            self.account = user_input.get(CONF_FIELD_ACCOUNT)
            self.country_code = user_input.get(CONF_FIELD_COUNTRY_CODE)
            self.account_type = 0
            GLOBAL_DATA_MANAGER.session.set_country(self.country_code)

            refresh_token = user_input.get(CONF_FIELD_REFRESH_TOKEN)
            if refresh_token and refresh_token != "":
                resp = await GLOBAL_DATA_MANAGER.session.async_refresh_token(
                    refresh_token
                )
                if resp["code"] == 0:
                    self._auth = GLOBAL_DATA_MANAGER.create_token_data(
                        self.account,
                        self.account_type,
                        self.country_code,
                        resp["result"],
                    )
                    return await self.async_step_exclude_devices()
                else:
                    # TODO 这里要处理API失败的情况
                    pass
            else:
                resp = await GLOBAL_DATA_MANAGER.session.async_get_auth_code(
                    self.account, 0
                )
                if resp["code"] == 0:
                    return await self.async_step_get_token()
                else:
                    # TODO 这里要处理API失败的情况
                    pass

        return self.async_show_form(
            step_id="get_auth_code",
            data_schema=DEVICE_GET_AUTH_CODE_CONFIG,
            errors=errors,
        )

    async def async_step_get_token(self, user_input=None):
        errors = {}
        if user_input:
            auth_code = user_input.get(CONF_FIELD_AUTH_CODE)
            resp = await GLOBAL_DATA_MANAGER.session.async_get_token(
                auth_code, self.account, 0
            )

            if resp["code"] == 0:
                self._auth = GLOBAL_DATA_MANAGER.create_token_data(
                    self.account,
                    self.account_type,
                    self.country_code,
                    resp["result"],
                )
            else:
                errors["base"] = "cloud_credentials_incomplete"

            if self._auth:
                return await self.async_step_exclude_devices()

        return self.async_show_form(
            step_id="get_token", data_schema=DEVICE_GET_TOKEN_CONFIG, errors=errors
        )

    async def async_step_exclude_devices(self, user_input=None):
        errors = {}
        if user_input:
            if CONF_FIELD_EXCLUDE_DEVICES in user_input:
                dids = user_input[CONF_FIELD_EXCLUDE_DEVICES]
                return self.async_create_entry(
                    title=data_masking(self._auth[CONF_ENTRY_AUTH_ACCOUNT], 4),
                    data=dict({"excluded_dids": dids}, **self._auth),
                )
                # return self.async_abort(reason="complete")
        await GLOBAL_DATA_MANAGER.aiot_manager.async_refresh_all_devices()
        devlist = {}
        [
            devlist.setdefault(x.did, f"{x.device_name} - {x.model}")
            for x in GLOBAL_DATA_MANAGER.aiot_manager.supported_devices
        ]
        return self.async_show_form(
            step_id="exclude_devices",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FIELD_EXCLUDE_DEVICES, default=[]
                    ): cv.multi_select(devlist)
                }
            ),
            errors=errors,
        )
