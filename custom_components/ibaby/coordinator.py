# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Coordinator: one short-lived control session per camera, plus the video bridge.

pyibaby's ``LANCamera`` is a blocking, single-socket session. Rather than hold a
persistent control session and multiplex sensors + commands on one socket, this
coordinator opens a fresh control session for each operation (a sensor poll or a
single command) in the executor, guarded by one ``asyncio.Lock``. That bounds the
camera to at most two concurrent P2P sessions - the long-lived video session owned
by the ``CameraBridge`` subprocess, and one control operation at a time - which is
within what the hardware accepts. Connect latency (~1-2 s) is paid per operation;
acceptable for a baby monitor and far simpler than a shared-socket worker thread.

All camera identity is stored on the config entry, so the LAN sessions need no
cloud login; the cloud is only used for the built-in music list.
"""

from __future__ import annotations

import logging
from asyncio import Lock
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyibaby import Camera, IBabyCloud, LANCamera
from pyibaby.protocol import ProjectorState
from pyibaby.sensors import SensorReading

from .bridge import CameraBridge
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_SCAN_INTERVAL_S,
    DOMAIN,
    MANUFACTURER,
    PROJECTOR_READ_TIMEOUT_S,
    SENSOR_READ_TIMEOUT_S,
)

_LOGGER = logging.getLogger(__name__)

type IbabyConfigEntry = ConfigEntry[list[IbabyCoordinator]]


@dataclass
class IbabyData:
    """One poll's worth of camera state."""

    sensors: SensorReading
    projector: ProjectorState | None = None


class IbabyCoordinator(DataUpdateCoordinator[IbabyData]):
    """Polls one camera's environment sensors and dispatches its control commands."""

    config_entry: IbabyConfigEntry

    def __init__(self, hass: HomeAssistant, entry: IbabyConfigEntry, camera: Camera) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {camera.camid}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_S),
        )
        self.camera = camera
        self._lock = Lock()
        self.bridge = CameraBridge(
            hass,
            camid=camera.camid,
            p2p_uid=camera.p2p_uid,
            p2p_password=camera.p2p_password,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Single device grouping every entity for this camera."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.camera.camid)},
            name=self.camera.camname or self.camera.camid,
            manufacturer=MANUFACTURER,
            model=self.camera.camtype or None,
        )

    # --- polling -------------------------------------------------------- #
    async def _async_update_data(self) -> IbabyData:
        async with self._lock:
            try:
                return await self.hass.async_add_executor_job(self._poll)
            except UpdateFailed:
                raise
            except Exception as err:  # noqa: BLE001 - any pyibaby/socket error -> unavailable
                raise UpdateFailed(f"error polling {self.camera.camid}: {err}") from err

    def _poll(self) -> IbabyData:
        lan = LANCamera(self.camera)
        try:
            lan.connect()
            reading = lan.read_sensors(timeout=SENSOR_READ_TIMEOUT_S)
            # Projector/privacy state is best-effort on the same session; a failure
            # there leaves the switches "unknown" rather than failing the whole poll.
            projector = None
            if reading is not None:
                try:
                    projector = lan.get_projector(timeout=PROJECTOR_READ_TIMEOUT_S)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("projector state read failed for %s: %s", self.camera.camid, err)
        finally:
            lan.close()
        if reading is None:
            raise UpdateFailed("no sensor record received")
        return IbabyData(sensors=reading, projector=projector)

    # --- control commands ----------------------------------------------- #
    async def async_command(self, fn: Callable[[LANCamera], None]) -> None:
        """Run a single control command on a fresh, serialized control session."""
        async with self._lock:
            await self.hass.async_add_executor_job(self._command, fn)

    def _command(self, fn: Callable[[LANCamera], None]) -> None:
        lan = LANCamera(self.camera)
        try:
            lan.connect()
            fn(lan)
            lan.pump(1.0)  # service retransmit so the reliable command is delivered
        finally:
            lan.close()

    # --- video + cloud helpers ------------------------------------------ #
    async def async_stream_source(self) -> str | None:
        return await self.bridge.async_stream_source()

    async def async_music_list(self, category: str) -> list[dict]:
        return await self.hass.async_add_executor_job(self._music_list, category)

    def _music_list(self, category: str) -> list[dict]:
        cloud = IBabyCloud()
        cloud.login(
            self.config_entry.data[CONF_EMAIL],
            self.config_entry.data[CONF_PASSWORD],
        )
        return cloud.music_list(category)

    async def async_shutdown(self) -> None:
        await self.bridge.async_stop()
        await super().async_shutdown()
