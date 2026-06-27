# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""The iBaby Monitor integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pyibaby import Camera

from .const import (
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
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
]


def camera_from_entry(entry: IbabyConfigEntry) -> Camera:
    """Rebuild a pyibaby Camera from the identity stored on the config entry."""
    d = entry.data
    return Camera(
        camid=d[CONF_CAMID],
        camname=d.get(CONF_CAMNAME, ""),
        camtype=d.get(CONF_CAMTYPE, ""),
        p2p_uid=d[CONF_P2P_UID],
        p2p_provider=str(d.get(CONF_P2P_PROVIDER, "1")),
        p2p_password=d[CONF_P2P_PASSWORD],
    )


async def async_setup_entry(hass: HomeAssistant, entry: IbabyConfigEntry) -> bool:
    """Set up an iBaby camera from a config entry."""
    coordinator = IbabyCoordinator(hass, entry, camera_from_entry(entry))
    # Confirms the camera is reachable on the LAN; raises ConfigEntryNotReady if not.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IbabyConfigEntry) -> bool:
    """Unload a config entry, stopping the video bridge and control session."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_shutdown()
    return unload_ok
