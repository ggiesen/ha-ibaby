# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Per-camera RTSP bridge: runs a ``pyibaby.rtspd`` subprocess that holds the
video P2P session and serves it as ``rtsp://127.0.0.1:<port>/cam``.

Home Assistant's bundled go2rtc cannot exec a Python producer (it is locked to
``exec: allow_paths: [ffmpeg]``), so the camera entity hands go2rtc this local
RTSP URL instead and go2rtc ingests it. The subprocess authenticates to the
camera directly from its stored identity (UID/camid/device password), so no
cloud login is needed to stream.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
import sys

from homeassistant.core import HomeAssistant

from .const import RTSP_BIND_HOST

_LOGGER = logging.getLogger(__name__)

_START_TIMEOUT = 15.0


def _free_port() -> int:
    """Pick a currently-free TCP port on the loopback interface."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((RTSP_BIND_HOST, 0))
        return s.getsockname()[1]


class CameraBridge:
    """Owns the per-camera ``pyibaby.rtspd`` subprocess and its stream URL."""

    def __init__(self, hass: HomeAssistant, *, camid: str, p2p_uid: str, p2p_password: str) -> None:
        self.hass = hass
        self._camid = camid
        self._p2p_uid = p2p_uid
        self._p2p_password = p2p_password
        self._proc: asyncio.subprocess.Process | None = None
        self._port: int | None = None
        self._lock = asyncio.Lock()

    async def async_stream_source(self) -> str | None:
        """Return the local RTSP URL, (re)starting the subprocess if needed."""
        async with self._lock:
            if (
                self._proc is None or self._proc.returncode is not None
            ) and not await self._start():
                return None
            return f"rtsp://{RTSP_BIND_HOST}:{self._port}/cam"

    async def _start(self) -> bool:
        port = _free_port()
        env = {
            **os.environ,
            "IBABY_UID": self._p2p_uid,
            "IBABY_CAMID": self._camid,
            "IBABY_DEV_PASSWORD": self._p2p_password,
        }
        _LOGGER.debug("starting pyibaby.rtspd for %s on 127.0.0.1:%s", self._camid, port)
        try:
            self._proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "pyibaby.rtspd",
                "--host",
                RTSP_BIND_HOST,
                "--port",
                str(port),
                "--path",
                "/cam",
                env=env,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as err:
            _LOGGER.error("failed to launch pyibaby.rtspd for %s: %s", self._camid, err)
            return False
        self._port = port
        if not await self._wait_listening(port):
            _LOGGER.error("pyibaby.rtspd for %s did not start serving in time", self._camid)
            await self.async_stop()
            return False
        return True

    async def _wait_listening(self, port: int) -> bool:
        """Wait until the RTSP server accepts connections (or the process dies)."""
        deadline = self.hass.loop.time() + _START_TIMEOUT
        while self.hass.loop.time() < deadline:
            if self._proc is None or self._proc.returncode is not None:
                return False
            try:
                _, writer = await asyncio.open_connection(RTSP_BIND_HOST, port)
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()
                return True
            except OSError:
                await asyncio.sleep(0.25)
        return False

    async def async_stop(self) -> None:
        """Terminate the subprocess, releasing the camera's video session."""
        proc = self._proc
        self._proc = None
        self._port = None
        if proc is None or proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            proc.terminate()
        with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        if proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
