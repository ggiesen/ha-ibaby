"""Switch platform tests (optimistic moonlight / music-light / privacy)."""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from pyibaby.sensors import SensorReading
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ibaby.const import DOMAIN

from .test_sensor import ENTRY_DATA


@contextlib.asynccontextmanager
async def setup_with_mock(hass: HomeAssistant):
    """Set up the entry with a mocked LANCamera/bridge, keeping the mocks active."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id="712Qacwg")
    entry.add_to_hass(hass)
    lan = MagicMock()
    lan.read_sensors.return_value = SensorReading(temperature_c=26.0, humidity_pct=50.0)
    with (
        patch("custom_components.ibaby.coordinator.LANCamera", return_value=lan),
        patch(
            "custom_components.ibaby.bridge.CameraBridge.async_stream_source",
            new=AsyncMock(return_value=None),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield lan


async def test_moonlight_switch_drives_camera(hass: HomeAssistant) -> None:
    async with setup_with_mock(hass) as lan:
        assert hass.states.get("switch.nursery_moonlight").state == "off"

        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.nursery_moonlight"}, blocking=True
        )
        lan.moonlight.assert_called_with(True)
        assert hass.states.get("switch.nursery_moonlight").state == "on"

        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": "switch.nursery_moonlight"}, blocking=True
        )
        lan.moonlight.assert_called_with(False)
        assert hass.states.get("switch.nursery_moonlight").state == "off"


async def test_privacy_switch(hass: HomeAssistant) -> None:
    async with setup_with_mock(hass) as lan:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.nursery_privacy_mode"}, blocking=True
        )
        lan.privacy_mode.assert_called_with(True)
