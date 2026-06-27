# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Projector / privacy switches.

State is read back from the camera via GET_PROJECTORLAMP (polled by the
coordinator), so these reflect the real moonlight / music-light / privacy state -
including the projector's own ~15-minute auto-off.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyibaby import LANCamera
from pyibaby.protocol import ProjectorState

from .coordinator import IbabyConfigEntry, IbabyCoordinator
from .entity import IbabyEntity


@dataclass(frozen=True, kw_only=True)
class IbabySwitchDescription(SwitchEntityDescription):
    """Describes a switch: the camera calls that drive it and how to read its state."""

    turn_on: Callable[[LANCamera], None]
    turn_off: Callable[[LANCamera], None]
    is_on_fn: Callable[[ProjectorState], bool]


SWITCHES: tuple[IbabySwitchDescription, ...] = (
    IbabySwitchDescription(
        key="moonlight",
        translation_key="moonlight",
        turn_on=lambda lan: lan.moonlight(True),
        turn_off=lambda lan: lan.moonlight(False),
        is_on_fn=lambda p: p.moonlight_on,
    ),
    IbabySwitchDescription(
        key="music_light",
        translation_key="music_light",
        turn_on=lambda lan: lan.music_light(True),
        turn_off=lambda lan: lan.music_light(False),
        is_on_fn=lambda p: p.music_light_on,
    ),
    IbabySwitchDescription(
        key="privacy",
        translation_key="privacy",
        turn_on=lambda lan: lan.privacy_mode(True),
        turn_off=lambda lan: lan.privacy_mode(False),
        is_on_fn=lambda p: p.privacy,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IbabyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the projector / privacy switches for every camera."""
    async_add_entities(
        IbabySwitch(coordinator, description)
        for coordinator in entry.runtime_data
        for description in SWITCHES
    )


class IbabySwitch(IbabyEntity, SwitchEntity):
    """An on/off control whose state is read back from the camera."""

    entity_description: IbabySwitchDescription

    def __init__(self, coordinator: IbabyCoordinator, description: IbabySwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data
        projector = data.projector if data else None
        if projector is None:
            return None  # state not yet known / read failed
        return self.entity_description.is_on_fn(projector)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.entity_description.turn_on)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.entity_description.turn_off)
        await self.coordinator.async_request_refresh()
