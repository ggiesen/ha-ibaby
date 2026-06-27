# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Live camera stream.

The entity hands Home Assistant's go2rtc the local ``rtsp://127.0.0.1:<port>/cam``
URL produced by the per-camera ``pyibaby.rtspd`` bridge (see ``bridge.py``); go2rtc
ingests it and serves WebRTC / HLS. Snapshots are pulled from the same URL via the
ffmpeg integration (available on HAOS by default).
"""

from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IbabyConfigEntry, IbabyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IbabyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the camera entity."""
    async_add_entities([IbabyCamera(entry.runtime_data)])


class IbabyCamera(CoordinatorEntity[IbabyCoordinator], Camera):
    """The camera's live video, bridged to go2rtc over local RTSP."""

    _attr_has_entity_name = True
    _attr_name = None  # primary entity: takes the device (camera) name
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator: IbabyCoordinator) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.camera.camid}_camera"

    async def stream_source(self) -> str | None:
        return await self.coordinator.async_stream_source()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        from homeassistant.components.ffmpeg import async_get_image  # noqa: PLC0415

        url = await self.coordinator.async_stream_source()
        if not url:
            return None
        return await async_get_image(self.hass, url, width=width, height=height)
