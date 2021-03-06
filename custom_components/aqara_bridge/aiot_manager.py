import asyncio
import datetime
import json
import logging
import time

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo, Entity
from rocketmq.client import PushConsumer, RecvMessage
from homeassistant.helpers import aiohttp_client

from .aiot_cloud import AiotCloud

from .aiot_cloud import AiotCloud, APP_ID, KEY_ID, APP_KEY
from .aiot_mapping import (
    MK_MAPPING_PARAMS,
    MK_INIT_PARAMS,
    MK_RESOURCES,
    AIOT_DEVICE_MAPPING,
)
from .const import (
    DOMAIN,
    CONF_ENTRY_AUTH_ACCOUNT,
    CONF_ENTRY_AUTH_ACCOUNT_TYPE,
    CONF_ENTRY_AUTH_COUNTRY_CODE,
    CONF_ENTRY_AUTH_EXPIRES_IN,
    CONF_ENTRY_AUTH_EXPIRES_TIME,
    CONF_ENTRY_AUTH_ACCESS_TOKEN,
    CONF_ENTRY_AUTH_REFRESH_TOKEN,
    CONF_ENTRY_AUTH_OPENID,
    CONF_ENTRY_EXCLUDED_DIDS,
)


_LOGGER = logging.getLogger(__name__)


class AiotDevice:
    def __init__(self, **kwargs):
        self.did = kwargs.get("did")
        self.parent_did = kwargs.get("parentDid")
        self.model = kwargs.get("model")
        self.model_type = kwargs.get("modelType")
        self.device_name = kwargs.get("deviceName")
        self.state = kwargs.get("state")
        self.timezone = kwargs.get("timeZone")
        self.firmware_version = kwargs.get("firmwareVersion")
        self.create_time = kwargs.get("createTime")
        self.update_time = kwargs.get("updateTime")
        self.platforms = None
        if AIOT_DEVICE_MAPPING.get(self.model):
            self.platforms = list(AIOT_DEVICE_MAPPING.get(self.model).keys())
        self.children = []

    @property
    def is_supported(self):
        return self.platforms is not None


class AiotEntityBase(Entity):
    def __init__(self, hass, device, res_params, type_name, channel=None, **kwargs):
        self._device = device
        self._res_params = res_params
        self._supported_resources = []
        [
            self._supported_resources.append(v[0].format(channel))
            for k, v in res_params.items()
        ]
        self._channel = channel

        self.hass = hass
        self._attr_name = device.device_name
        self._attr_should_poll = False
        self._attr_unique_id = (
            f"{DOMAIN}.{type_name}_{device.model.replace('.','_')}_{device.did[-5:]}"
        )
        self.entity_id = f"{DOMAIN}.{device.model.replace('.','_')}_{device.did[-5:]}"
        if channel:
            self._attr_unique_id = f"{self._attr_unique_id}_{channel}"
            self.entity_id = f"{self.entity_id}_{channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.did)},
            name=self._attr_name,
            model=device.model,
            manufacturer=(device.model or "Lumi").split(".", 1)[0].capitalize(),
            sw_version=device.firmware_version,
        )
        self._attr_supported_features = kwargs.get("supported_features")
        self._attr_unit_of_measurement = kwargs.get("unit_of_measurement")
        self._attr_device_class = kwargs.get("device_class")

    _channel = None
    _device = None
    _res_params = None
    _supported_resources = None

    @property
    def channel(self) -> int:
        return self._channel

    @property
    def supported_resources(self) -> list:
        return self._supported_resources

    @property
    def device(self) -> AiotDevice:
        return self._device

    def get_res_id_by_name(self, res_name):
        return self._res_params[res_name][0].format(self._channel)

    async def async_set_res_value(self, res_name, value):
        """???????????????"""
        res_id = self.get_res_id_by_name(res_name)
        return await GLOBAL_DATA_MANAGER.session.async_write_resource_device(
            self.device.did, res_id, value
        )

    async def async_fetch_res_values(self, *args):
        """???????????????"""
        res_ids = []
        if len(args) > 0:
            res_ids = args
        else:
            [
                res_ids.append(self.get_res_id_by_name(k))
                for k, v in self._res_params.items()
            ]
        return await GLOBAL_DATA_MANAGER.session.async_query_resource_value(
            self.device.did, res_ids
        )

    async def async_update(self, write_ha_state=False):
        resp = await self.async_fetch_res_values()
        for x in resp:
            await self.async_set_attr(x["resourceId"], x["value"], write_ha_state)

    async def async_set_resource(self, res_name, attr_value):
        """??????aiot resource??????"""
        tup_res = self._res_params.get(res_name)
        res_value = attr_value
        current_value = getattr(self, tup_res[1])
        resp = None
        if current_value != attr_value:
            res_value = self.convert_attr_to_res(res_name, attr_value)
            resp = await self.async_set_res_value(res_name, res_value)
        # TODO ??????????????????????????????????????????????????????
        self.__setattr__(tup_res[1], attr_value)
        self.async_write_ha_state()
        return resp

    async def async_set_attr(self, res_id, res_value, write_ha_state=True):
        """??????ha attr??????"""
        res_name = next(
            k
            for k, v in self._res_params.items()
            if v[0].format(self.channel) == res_id
        )
        tup_res = self._res_params.get(res_name)
        attr_value = self.convert_res_to_attr(res_name, res_value)
        current_value = getattr(self, tup_res[1], None)
        if current_value != attr_value:
            self.__setattr__(tup_res[1], attr_value)
            if write_ha_state:
                self.async_write_ha_state()  # ??????????????????????????????????????????????????????????????????????????????

    def convert_attr_to_res(self, res_name, attr_value):
        """???attr?????????res"""
        return attr_value

    def convert_res_to_attr(self, res_name, res_value):
        """???res?????????attr"""
        return res_value


