"""PTZ button tests."""

from homeassistant.core import HomeAssistant

from .test_switch import setup_with_mock


async def test_ptz_buttons(hass: HomeAssistant) -> None:
    async with setup_with_mock(hass) as lan:
        for ent, direction in (
            ("button.nursery_move_up", 1),
            ("button.nursery_move_down", 2),
            ("button.nursery_move_left", 3),
            ("button.nursery_move_right", 6),
        ):
            await hass.services.async_call("button", "press", {"entity_id": ent}, blocking=True)
            assert lan.ptz.call_args.args == (direction,)
