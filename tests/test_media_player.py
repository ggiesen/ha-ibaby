"""Music media_player tests (browse + play + transport)."""

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.core import HomeAssistant

from .test_switch import setup_with_mock

ENTITY = "media_player.nursery_music"


async def test_features_and_transport(hass: HomeAssistant) -> None:
    async with setup_with_mock(hass) as lan:
        state = hass.states.get(ENTITY)
        assert state is not None
        feats = int(state.attributes["supported_features"])
        for f in (
            MediaPlayerEntityFeature.BROWSE_MEDIA,
            MediaPlayerEntityFeature.PLAY_MEDIA,
            MediaPlayerEntityFeature.PAUSE,
            MediaPlayerEntityFeature.STOP,
            MediaPlayerEntityFeature.NEXT_TRACK,
        ):
            assert feats & f

        await hass.services.async_call(
            "media_player", "media_next_track", {"entity_id": ENTITY}, blocking=True
        )
        lan.next_music.assert_called_once()
        await hass.services.async_call(
            "media_player", "media_stop", {"entity_id": ENTITY}, blocking=True
        )
        lan.stop_music.assert_called_once()


async def test_browse_and_play(hass: HomeAssistant) -> None:
    async with setup_with_mock(hass) as lan:
        coord = hass.config_entries.async_entries("ibaby")[0].runtime_data[0]
        tracks = [
            {
                "id": 2929,
                "name": "A Friend Like You",
                "camera_url": "http://x/y.mp3",
                "playlist_id": -10,
            },
        ]

        async def fake_list(category):
            return tracks

        coord.async_music_list = fake_list

        entity = hass.data[MP_DOMAIN].get_entity(ENTITY)

        root = await entity.async_browse_media()
        assert any(c.media_content_id == "category/songs" for c in root.children)

        listing = await entity.async_browse_media(media_content_id="category/songs")
        assert listing.children[0].media_content_id == "track/songs/2929"
        assert listing.children[0].can_play

        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": ENTITY,
                "media_content_type": "music",
                "media_content_id": "track/songs/2929",
            },
            blocking=True,
        )
        assert lan.play_music.call_args.args[0] == tracks[0]
        assert hass.states.get(ENTITY).state == "playing"