class AiotToggleableEntityBase(AiotEntityBase):
    def __init__(self, hass, device, res_params, type_name, channel, **kwargs):
        super().__init__(hass, device, res_params, type_name, channel=channel, **kwargs)
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs):
        await self.async_set_resource("toggle", True)

    async def async_turn_off(self, **kwargs):
        await self.async_set_resource("toggle", False)

    def convert_attr_to_res(self, res_name, attr_value):
        if res_name == "toggle":
            # res_value???bool
            return "1" if attr_value else "0"
        return super().convert_attr_to_res(res_name, attr_value)

    def convert_res_to_attr(self, res_name, res_value):
        if res_name == "toggle":
            # res_value???0???1????????????
            return res_value == "1"
        return super().convert_res_to_attr(res_name, res_value)


class AiotMessageHandler:
    def __init__(self, loop):
        self._loop = loop
        self._consumer = PushConsumer(APP_ID)
        self._consumer.set_namesrv_addr("3rd-subscription.aqara.cn:9876")
        self._consumer.set_session_credentials(KEY_ID, APP_KEY, "")
        self._ts = int(round(time.time() * 1000))

    def start(self, callback):
        def consumer_callback(msg: RecvMessage):
            json_msg = json.loads(str(msg.body, "utf-8"))
            if int(json_msg.get("time")) >= self._ts:
                asyncio.run_coroutine_threadsafe(
                    callback(json_msg),
                    self._loop,
                )

        self._consumer.subscribe(APP_ID, consumer_callback)
        self._consumer.start()

    def stop(self):
        self._consumer.shutdown()


