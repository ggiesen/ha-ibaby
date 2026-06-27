# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Built-in music player.

The camera plays built-in sounds itself (it fetches the track URL and plays it on
its own speaker), so this is a control + browser surface, not an audio renderer.
The camera reports no reliable playback status, so state is optimistic.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyibaby import protocol as P

from .coordinator import IbabyConfigEntry, IbabyCoordinator
from .entity import IbabyEntity

# Category key (pyibaby cloud.MUSIC_CATEGORIES) -> display label.
CATEGORIES: dict[str, str] = {
    "lullabies": "Lullabies",
    "stories": "Stories",
    "white_noise": "White noise",
    "nature": "Nature",
    "songs": "Songs",
}

_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IbabyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a music player per camera."""
    async_add_entities(IbabyMediaPlayer(coordinator) for coordinator in entry.runtime_data)


class IbabyMediaPlayer(IbabyEntity, MediaPlayerEntity):
    """Plays the camera's built-in lullabies / stories / nature / white-noise / songs."""

    _attr_translation_key = "music"
    _attr_supported_features = _FEATURES
    _attr_media_content_type = MediaType.MUSIC

    def __init__(self, coordinator: IbabyCoordinator) -> None:
        super().__init__(coordinator, "music")
        self._attr_state = MediaPlayerState.IDLE
        self._last_track: dict | None = None

    # --- transport ------------------------------------------------------ #
    async def async_media_pause(self) -> None:
        await self.coordinator.async_command(lambda lan: lan.pause_music())
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        await self.coordinator.async_command(lambda lan: lan.stop_music())
        self._attr_state = MediaPlayerState.IDLE
        self._attr_media_title = None
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        await self.coordinator.async_command(lambda lan: lan.next_music())
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_previous_track(self) -> None:
        await self.coordinator.async_command(lambda lan: lan.prev_music())
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        # No bare resume in the protocol surface; replay the last track.
        if self._last_track is not None:
            await self._play_track(self._last_track)

    # --- play a track --------------------------------------------------- #
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        if not media_id.startswith("track/"):
            raise HomeAssistantError(f"Unsupported media id: {media_id}")
        _, category, track_id = media_id.split("/", 2)
        tracks = await self.coordinator.async_music_list(category)
        track = next((t for t in tracks if str(t["id"]) == track_id), None)
        if track is None:
            raise HomeAssistantError(f"Track {track_id} not found in {category}")
        await self._play_track(track)

    async def _play_track(self, track: dict) -> None:
        await self.coordinator.async_command(lambda lan: lan.play_music(track, mode=P.VMODE_SINGLE))
        self._last_track = track
        self._attr_state = MediaPlayerState.PLAYING
        self._attr_media_title = track.get("name")
        self.async_write_ha_state()

    # --- browsing ------------------------------------------------------- #
    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        if media_content_id in (None, "root"):
            return self._browse_root()
        if media_content_id.startswith("category/"):
            return await self._browse_category(media_content_id.split("/", 1)[1])
        raise HomeAssistantError(f"Cannot browse {media_content_id}")

    def _browse_root(self) -> BrowseMedia:
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="root",
            media_content_type="",
            title="iBaby music",
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                BrowseMedia(
                    media_class=MediaClass.DIRECTORY,
                    media_content_id=f"category/{key}",
                    media_content_type="",
                    title=label,
                    can_play=False,
                    can_expand=True,
                )
                for key, label in CATEGORIES.items()
            ],
        )

    async def _browse_category(self, category: str) -> BrowseMedia:
        if category not in CATEGORIES:
            raise HomeAssistantError(f"Unknown category: {category}")
        tracks = await self.coordinator.async_music_list(category)
        return BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id=f"category/{category}",
            media_content_type="",
            title=CATEGORIES[category],
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.TRACK,
            children=[
                BrowseMedia(
                    media_class=MediaClass.TRACK,
                    media_content_id=f"track/{category}/{track['id']}",
                    media_content_type=MediaType.MUSIC,
                    title=track.get("name") or str(track["id"]),
                    can_play=True,
                    can_expand=False,
                )
                for track in tracks
                if track.get("id") is not None
            ],
        )
