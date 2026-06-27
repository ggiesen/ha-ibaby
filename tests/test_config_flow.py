"""Config flow tests."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pyibaby import Camera
from pyibaby.cloud import CloudError

from custom_components.ibaby.const import (
    CONF_CAMID,
    CONF_EMAIL,
    CONF_P2P_UID,
    CONF_PASSWORD,
    DOMAIN,
)


def _camera(camid: str = "712Qacwg") -> Camera:
    return Camera(
        camid=camid,
        camname="Nursery",
        camtype="M7",
        p2p_uid="FCARE-044194-DBJFD",
        p2p_provider="1",
        p2p_password="devsecret",
    )


async def test_full_flow_creates_entry(hass: HomeAssistant) -> None:
    with patch("custom_components.ibaby.config_flow.IBabyCloud") as cloud:
        cloud.return_value.login.return_value = [_camera()]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_CAMID: "712Qacwg"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Nursery"
    assert result["data"][CONF_CAMID] == "712Qacwg"
    assert result["data"][CONF_P2P_UID] == "FCARE-044194-DBJFD"
    assert result["result"].unique_id == "712Qacwg"


async def test_invalid_auth(hass: HomeAssistant) -> None:
    with patch("custom_components.ibaby.config_flow.IBabyCloud") as cloud:
        cloud.return_value.login.side_effect = CloudError("bad creds")
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "a@b.c", CONF_PASSWORD: "wrong"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_no_pppp_cameras_aborts(hass: HomeAssistant) -> None:
    tutk = _camera()
    tutk.p2p_provider = "0"  # TUTK IOTC, out of scope
    with patch("custom_components.ibaby.config_flow.IBabyCloud") as cloud:
        cloud.return_value.login.return_value = [tutk]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_cameras"