class AiotManager:
    def __init__(self):
        self._msg_handler = AiotMessageHandler(asyncio.get_event_loop())
        self._msg_handler.start(self._msg_callback)

    # ????????????
    _all_devices: dict[str, list[AiotDevice]] = {}

    # ?????????HA??????????????????
    _managed_devices: dict[str, AiotDevice] = {}

    # ?????????????????????????????????1???N
    _devices_entities: dict[str, list[AiotEntityBase]] = {}

    # ??????????????????????????????
    _unsupported_devices: list[AiotDevice] = []

    @property
    def all_devices(self) -> list[AiotDevice]:
        """??????Aiot Cloud??????????????????"""
        return self._all_devices.values()

    @property
    def unmanaged_gateways(self) -> list[AiotDevice]:
        """??????HA????????????????????????"""
        gateways = []
        [
            gateways.append(x)
            for x in self.all_devices
            if x.model_type in (1, 2) and x.did not in self._managed_devices.keys()
        ]
        return gateways

    @property
    def unsupported_devices(self) -> list[AiotDevice]:
        """??????????????????????????????"""
        devices = []
        [devices.append(x) for x in self.all_devices if not x.is_supported]
        return devices

    @property
    def supported_devices(self) -> list[AiotDevice]:
        """???????????????????????????"""
        devices = []
        [devices.append(x) for x in self.all_devices if x.is_supported]
        return devices

    async def _msg_callback(self, msg):
        """????????????????????????https://opendoc.aqara.cn/docs/%E4%BA%91%E5%AF%B9%E6%8E%A5%E5%BC%80%E5%8F%91%E6%89%8B%E5%86%8C/%E6%B6%88%E6%81%AF%E6%8E%A8%E9%80%81/%E6%B6%88%E6%81%AF%E6%8E%A8%E9%80%81%E6%A0%BC%E5%BC%8F.html"""
        if msg.get("msgType"):
            # ???????????????resource_report
            for x in msg["data"]:
                entities = self._devices_entities.get(x["subjectId"])
                if entities:
                    for entity in entities:
                        if x["resourceId"] in entity.supported_resources:
                            await entity.async_set_attr(x["resourceId"], x["value"])

    async def async_refresh_all_devices(self):
        """??????Aiot????????????"""
        self._all_devices = {}
        results = await GLOBAL_DATA_MANAGER.session.async_query_all_devices_info()
        [self._all_devices.setdefault(x["did"], AiotDevice(**x)) for x in results]

    async def async_add_devices(self, config_entry: ConfigEntry):
        excluded_dids = config_entry.data.get(CONF_ENTRY_EXCLUDED_DIDS)
        await self.async_refresh_all_devices()  # ??????????????????????????????
        for device in self.supported_devices:
            if device.did not in excluded_dids:
                self._managed_devices[device.did] = device

    async def async_forward_entry_setup(self, config_entry: ConfigEntry):
        platforms = []
        [platforms.extend(v.platforms) for k, v in self._managed_devices.items()]
        platforms = set(platforms)
        [
            GLOBAL_DATA_MANAGER.hass.async_create_task(
                GLOBAL_DATA_MANAGER.hass.config_entries.async_forward_entry_setup(
                    config_entry, x
                )
            )
            for x in platforms
        ]

    async def async_add_entities(self, entity_type: str, t, async_add_entities):
        """??????ConfigEntry??????Entity"""
        devices = []
        [
            devices.append(v)
            for k, v in self._managed_devices.items()
            if entity_type in v.platforms
        ]
        entities = []
        for device in devices:
            self._devices_entities.setdefault(device.did, [])
            params = AIOT_DEVICE_MAPPING[device.model][entity_type]
            ch_count = None
            # ??????????????????????????????
            if device.model == "lumi.airrtc.vrfegl01":
                # VRF???????????????
                resp = await GLOBAL_DATA_MANAGER.session.async_query_resource_value(
                    device.did, ["13.1.85"]
                )
                ch_count = int(resp[0]["value"])

            if params.get(MK_MAPPING_PARAMS):
                ch_count = ch_count or params[MK_MAPPING_PARAMS].get("ch_count")

            if ch_count:
                for i in range(ch_count):
                    instance = t(
                        GLOBAL_DATA_MANAGER.hass,
                        device,
                        params[MK_RESOURCES],
                        i + 1,
                        **params.get(MK_INIT_PARAMS) or {},
                    )
                    self._devices_entities[device.did].append(instance)
                    entities.append(instance)
            else:
                instance = t(
                    GlobalDataManager.hass,
                    device,
                    params[MK_RESOURCES],
                    **params.get(MK_INIT_PARAMS) or {},
                )
                self._devices_entities[device.did].append(instance)
                entities.append(instance)

        async_add_entities(entities, update_before_add=True)

    async def async_remove_entry(self):
        """ConfigEntry remove."""
        for device_id in self._managed_devices.keys():
            self._managed_devices.pop(device_id)
            self._devices_entities.pop(device_id)


