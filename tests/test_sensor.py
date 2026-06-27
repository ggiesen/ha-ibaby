"""Coordinator + sensor platform tests."""

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from pyibaby.sensors import SensorReading
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ibaby.const import (
    CONF_CAMID,
    CONF_CAMNAME,
    CONF_CAMTYPE,
    CONF_EMAIL,
    CONF_P2P_PASSWORD,
    CONF_P2P_PROVIDER,
    CONF_P2P_UID,
    CONF_PASSWORD,
    DOMAIN,
)

ENTRY_DATA = {
    CONF_EMAIL: "a@b.c",
    CONF_PASSWORD: "pw",
    CONF_CAMID: "712Qacwg",
    CONF_CAMNAME: "Nursery",
    CONF_CAMTYPE: "M7",
    CONF_P2P_UID: "FCARE-044194-DBJFD",
    CONF_P2P_PROVIDER: "1",
    CONF_P2P_PASSWORD: "devsecret",
}


async def _setup(hass: HomeAssistant, reading: SensorReading | None) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id="712Qacwg")
    entry.add_to_hass(hass)
    lan = MagicMock()
    lan.read_sensors.return_value = reading
    with patch("custom_components.ibaby.coordinator.LANCamera", return_value=lan):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_sensors_populate(hass: HomeAssistant) -> None:
    await _setup(
        hass, SensorReading(temperature_c=26.3, humidity_pct=52.6, co2_ppm=1328, voc=9175, wifi=80)
    )

    assert hass.states.get("sensor.nursery_temperature").state == "26.3"
    assert hass.states.get("sensor.nursery_humidity").state == "52.6"
    assert hass.states.get("sensor.nursery_carbon_dioxide").state == "1328"
    assert hass.states.get("sensor.nursery_voc").state == "9175"
    assert hass.states.get("sensor.nursery_wi_fi_signal").state == "80"


async def test_unreachable_camera_not_ready(hass: HomeAssistant) -> None:
    # read_sensors returning None => no record => ConfigEntryNotReady => not loaded
    entry = await _setup(hass, None)
    assert entry.state is not None
    assert hass.states.get("sensor.nursery_temperature") is None
