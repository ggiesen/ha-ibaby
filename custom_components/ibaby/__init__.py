# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The iBaby Monitor integration.

One config entry per account; one coordinator (and rtspd video bridge) per camera
on it.
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pyibaby import Camera

from .const import (
    CONF_CAMERAS,
    CONF_CAMID,
    CONF_CAMNAME,
    CONF_CAMTYPE,
    CONF_P2P_PASSWORD,
    CONF_P2P_PROVIDER,
    CONF_P2P_UID,
)
from .coordinator import IbabyConfigEntry, IbabyCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms are added here as they are implemented.
PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
    Platform.SWITCH,
]


def _camera(data: dict) -> Camera:
    """Rebuild a pyibaby Camera from a stored camera identity."""
    return Camera(
        camid=data[CONF_CAMID],
        camname=data.get(CONF_CAMNAME, ""),
        camtype=data.get(CONF_CAMTYPE, ""),
        p2p_uid=data[CONF_P2P_UID],
        p2p_provider=str(data.get(CONF_P2P_PROVIDER, "1")),
        p2p_password=data[CONF_P2P_PASSWORD],
    )


async def async_setup_entry(hass: HomeAssistant, entry: IbabyConfigEntry) -> bool:
    """Set up an iBaby account: one coordinator per camera."""
    coordinators = [IbabyCoordinator(hass, entry, _camera(c)) for c in entry.data[CONF_CAMERAS]]

    # Refresh all cameras in parallel; don't block the whole account on one
    # unreachable camera, but do fail setup (and retry) if none are reachable.
    await asyncio.gather(*(c.async_refresh() for c in coordinators))
    if not any(c.last_update_success for c in coordinators):
        raise ConfigEntryNotReady("no cameras reachable on the LAN")

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IbabyConfigEntry) -> bool:
    """Unload the account entry, stopping every camera's bridge and session."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        for coordinator in entry.runtime_data:
            await coordinator.async_shutdown()
    return unload_ok