class GlobalDataManager:

    _hass: HomeAssistant = None
    _entry: ConfigEntry = None
    _session: AiotCloud = None
    _aiot_manager: AiotManager = None

    @property
    def hass(self) -> HomeAssistant:
        return self._hass

    @property
    def entry(self) -> ConfigEntry:
        """???????????????entry??????"""
        return self._entry

    @property
    def entry_data(self) -> dict:
        return self.entry.data.copy()

    def set_entry(self, entry: ConfigEntry):
        self._entry = entry

    @property
    def session(self) -> AiotCloud:
        """TCP??????"""
        return self._session

    @property
    def aiot_manager(self) -> AiotManager:
        return self._aiot_manager

    def init_data(self, hass):
        if self.hass is not None:
            return

        self._hass = hass
        # self._hass.data.setdefault(DOMAIN, {})  # ???????????????
        self._session = AiotCloud(aiohttp_client.async_create_clientsession(self.hass))
        self._session.update_token_event_callback = self.entry_update_token
        self._aiot_manager = AiotManager()

    def create_token_data(
        self, account: str, account_type: int, country_code: str, token_result: dict
    ):
        data = {}
        data[CONF_ENTRY_AUTH_ACCOUNT] = account
        data[CONF_ENTRY_AUTH_ACCOUNT_TYPE] = account_type
        data[CONF_ENTRY_AUTH_COUNTRY_CODE] = country_code
        data[CONF_ENTRY_AUTH_OPENID] = token_result["openId"]
        data[CONF_ENTRY_AUTH_ACCESS_TOKEN] = token_result["accessToken"]
        data[CONF_ENTRY_AUTH_EXPIRES_IN] = token_result["expiresIn"]
        data[CONF_ENTRY_AUTH_EXPIRES_TIME] = (
            datetime.datetime.now()
            + datetime.timedelta(seconds=int(token_result["expiresIn"]))
        ).strftime("%Y-%m-%d %H:%M:%S")
        data[CONF_ENTRY_AUTH_REFRESH_TOKEN] = token_result["refreshToken"]
        return data

    def session_update_token(
        self, access_token: str, refresh_token: str, country_code: str = None
    ):
        if country_code:
            self.session.set_country(country_code)
        self.session.access_token = access_token
        self.session.refresh_token = refresh_token

    def entry_update_token(self, token_result: dict):
        if self.entry:
            data = self.entry.data.copy()
            data[CONF_ENTRY_AUTH_ACCESS_TOKEN] = token_result["accessToken"]
            data[CONF_ENTRY_AUTH_EXPIRES_IN] = token_result["expiresIn"]
            data[CONF_ENTRY_AUTH_EXPIRES_TIME] = (
                datetime.datetime.now()
                + datetime.timedelta(seconds=int(token_result["expiresIn"]))
            ).strftime("%Y-%m-%d %H:%M:%S")
            data[CONF_ENTRY_AUTH_REFRESH_TOKEN] = token_result["refreshToken"]
            self.hass.config_entries.async_update_entry(self.entry, data=data)

    async def async_refresh_token(
        self, refresh_token: str = None, force_refresh_token=False
    ):
        """
        ????????????
        refresh_token?????????refresh token?????????????????????????????????force_refresh_token??????
        force_refresh_token?????????????????????????????????????????????False??????????????????????????????????????????
        """
        data = self.entry.data.copy()
        resp = None
        if refresh_token:
            resp = await self.session.async_refresh_token(refresh_token)
        else:
            if force_refresh_token:
                resp = await self.session.async_refresh_token(
                    data.get(CONF_ENTRY_AUTH_REFRESH_TOKEN)
                )
            else:
                if (
                    datetime.datetime.strptime(
                        data.get(CONF_ENTRY_AUTH_EXPIRES_TIME), "%Y-%m-%d %H:%M:%S"
                    )
                    <= datetime.datetime.now()
                ):
                    resp = await self.session.async_refresh_token(
                        data.get(CONF_ENTRY_AUTH_REFRESH_TOKEN)
                    )

        if resp and resp["code"] == 0:
            self.entry_update_token(resp["result"])
            return True
        else:
            return False


GLOBAL_DATA_MANAGER = GlobalDataManager()
