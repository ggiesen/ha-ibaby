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


async def test_add_second_camera(hass: HomeAssistant) -> None:
    """Each camera becomes its own entry; the pick step hides already-added ones."""
    cam1 = _camera("712Qacwg")
    cam2 = Camera(
        camid="909Racga",
        camname="Playroom",
        camtype="M7T",
        p2p_uid="FCARE-138313-TNNJZ",
        p2p_provider="1",
        p2p_password="dev2",
    )

    async def add(camid: str) -> None:
        with patch("custom_components.ibaby.config_flow.IBabyCloud") as cloud:
            cloud.return_value.login.return_value = [cam1, cam2]
            r = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            r = await hass.config_entries.flow.async_configure(
                r["flow_id"], {CONF_EMAIL: "a@b.c", CONF_PASSWORD: "pw"}
            )
            # the pick step must only offer not-yet-configured cameras
            schema_keys = r["data_schema"].schema[CONF_CAMID].container
            assert camid in schema_keys
            r = await hass.config_entries.flow.async_configure(r["flow_id"], {CONF_CAMID: camid})
            assert r["type"] is FlowResultType.CREATE_ENTRY

    await add("712Qacwg")
    await add("909Racga")

    entries = hass.config_entries.async_entries(DOMAIN)
    assert {e.unique_id for e in entries} == {"712Qacwg", "909Racga"}
