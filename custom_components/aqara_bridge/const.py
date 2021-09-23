"""Constants for the Aqara Bridge component."""
DOMAIN = "aqara_bridge"

# Config flow fields
CONF_FIELD_ACCOUNT = "field_account"
CONF_FIELD_COUNTRY_CODE = "field_country_code"
CONF_FIELD_AUTH_CODE = "field_auth_code"
CONF_FIELD_EXCLUDE_DEVICES = "field_excluded_devices"
CONF_FIELD_REFRESH_TOKEN = "field_refresh_token"

# Cloud
SERVER_COUNTRY_CODES = ["CN", "USA", "KR", "RU", "GER"]
SERVER_COUNTRY_CODES_DEFAULT = "CN"

# CONFIG ENTRY
CONF_ENTRY_AUTH_ACCOUNT = "account"
CONF_ENTRY_AUTH_ACCOUNT_TYPE = "account_type"
CONF_ENTRY_AUTH_COUNTRY_CODE = "country_code"
CONF_ENTRY_AUTH_EXPIRES_IN = "expires_in"
CONF_ENTRY_AUTH_EXPIRES_TIME = "expires_datetime"
CONF_ENTRY_AUTH_ACCESS_TOKEN = "access_token"
CONF_ENTRY_AUTH_REFRESH_TOKEN = "refresh_token"
CONF_ENTRY_AUTH_OPENID = "open_id"
CONF_ENTRY_EXCLUDED_DIDS = "excluded_dids"
