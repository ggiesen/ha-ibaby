"""Switch platform tests (moonlight / music-light / privacy state read-back)."""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from pyibaby.protocol import ProjectorState
from pyibaby.sensors import SensorReading
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ibaby.const import DOMAIN

from .test_sensor import ENTRY_DATA


@contextlib.asynccontextmanager
async def setup_with_mock(hass: HomeAssistant, projector: ProjectorState | None = None):
    """Set up the entry with a mocked LANCamera/bridge, keeping the mocks active.

    ``projector`` is what the camera reports for GET_PROJECTORLAMP each poll.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA, unique_id="712Qacwg")
    entry.add_to_hass(hass)
    lan = MagicMock()
    lan.read_sensors.return_value = SensorReading(temperature_c=26.0, humidity_pct=50.0)
    lan.get_projector.return_value = projector or ProjectorState(
        moonlight=0, privacy=False, open_time=900
    )
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


async def test_switches_reflect_moonlight_state(hass: HomeAssistant) -> None:
    async with setup_with_mock(hass, ProjectorState(moonlight=1, privacy=True, open_time=900)):
        assert hass.states.get("switch.nursery_moonlight").state == "on"
        assert hass.states.get("switch.nursery_music_light").state == "off"
        assert hass.states.get("switch.nursery_privacy_mode").state == "on"


async def test_music_light_state(hass: HomeAssistant) -> None:
    async with setup_with_mock(hass, ProjectorState(moonlight=2, privacy=False, open_time=900)):
        assert hass.states.get("switch.nursery_music_light").state == "on"
        assert hass.states.get("switch.nursery_moonlight").state == "off"
        assert hass.states.get("switch.nursery_privacy_mode").state == "off"


async def test_turn_on_sends_command(hass: HomeAssistant) -> None:
    async with setup_with_mock(hass) as lan:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.nursery_moonlight"}, blocking=True
        )
        lan.moonlight.assert_called_with(True)

        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": "switch.nursery_privacy_mode"}, blocking=True
        )
        lan.privacy_mode.assert_called_with(True)
