"""Config flow tests (one sign-in adds the whole account)."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pyibaby import Camera
from pyibaby.cloud import CloudError

from custom_components.ibaby.const import (
    CONF_CAMERAS,
    CONF_CAMID,
    CONF_EMAIL,
    CONF_PASSWORD,
    DOMAIN,
)


def _camera(camid: str, name: str, uid: str) -> Camera:
    return Camera(
        camid=camid,
        camname=name,
        camtype="M7",
        p2p_uid=uid,
        p2p_provider="1",
        p2p_password="dev",
    )


CAMS = [
    _camera("712Qacwg", "Nursery", "FCARE-044194-DBJFD"),
    _camera("909Racga", "Playroom", "FCARE-138313-TNNJZ"),
]


async def _run(hass: HomeAssistant, cameras: list[Camera]) -> dict:
    with patch("custom_components.ibaby.config_flow.IBabyCloud") as cloud:
        cloud.return_value.login.return_value = cameras
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw"}
        )


async def test_one_signin_adds_all_cameras(hass: HomeAssistant) -> None:
    result = await _run(hass, CAMS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "a@b.c"
    assert result["result"].unique_id == "a@b.c"
    camids = {c[CONF_CAMID] for c in result["data"][CONF_CAMERAS]}
    assert camids == {"712Qacwg", "909Racga"}


async def test_only_pppp_cameras_are_added(hass: HomeAssistant) -> None:
    tutk = _camera("0000TUTK", "Old", "FCARE-000001-AAAAA")
    tutk.p2p_provider = "0"  # ThroughTek IOTC, out of scope
    result = await _run(hass, [*CAMS, tutk])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    camids = {c[CONF_CAMID] for c in result["data"][CONF_CAMERAS]}
    assert camids == {"712Qacwg", "909Racga"}


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
    tutk = _camera("0000TUTK", "Old", "FCARE-000001-AAAAA")
    tutk.p2p_provider = "0"
    result = await _run(hass, [tutk])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_cameras"


async def test_account_added_once(hass: HomeAssistant) -> None:
    assert (await _run(hass, CAMS))["type"] is FlowResultType.CREATE_ENTRY
    second = await _run(hass, CAMS)
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_configured"
