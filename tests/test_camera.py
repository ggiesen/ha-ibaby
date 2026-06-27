"""Camera platform tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.camera import CameraEntityFeature, async_get_stream_source
from homeassistant.core import HomeAssistant
from pyibaby.sensors import SensorReading
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ibaby.const import DOMAIN

from .test_sensor import ENTRY_DATA


async def test_camera_entity_and_stream_source(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id="a@b.c")
    entry.add_to_hass(hass)
    lan = MagicMock()
    lan.read_sensors.return_value = SensorReading(temperature_c=26.0, humidity_pct=50.0)

    with (
        patch("custom_components.ibaby.coordinator.LANCamera", return_value=lan),
        # never spawn a real rtspd subprocess; stub the bridge URL for the whole test
        patch(
            "custom_components.ibaby.bridge.CameraBridge.async_stream_source",
            new=AsyncMock(return_value="rtsp://127.0.0.1:8554/cam"),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("camera.nursery")
        assert state is not None
        assert int(state.attributes["supported_features"]) & CameraEntityFeature.STREAM
        assert await async_get_stream_source(hass, "camera.nursery") == "rtsp://127.0.0.1:8554/cam"
