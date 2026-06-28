# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Built-in music player.

The camera plays built-in sounds itself (it fetches the track URL and plays it on
its own speaker), so this is a control + browser surface, not an audio renderer.
The camera reports no reliable playback status, so state is optimistic.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.media_player import (
    BrowseMedia,
    MediaClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyibaby import protocol as P

from .coordinator import IbabyConfigEntry, IbabyCoordinator
from .entity import IbabyEntity

_LOGGER = logging.getLogger(__name__)

# Category key (pyibaby cloud.MUSIC_CATEGORIES) -> display label.
CATEGORIES: dict[str, str] = {
    "lullabies": "Lullabies",
    "stories": "Stories",
    "white_noise": "White noise",
    "nature": "Nature",
    "songs": "Songs",
}

# Hold the control session open this long after a play/next/prev so the camera
# can fetch and latch the track before we close it. Closing too soon aborts the
# fetch -- the card flips to "playing" but nothing comes out of the speaker.
MUSIC_PLAY_SETTLE_S = 4.0

_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
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
        self._pending_track: dict | None = None  # single-slot queue: only the latest pick waits
        self._drain_task: asyncio.Task | None = None
        # Volume is the one media-player attribute the camera reports reliably; seed
        # it from the latest poll and keep it in sync via _handle_coordinator_update.
        self._attr_volume_level = self._poll_volume_level()

    def _poll_volume_level(self) -> float | None:
        """Latest camera volume from the coordinator poll, as a 0.0-1.0 level."""
        data = self.coordinator.data
        if data is not None and data.volume is not None:
            return max(0, min(100, data.volume)) / 100
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        # Refresh the volume slider from the camera each poll (catches changes made
        # from the official app); play state stays optimistic and is left untouched.
        level = self._poll_volume_level()
        if level is not None:
            self._attr_volume_level = level
        super()._handle_coordinator_update()

    async def async_set_volume_level(self, volume: float) -> None:
        vol = round(max(0.0, min(1.0, volume)) * 100)
        await self.coordinator.async_command(lambda lan: lan.set_music_volume(vol))
        self._attr_volume_level = vol / 100
        self.async_write_ha_state()

    def _clear_pending(self) -> None:
        """Drop any queued play so an explicit transport action isn't undone by it.

        An in-flight play (already past the queue, holding the command lock) still
        finishes, but with the pending slot empty the drain loop then exits, so the
        transport command that follows it on the lock wins.
        """
        self._pending_track = None

    # --- transport ------------------------------------------------------ #
    async def async_media_pause(self) -> None:
        self._clear_pending()
        await self.coordinator.async_command(lambda lan: lan.pause_music())
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        self._clear_pending()
        await self.coordinator.async_command(lambda lan: lan.stop_music())
        self._attr_state = MediaPlayerState.IDLE
        self._attr_media_title = None
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        self._clear_pending()
        await self.coordinator.async_command(lambda lan: lan.next_music(), settle=MUSIC_PLAY_SETTLE_S)
        # the device advances to a track we cannot name; don't keep showing the old one
        self._attr_state = MediaPlayerState.PLAYING
        self._attr_media_title = None
        self._last_track = None
        self.async_write_ha_state()

    async def async_media_previous_track(self) -> None:
        self._clear_pending()
        await self.coordinator.async_command(lambda lan: lan.prev_music(), settle=MUSIC_PLAY_SETTLE_S)
        self._attr_state = MediaPlayerState.PLAYING
        self._attr_media_title = None
        self._last_track = None
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        # No bare "resume" in the protocol; replay the last track, or start the
        # first lullaby if nothing's been selected yet so Play isn't a no-op.
        track = self._last_track
        if track is None:
            tracks = await self.coordinator.async_music_list("lullabies")
            track = tracks[0] if tracks else None
        if track is not None:
            await self._play_track(track)

    # --- play a track --------------------------------------------------- #
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        if not media_id.startswith("track/"):
            raise HomeAssistantError(f"Unsupported media id: {media_id}")
        _, category, track_id = media_id.split("/", 2)
        if category not in CATEGORIES:
            raise HomeAssistantError(f"Unknown category: {category}")
        tracks = await self.coordinator.async_music_list(category)
        track = next((t for t in tracks if str(t.get("id")) == track_id), None)
        if track is None:
            raise HomeAssistantError(f"Track {track_id} not found in {category}")
        await self._play_track(track)

    async def _play_track(self, track: dict) -> None:
        # Optimistic UI: reflect the pick right away; the drain confirms or reverts it.
        # _last_track is NOT committed here -- only after a confirmed send -- so a
        # failed play can't leave a permanent fake "playing" or replay a silent track.
        self._attr_state = MediaPlayerState.PLAYING
        self._attr_media_title = track.get("name")
        self.async_write_ha_state()
        # Single-deep queue: whatever is loading runs to completion, and only the
        # LATEST further request waits behind it. Rapid switching collapses to
        # "now loading + last requested" instead of grinding through every tap.
        self._pending_track = track
        if self._drain_task is None or self._drain_task.done():
            # Entry-scoped so HA cancels it on unload/reload (no orphaned session).
            self._drain_task = self.coordinator.config_entry.async_create_background_task(
                self.hass, self._drain(), name=f"ibaby-music-drain-{self.coordinator.camera.camid}"
            )

    async def _drain(self) -> None:
        while self._pending_track is not None:
            track = self._pending_track
            self._pending_track = None
            try:
                await self.coordinator.async_command(
                    lambda lan, t=track: lan.play_music(t, mode=P.VMODE_SINGLE),
                    settle=MUSIC_PLAY_SETTLE_S,
                )
            except Exception:  # noqa: BLE001 - a failed send must not stall the queue or lie about state
                _LOGGER.exception("ibaby music play failed for %s", track.get("name"))
                self._attr_state = MediaPlayerState.IDLE
                self._attr_media_title = None
                self.async_write_ha_state()
            else:
                self._last_track = track  # commit only after a confirmed send

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
